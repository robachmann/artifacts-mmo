from collections import defaultdict
from datetime import datetime, timedelta, UTC
import json
import os
from typing import Dict, List, Optional, Set

from aws_lambda_powertools.utilities.data_classes import event_source, SQSEvent
from aws_lambda_powertools.utilities.data_classes.sqs_event import SQSRecord
from aws_lambda_powertools.utilities.typing import LambdaContext
from event_priorities import event_priorities
from quest_config_service import QuestConfigService
from quest_leaders import get_quest_join_exclusion_map, get_quest_join_exclusions, get_quest_leaders
from telegram.constants import ParseMode
from trade_limits import get_trade_limits

from artifactsmmo.actions.move_action import MoveAction
from artifactsmmo.client.actions import ActionsClient
from artifactsmmo.client.client import Client
from artifactsmmo.dynamodb.character_table import CharacterTable
from artifactsmmo.dynamodb.counters_table import CountersTable
from artifactsmmo.dynamodb.equipment_lock_table import EquipmentLockTable
from artifactsmmo.dynamodb.skip_events_table import SkipEventsTable
from artifactsmmo.dynamodb.task_progress_table import TaskProgressTable
from artifactsmmo.extensions import CharacterSchemaExtension
from artifactsmmo.game_constants import FAILURE_POSITION_ID
from artifactsmmo.log.logger import logger
from artifactsmmo.models import ActiveEventSchema
from artifactsmmo.quests.quests import Quest
from artifactsmmo.queue.worker_queue import WorkerQueue
from artifactsmmo.service import helpers
from artifactsmmo.service.dispatch_service import DispatchService
from artifactsmmo.service.food_service import FoodService
from artifactsmmo.service.helpers import escape_string, list_to_string, ShoppingBasket
from artifactsmmo.service.service import Service
from artifactsmmo.service.tasks import Task
from artifactsmmo.telegram.client import TelegramClient
from artifactsmmo.templates.template_processor import TemplateProcessor


def is_unfinished(tasks: List[Task], task_id: str) -> bool:
    for task in tasks:
        if task.task_id == task_id and task.action in ['fight', 'gather', 'gather-resource']:
            logger.debug('search for task_id=%s: action=%s, task_id=%s, ttl=%d', task_id, task.action, task.task_id, task.ttl)

            if task.ttl > 0:
                return True
            elif task.until is not None:
                if task.until.status != 'done':
                    return True
    return False


class Dispatcher:
    def __init__(self):
        if os.environ.get('AWS_LAMBDA_FUNCTION_NAME') is None:
            from dotenv import load_dotenv

            load_dotenv()

        self.character_table: CharacterTable = CharacterTable()
        self.task_progress_table: TaskProgressTable = TaskProgressTable()
        self.worker_queue: WorkerQueue = WorkerQueue()
        self.client: Client = Client()
        self.service: Service = Service(self.client)
        food_service: FoodService = FoodService(self.service)
        actions_client = ActionsClient()
        counters_table = CountersTable()
        self.move_action = MoveAction(actions_client, self.service, counters_table, None, self.task_progress_table, None, food_service, None)
        telegram_client: TelegramClient = TelegramClient()
        self.telegram_client = telegram_client
        self.equipment_lock_table = EquipmentLockTable()
        self.skip_events_table = SkipEventsTable()
        self.quest_config_service = QuestConfigService(self.service)
        self.dispatch_service = DispatchService(self.service, self.character_table, self.worker_queue)

    def handler(self, event: SQSEvent, context: LambdaContext):
        records = event.get('Records')
        if records:
            self.handle_sqs_message(event)
        else:
            self.handle_invoke(scheduled_invoke=True)

        return {'statusCode': 200, 'body': json.dumps({'status': 'ok'})}

    def handle_sqs_message(self, event: SQSEvent):
        for record in event.records:
            logger.append_keys(message_id=record.message_id)
            if 'message_type' in record.message_attributes:
                message_type_obj = record.message_attributes.get('message_type')
                message_type = message_type_obj.get('stringValue', '')
                match message_type:
                    case 'invoke':
                        character_list = record.json_body
                        logger.info(f'Invoke dispatcher for parameters={character_list}')
                        self.handle_invoke(character_list)
                    case 'reset':
                        character_list = record.json_body
                        logger.info(f'Reset dispatcher for parameters={character_list}')
                        self.handle_reset(parameters=character_list)
                    case 'restart':
                        character_list = record.json_body
                        logger.info(f'Restart dispatcher for parameters={character_list}')
                        self.handle_restart(parameters=character_list)
                    case 'solve':
                        parameters = record.json_body
                        logger.info(f'Solve dispatcher for parameters={parameters}')
                        self.handle_solve(parameters=parameters)
                    case 'release':
                        character_list = record.json_body
                        logger.info(f'Release dispatcher for parameters={character_list}')
                        self.handle_release(parameters=character_list)
                    case 'join':
                        character_list = record.json_body
                        logger.info(f'Join dispatcher for parameters={character_list}')
                        self.handle_join(parameters=character_list)
                    case 'reset-quest-joiners':
                        logger.info('Reset dispatcher for reset_quest_joiners=True')
                        self.handle_reset(reset_quest_joiners=True)
                    case 'task_list':
                        self.handle_task_list(record)
                    case 'buy':
                        self.handle_buy_command(record)
                    case 'deliver':
                        self.handle_deliver_command(record)
            logger.remove_keys(['message_id'])

    def handle_invoke(self, character_list: List[str] = None, check_success_position: bool = True, scheduled_invoke: bool = False) -> bool:
        all_character_details = self.service.get_all_character_details()
        filtered_character_details = (
            self.service.get_characters_by_param(character_list, characters=all_character_details) if character_list else all_character_details
        )

        if check_success_position:
            overwrite_quest = False
            characters_at_dispatch = [c for c in filtered_character_details if c.at_success_position()]
        else:
            overwrite_quest = True
            characters_at_dispatch = filtered_character_details

        logger.info(
            f'characters_at_dispatch={[c.name for c in characters_at_dispatch]}, '
            f'filtered_character_details={[c.name for c in filtered_character_details]}, overwrite_quest={overwrite_quest}'
        )

        quest_joining_characters_at_dispatch = [c for c in characters_at_dispatch if c.name not in get_quest_join_exclusions()]
        characters_not_at_dispatch: List[CharacterSchemaExtension] = [c for c in filtered_character_details if not c.at_success_position()]
        if not filtered_character_details:
            self.init_season()
            return True

        skip_event_entries: Dict[str, List[str]] = self.skip_events_table.get_all_skip_event_entries()
        if skip_event_entries:
            logger.info(f'Read skip_event_entries={skip_event_entries}')

        dispatched_characters = (
            self.dispatch_events(filtered_character_details, skip_event_entries)
            or self.dispatch_quest_leaders(
                all_character_details,
                characters_at_dispatch,
                filtered_character_details,
                skip_event_entries,
                overwrite_quest,
            )
            or self.dispatch_quest_joiners(quest_joining_characters_at_dispatch, skip_event_entries)
            or self.dispatch_single_quests(characters_at_dispatch, overwrite_quest)
            or self.reset_failures(characters_at_dispatch)
        )
        logger.info('dispatched_characters=%s', dispatched_characters)
        reset_any = self.reset_failures(characters_not_at_dispatch)
        if not reset_any and not dispatched_characters and scheduled_invoke:
            self.perform_health_check(all_character_details)
        return dispatched_characters

    def handle_reset(self, parameters: List[str] = None, reset_quest_joiners: bool = False):
        characters: List[CharacterSchemaExtension] = self.service.get_characters_by_param(parameters)
        if reset_quest_joiners:
            exclude_quest_joiners: List[str] = [*get_quest_join_exclusions(), *get_quest_leaders()]
            for character in self.service.get_all_character_details():
                character_already_reset = False
                for reset_character in characters:
                    if reset_character.name == character.name:
                        character_already_reset = True
                        break

                if not character_already_reset and character.name not in exclude_quest_joiners:
                    characters.append(character)

        self.reset_characters(characters)

    def handle_restart(self, parameters: List[str] = None):
        characters: List[CharacterSchemaExtension] = self.service.get_characters_by_param(parameters)
        self.restart_characters(characters)

    def handle_solve(self, parameters: dict = None):
        character_name = parameters.get('character_name')
        count = int(parameters.get('count', 1))
        logger.info(f'handle_solve for character_name={character_name} count={count}')
        if character_name and count:
            character = self.service.get_character_details(character_name)
            self.solve_task(character, count)

    def handle_release(self, parameters: List[str] = None):
        characters: List[CharacterSchemaExtension] = self.service.get_characters_by_param(parameters)
        self.release_characters(characters)

    def handle_join(self, parameters: List[str] = None):
        characters = self.service.get_characters_by_param(parameters)
        exclude_quest_joiners = set(get_quest_join_exclusions()) | set(get_quest_leaders())
        characters_to_handle = [char for char in characters if char.name not in exclude_quest_joiners]
        logger.info(
            f'Handle /join command for characters={[char.name for char in characters]}, '
            f'exclude_quest_joiners={exclude_quest_joiners}, result={[char.name for char in characters_to_handle]}'
        )
        self.dispatch_quest_joiners(characters_to_handle, {}, force_join=True)

    def handle_task_list(self, record: SQSRecord):
        all_character_details: List[CharacterSchemaExtension] = self.service.get_all_character_details()
        characters_at_dispatch: List[CharacterSchemaExtension] = [c for c in all_character_details if c.at_success_position()]
        if 'quest_id' in record.message_attributes:
            quest_id_obj = record.message_attributes.get('quest_id')
            quest_id = quest_id_obj.get('stringValue', '')
            leader_obj = record.message_attributes.get('leader')
            leader = leader_obj.get('stringValue', '')

            if quest_id:
                task_list: List[Task] = [Task.from_dict(j) for j in record.json_body]
                logger.info(f'Got SQS message for quest_id={quest_id} from leader={leader}, task list size {len(task_list)}')

                quest_joiners: List[str] = []
                for character in characters_at_dispatch:
                    if character.name != leader and self.character_table.get_quest(character.name) is None:
                        for t in task_list:
                            if t.action == 'gather-recipe':
                                t.ttl = 1
                        self.dispatch_service.dispatch(
                            character=character,
                            task_list=task_list,
                            quest_id=quest_id,
                            is_new_quest_id=True,
                            leader=leader,
                        )
                        quest_joiners.append(character.name)

                if len(quest_joiners) > 0:
                    self.telegram_client.send_notification(
                        f'✨ {list_to_string(quest_joiners, fmt="*")} joined quest of *{escape_string(leader)}*\\.', parse_mode='MarkdownV2'
                    )

    def dispatch_events(self, all_character_details: List[CharacterSchemaExtension], skip_event_entries: Dict[str, List[str]]) -> bool:
        dispatched_characters = False
        active_events: List[ActiveEventSchema] = self.service.get_active_events()

        if not active_events:
            return False
        else:
            logger.info(f'active_events={[e.code for e in active_events]}')

        active_events_map: Dict[str, ActiveEventSchema] = {event.map.interactions.content.code: event for event in active_events}
        event_priorities_map: Dict[str, List[str]] = event_priorities()

        joiner_map: Dict[str, List[str]] = defaultdict(list)
        npc_interactions: Set[str] = set()
        for character in all_character_details:
            for content_code in event_priorities_map.get(character.name, []):  # What we configured in the event_priorities file
                active_event = active_events_map.get(content_code)  # check if currently active
                should_skip_event = content_code in skip_event_entries.get(character.name, [])
                if active_event and not should_skip_event:
                    mp = active_event.map
                    if character.map_id not in [mp.map_id, FAILURE_POSITION_ID]:
                        active_quest = self.character_table.get_quest(character.name)
                        if not active_quest or (active_quest.status != content_code and not active_quest.is_locked()):
                            event_parameters: Dict[str, Dict[str, int]] = {}
                            if mp.interactions.content.type == 'resource' and (resource := self.service.get_resource(content_code)) is not None:
                                if character.skills[str(resource.skill)].level < resource.level:
                                    logger.info(f'Character={character.name} cannot participate in event (yet).')
                                    continue
                            elif mp.interactions.content.type == 'npc':
                                npc_code = mp.interactions.content.code
                                trade_limits = get_trade_limits()
                                if trade_limits:
                                    npc = self.service.get_npc(npc_code)
                                    if any(item_code in npc.items for item_code in trade_limits):
                                        bank_items_map = self.service.get_bank_items_map()
                                        global_quantity_map: Dict[str, int] = self.service.get_global_quantity_map(bank_items_map=bank_items_map)
                                        available_gold = self.service.get_bank_details().gold + character.gold

                                        for item_code, limits in trade_limits.items():
                                            if item_code in npc.items:
                                                global_quantity = global_quantity_map.get(item_code, 0)
                                                threshold = limits.get('threshold', 0)
                                                if 'max_quantity' in limits:
                                                    max_quantity = limits['max_quantity']
                                                    if bank_items_map.get(item_code, 0) > 0 and global_quantity > max_quantity + threshold:
                                                        if self.__trade_value_above_1g(global_quantity - max_quantity, npc.items[item_code]):
                                                            event_parameters[item_code] = limits
                                                            npc_interactions.add(item_code)

                                                elif 'min_quantity' in limits and global_quantity < limits['min_quantity']:
                                                    if available_gold > npc.items[item_code].buy_price:
                                                        event_parameters[item_code] = limits
                                                        npc_interactions.add(item_code)

                                        if not event_parameters:
                                            logger.info(f'Nothing to trade with npc={npc_code} or insufficient gold available.')
                                            continue

                                    else:
                                        logger.info(f'No trade limits defined for npc={npc_code}, skipping event.')
                                        continue

                            self.dispatch_event_tasks(character=character, active_event=active_event, event_parameters=event_parameters)
                            joiner_map[content_code].append(character.name)
                            dispatched_characters = True
                    else:
                        logger.debug(
                            'Skip assigning event to character=%s, target_location=(%d, %d), current_position=(%d, %d)',
                            character.name,
                            mp.x,
                            mp.y,
                            character.x,
                            character.y,
                        )
                    break

        for content_code, character_list in joiner_map.items():
            time_str = self.telegram_client.format_time_at_user_timezone(active_events_map[content_code].expiration)

            npc_interactions_str = ''
            if npc_interactions:
                npc_interactions_str = f' Plan to trade: {escape_string(", ".join(npc_interactions))}\\.'

            self.telegram_client.send_notification(
                f'⚡ Assigned event task *{escape_string(content_code)}* '
                f'\\(until {escape_string(time_str)}\\) '
                f'to {list_to_string(character_list, fmt="*")}\\.{npc_interactions_str}',
                parse_mode=ParseMode.MARKDOWN_V2,
            )

        return dispatched_characters

    def dispatch_event_tasks(
        self, character: CharacterSchemaExtension, active_event: ActiveEventSchema, event_parameters: Dict[str, Dict[str, int]]
    ):
        tasks = [
            Task.reload_character(),
            Task.unequip_utilities(),
            Task.ensure_inventory(),
            Task.solve_event(
                content_type=active_event.map.interactions.content.type,
                content_code=active_event.map.interactions.content.code,
                map_id=active_event.map.map_id,
                event_parameters=event_parameters,
            ),
        ]
        self.dispatch_service.dispatch(
            character=character,
            task_list=tasks,
            quest_id=Quest.generate_quest_id(),
            is_new_quest_id=True,
            status=active_event.map.interactions.content.code,
            #    created_at=created_at,
        )
        self.service.delete_bank_reservations(character_name=character.name)

    def dispatch_quest_leaders(
        self,
        all_character_details: List[CharacterSchemaExtension],
        characters_at_dispatch: List[CharacterSchemaExtension],
        filtered_character_details: List[CharacterSchemaExtension],
        skip_event_entries: Dict[str, List[str]],
        overwrite_quest: bool = False,
    ) -> bool:
        quest_map: Dict[str, List[Task]] = self.quest_config_service.get_quest_leaders(all_character_details)

        # quest_map: Dict[str, List[Task]] = quest_leaders(skill_map)
        character_details_map = {character.name: character for character in filtered_character_details}

        for leader, task_list in quest_map.items():
            logger.info(
                f'dispatch_quest_leaders: leader={leader}, task_list_len={len(task_list)}, '
                f'characters_at_dispatch={[c.name for c in characters_at_dispatch]}'
            )
            if task_list:
                should_skip_event = leader in skip_event_entries.get(leader, [])

                if (
                    not should_skip_event
                    and any([c.name == leader for c in characters_at_dispatch])
                    and (not self.character_table.get_quest(leader) or overwrite_quest)
                ):
                    self.dispatch_service.dispatch(
                        task_list=task_list,
                        quest_id=Quest.generate_quest_id(),
                        is_new_quest_id=True,
                        character=character_details_map[leader],
                        leader=leader,
                    )
                    self.telegram_client.send_notification(f'🧙‍♂️ *{escape_string(leader)}* started a quest\\.', parse_mode='MarkdownV2')
                    return True
                else:
                    logger.info(
                        f'Did not dispatch leader={leader}, should_skip_event={should_skip_event}, '
                        f'leader_at_dispatch={any([c.name == leader for c in characters_at_dispatch])}, '
                        f'not_active_quest={self.character_table.get_quest(leader) is None} or overwrite_quest={overwrite_quest}'
                    )
        return False

    def dispatch_quest_joiners(
        self, characters_at_dispatch: List[CharacterSchemaExtension], skip_event_entries: Dict[str, List[str]], force_join: bool = False
    ) -> bool:
        if characters_at_dispatch:
            all_quests: List[Quest] = self.character_table.get_all_quests()
            quest_map: Dict[str, Quest] = {q.character_name: q for q in all_quests}
            logger.info(f'dispatch_quest_joiners: all_quests_len={len(all_quests)}')

            for quest in all_quests:
                if quest.quest_id:
                    gather_tasks: List[Task] = []
                    for task in quest.tasks:
                        if task.action == 'gather-recipe' and task.extra.get('leader', '') == quest.character_name:
                            bank_items_map = self.service.get_bank_items_map(task_id=task.task_id)
                            item_code = task.extra.get('item')
                            quantity = task.extra.get('quantity')
                            force_gather = task.extra.get('force_gather')
                            if self.gather_recipe_unfinished(item_code, bank_items_map, quantity, force_gather):
                                gather_tasks.append(task)

                    gather_queue = [t for t in gather_tasks if is_unfinished(quest.tasks, t.task_id)]

                    if gather_queue:
                        logger.info(
                            f'Found quest={quest.quest_id} of leader={quest.character_name} with unfinished gather tasks: {len(gather_queue)}'
                        )
                        quest_joiners: List[str] = []
                        join_exclusion_map = get_quest_join_exclusion_map()
                        for character in characters_at_dispatch:
                            if character.name in join_exclusion_map.get(quest.character_name, []):
                                logger.info(f'Character={character.name} is not allowed to join quest of leader={quest.character_name}.')
                                continue

                            if quest.character_name in skip_event_entries.get(character.name, []):
                                continue

                            active_quest = quest_map.get(character.name)
                            if active_quest:
                                if not force_join:
                                    continue

                                if character.name == quest.character_name:
                                    continue

                                if active_quest.leader and active_quest.leader == quest.character_name:
                                    logger.info(f"Character {character.name} has already joined {quest.character_name}'s quest.")
                                    continue

                                if active_quest.description == 'solve-event':
                                    logger.info(f'Character {character.name} is currently occupied by an event.')
                                    continue

                                self.service.delete_bank_reservations(character_name=character.name)
                                self.equipment_lock_table.release_lock(locked_by=character.name)

                            for t in gather_queue:
                                t.ttl = 1

                            created_at: datetime = active_quest.created_at if active_quest else datetime.now(UTC)
                            self.dispatch_service.dispatch(
                                gather_queue,
                                quest.quest_id,
                                is_new_quest_id=True,
                                character=character,
                                leader=quest.character_name,
                                created_at=created_at,
                            )
                            quest_joiners.append(character.name)

                        if quest_joiners:
                            self.telegram_client.send_notification(
                                f'✨ {list_to_string(quest_joiners, fmt="*")} joined quest of *{escape_string(quest.character_name)}*\\.',
                                parse_mode='MarkdownV2',
                            )
                            return True
                    else:
                        logger.debug('Found no unfinished gather tasks for quest=%s', quest.quest_id)
        return False

    def dispatch_single_quests(self, characters_at_dispatch: List[CharacterSchemaExtension], overwrite_quest: bool = False) -> bool:
        dispatched_task = False
        character_list: List[str] = []
        for character in characters_at_dispatch:
            tasks: List[Task] = self.quest_config_service.get_character_quest(character)
            if tasks:
                if not self.character_table.get_quest(character.name) or overwrite_quest:
                    self.dispatch_service.dispatch(tasks, quest_id=Quest.generate_quest_id(), is_new_quest_id=True, character=character)
                    character_list.append(character.name)
                    dispatched_task = True
                else:
                    logger.info('Skipping new quest for character=%s at (%d, %d)', character.name, character.x, character.y)

        if character_list:
            self.telegram_client.send_notification(
                f'🆕 Assigned new tasks to {list_to_string(character_list, fmt="*")}\\.', parse_mode='MarkdownV2'
            )

        return dispatched_task

    def reset_failures(self, character_details: List[CharacterSchemaExtension]) -> bool:
        result = False
        character_list: List[str] = []
        now = datetime.now(UTC)
        locked_characters = self.equipment_lock_table.get_locked_characters(now)

        for character in character_details:
            if self.character_stranded(character, locked_characters, now):
                logger.info(
                    f'Resetting stranded character={character.name}, locked_characters={locked_characters}, '
                    f'cooldown={character.cooldown_expiration} ({now.replace(microsecond=0) - character.cooldown_expiration.replace(microsecond=0)})'
                )
                active_quest = self.character_table.get_quest(character.name)

                cancel_quest = True
                if active_quest:
                    first_unfinished_task = None
                    for task in active_quest.tasks:
                        if task.ttl > 0:
                            first_unfinished_task = task
                            break
                    if first_unfinished_task:
                        if first_unfinished_task.action == 'sleep':
                            if character.cooldown_expiration + timedelta(minutes=60) > now:
                                logger.info(f'First unfinished task is a sleep action. Let character sleep {first_unfinished_task.ttl} times.')
                                cancel_quest = False
                        elif first_unfinished_task.action in ['fight-monster', 'gather-resource', 'multi-character-fight', 'deliver-food']:
                            if character.cooldown_expiration + timedelta(minutes=15) > now:
                                logger.info(f'First unfinished task is a fight-monster action. Let character {character.name} obtain lock.')
                                cancel_quest = False
                        else:
                            logger.info(f'First unfinished task is of action={first_unfinished_task.action}.')

                if cancel_quest:
                    self.service.delete_bank_reservations(character_name=character.name)
                    if active_quest:
                        self.character_table.delete_quest(character.name)
                        logger.info(f'Deleted quest object of stranded character={character.name}')

                    if not character.at_success_position():
                        if character.map_id == FAILURE_POSITION_ID:
                            self.move_action.process(character, Task.move_success())
                        else:
                            self.dispatch_service.dispatch(
                                character=character,
                                task_list=[],
                                quest_id=Quest.generate_quest_id(),
                                is_new_quest_id=True,
                                status='Return to start',
                                active_quest=active_quest,
                                skip_post_tasks=False,
                            )
                        logger.info(f'Moved stranded character={character.name} back to dispatch position.')
                        character_list.append(character.name)
                        result = True

        if character_list:
            self.telegram_client.send_notification(
                f'⏪ Moved {list_to_string(character_list, fmt="*")} back to dispatch position\\.', parse_mode='MarkdownV2'
            )
        return result

    def reset_characters(self, character_details: List[CharacterSchemaExtension]):
        character_list: List[str] = []
        self.service.delete_bank_reservations(character_list=character_details)
        for character in character_details:
            self.equipment_lock_table.release_lock(locked_by=character.name)
            skip_events = self.skip_events_table.get_all_skip_event_entries().get(character.name, [])
            for skip_event in skip_events:
                self.skip_events_table.delete_skip_entry(character.name, skip_event)
            active_quest = self.character_table.get_quest(character.name)
            created_at: datetime = active_quest.created_at if active_quest else datetime.now(UTC)
            self.dispatch_service.dispatch(
                character=character,
                task_list=[],
                quest_id=Quest.generate_quest_id(),
                is_new_quest_id=True,
                status='Return to start',
                created_at=created_at,
                skip_pre_tasks=True,
                skip_post_tasks=False,
            )
            logger.info(f'Sent character={character.name} back to dispatch position.')
            character_list.append(character.name)
        if character_list:
            self.telegram_client.send_notification(
                f'⏪ Sent {list_to_string(character_list, fmt="*")} back to dispatch position\\.', parse_mode='MarkdownV2'
            )

    def restart_characters(self, character_details: List[CharacterSchemaExtension]):
        character_list: List[str] = []
        self.service.delete_bank_reservations(character_list=character_details)
        for character in character_details:
            self.equipment_lock_table.release_lock(locked_by=character.name)
            dispatched_character = self.handle_invoke(character_list=[character.name], check_success_position=False)
            if dispatched_character:
                logger.info(f'Restarted character={character.name}.')
                character_list.append(character.name)
        if character_list:
            self.telegram_client.send_notification(
                f'🔄 Restarted tasks of {list_to_string(character_list, fmt="*")}\\.', parse_mode='MarkdownV2'
            )
        else:
            self.telegram_client.send_notification('🔄 No tasks restarted\\.', parse_mode='MarkdownV2')

    def solve_task(self, character: CharacterSchemaExtension, count: int = 1):
        self.service.delete_bank_reservations(character_name=character.name)
        self.equipment_lock_table.release_lock(locked_by=character.name)
        active_quest = self.character_table.get_quest(character.name)
        self.dispatch_service.dispatch(
            task_list=count * [Task.solve_task()],
            character=character,
            quest_id=Quest.generate_quest_id(),
            is_new_quest_id=True,
            skip_pre_tasks=True,
            active_quest=active_quest,
        )

    def release_characters(self, character_details: List[CharacterSchemaExtension]):
        character_list: List[str] = []
        self.service.delete_bank_reservations(character_list=character_details)
        for character in character_details:
            self.equipment_lock_table.release_lock(locked_by=character.name)
            self.character_table.delete_quest(character.name)
            logger.info(f'Released character={character.name}.')
            character_list.append(character.name)
        if character_list:
            self.telegram_client.send_notification(
                f'🕹️ Released {list_to_string(character_list, fmt="*")}, ready to be controlled manually\\.', parse_mode='MarkdownV2'
            )

    def init_season(self):
        character_names: List[str] = helpers.get_character_list()
        for idx, character_name in enumerate(character_names):
            created_character = self.service.create_character(idx, character_name)
            logger.info(f'Created character={created_character.name}, skin={str(created_character.skin)}')
            self.dispatch_service.dispatch(
                character=created_character,
                task_list=[Task.unequip(slot='weapon'), Task.ensure_inventory()],
                quest_id=Quest.generate_quest_id(),
                is_new_quest_id=True,
                skip_pre_tasks=True,
                skip_post_tasks=True,
            )

    @staticmethod
    def character_stranded(character: CharacterSchemaExtension, locked_characters: List[str], now: datetime):
        minutes = 10 if character.name in locked_characters else 1
        return character.cooldown_expiration + timedelta(minutes=minutes) < now

    def gather_recipe_unfinished(self, item_code, bank_items_map, quantity, force_gather):
        resolved_recipe = self.service.resolve_item_recipe(item_code, bank_items_map, quantity, force_gather)
        return len(resolved_recipe.missing_items) > 0

    def handle_buy_command(self, record: SQSRecord):
        bsk = record.json_body
        basket = ShoppingBasket(bsk.get('quantity'), bsk.get('item'), bsk.get('order_id'))
        logger.info(f'Received buy command: quantity={basket.quantity}, item={basket.item}, order_id={basket.order_id}')

        all_characters = self.service.get_all_character_details()
        now = datetime.now(UTC)
        ge_map = self.service.get_closest_location(content_type='grand_exchange')

        required_gold: int = self.service.resolve_buy_order(basket)
        if required_gold > 0:
            character_ranks: Dict[str, int] = {}
            for character in all_characters:
                current_map = self.service.get_map_by_id(character.map_id)
                quest = self.character_table.get_quest(character.name)
                if quest is None or quest.status is None or not quest.status.startswith('Buy'):
                    total_seconds = 0
                    total_seconds += max((character.cooldown_expiration - now).total_seconds(), 0)

                    if required_gold <= character.gold:  # required gold in inventory
                        distance = self.service.get_distance_between(current_map, ge_map)
                        total_seconds += distance * 5
                    else:  # trip to bank required
                        total_seconds += 3  # withdrawal cooldown
                        bank_map = self.service.get_closest_location('bank', current_map=current_map)
                        bank_distance = self.service.get_distance_between(current_map, bank_map)
                        total_seconds += bank_distance * 5
                        bank_ge_distance = self.service.get_distance_between(bank_map, ge_map)
                        total_seconds += bank_ge_distance * 5
                    character_ranks[character.name] = total_seconds

            quickest_character = min(character_ranks, key=character_ranks.get)
            logger.info(f'Calculated character_ranks={character_ranks}, quickest_character={quickest_character}')

            for character in all_characters:
                if character.name == quickest_character:
                    self.service.delete_bank_reservations(character_list=[character])
                    self.equipment_lock_table.release_lock(locked_by=character.name)
                    active_quest = self.character_table.get_quest(character.name)
                    created_at: datetime = active_quest.created_at if active_quest else datetime.now(UTC)

                    if basket.order_id:
                        task = Task.buy_order(basket.order_id, basket.quantity)
                        target = basket.order_id
                    else:
                        task = Task.buy_item(basket.item, basket.quantity, True)
                        target = basket.item
                    status = f'Buy {target}'

                    self.dispatch_service.dispatch(
                        character=character,
                        task_list=[task],
                        quest_id=Quest.generate_quest_id(),
                        is_new_quest_id=True,
                        status=status,
                        created_at=created_at,
                        skip_pre_tasks=True,
                        skip_post_tasks=True,
                    )

                    self.telegram_client.send_notification(
                        f'🛒 Sent *{escape_string(character.name)}* to buy {escape_string(target)} for *{required_gold}*g\\.',
                        parse_mode='MarkdownV2',
                    )
                    break
        else:
            self.telegram_client.send_notification('Could not fulfil buy command.')

    def handle_deliver_command(self, record: SQSRecord):
        character_name = record.body
        logger.info(f'Received deliver command: character_name={character_name}')

        all_characters = self.service.get_all_character_details()
        boss_monster_map_id = 0

        dispatch_character: Optional[CharacterSchemaExtension] = None
        dispatch_character_quest: Optional[Quest] = None
        for character in all_characters:
            if character.name == character_name:
                dispatch_character = character
            if not boss_monster_map_id:
                active_quest = self.character_table.get_quest(character.name)
                if active_quest and active_quest.status and active_quest.status.startswith('boss-fight'):
                    for task in active_quest.tasks:
                        if task.ttl and task.action == 'multi-character-fight' and task.extra.get('map_id'):
                            boss_monster_map_id = int(task.extra.get('map_id'))
                            break

        if boss_monster_map_id:
            logger.info(f'Found active boss fight at map_id={boss_monster_map_id}. Plan to dispatch character={character_name}.')
            self.dispatch_service.dispatch(
                task_list=[Task.deliver_food(map_id=boss_monster_map_id)],
                quest_id=Quest.generate_quest_id(),
                is_new_quest_id=True,
                character=dispatch_character,
                status='deliver-food',
                active_quest=dispatch_character_quest,
                skip_pre_tasks=True,
            )
        else:
            logger.warning(f'No active boss fight. Will not dispatch character={character_name}')

    @staticmethod
    def __trade_value_above_1g(quantity, item):
        return item.currency != 'gold' or item.sell_price is None or quantity * item.sell_price > 30

    def perform_health_check(self, all_character_details: List[CharacterSchemaExtension]):
        message, restart_characters = self.service.perform_health_check(all_character_details)
        if message:
            self.telegram_client.send_notification(message)

        if restart_characters:
            self.restart_characters([c for c in all_character_details if c.name in restart_characters])


dispatcher = Dispatcher()


@event_source(data_class=SQSEvent)
def handler(event: SQSEvent, context: LambdaContext):
    dispatcher.handler(event, context)


if __name__ == '__main__':
    dispatcher.handler(SQSEvent(data={}), LambdaContext())
