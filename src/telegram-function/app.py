from collections import defaultdict
from datetime import datetime, timedelta, UTC
from itertools import groupby
import json
import os
from typing import Dict, List, Optional, Set, Tuple

from aws_lambda_powertools.utilities.data_classes import event_source, SQSEvent
from aws_lambda_powertools.utilities.data_classes.sqs_event import SQSRecord
from aws_lambda_powertools.utilities.typing import LambdaContext
from telegram import Message, Update
from telegram.constants import ParseMode

from artifactsmmo import game_constants
from artifactsmmo.actions.action_processor import ActionProcessor
from artifactsmmo.client.actions import ActionsClient
from artifactsmmo.client.client import Client
from artifactsmmo.dynamodb.bank_reservations_table import BankReservation
from artifactsmmo.dynamodb.character_table import CharacterTable
from artifactsmmo.dynamodb.counters_table import CountersTable
from artifactsmmo.dynamodb.skill_stats_table import SkillStatsTable
from artifactsmmo.dynamodb.task_progress_table import TaskProgressTable
from artifactsmmo.dynamodb.withdraw_table import WithdrawTable
from artifactsmmo.extensions import CharacterSchemaExtension, ItemSchemaExtension, MonsterSchemaExtension, NPCSchemaExtension
from artifactsmmo.extensions.account_achievement_schema_extension import AccountAchievementSchemaExtension
from artifactsmmo.game_constants import GATHERING_SKILLS
from artifactsmmo.log.logger import logger
from artifactsmmo.models import (
    AccountAchievementObjectiveSchema,
    AccountLeaderboardSchema,
    AchievementType,
    GEOrderSchema,
    ItemType,
    PendingItemSchema,
)
from artifactsmmo.quests.quests import Quest
from artifactsmmo.queue.dispatcher_queue import DispatcherQueue
from artifactsmmo.queue.worker_queue import WorkerQueue
from artifactsmmo.service.dispatch_service import DispatchService
from artifactsmmo.service.fight_simulator import FightSimulator
from artifactsmmo.service.follower_service import FollowerService
from artifactsmmo.service.food_service import FoodService
from artifactsmmo.service.helpers import (
    account_name,
    character_1_name,
    character_2_name,
    character_3_name,
    character_4_name,
    character_5_name,
    escape_string,
    format_dict,
    format_level,
    format_long_number,
    format_number,
    list_to_string,
    ResolvedItemRecipe,
    ResolvedItemRecipeDetails,
    ShoppingBasket,
)
from artifactsmmo.service.report import Report
from artifactsmmo.service.service import Service
from artifactsmmo.service.tasks import Task
from artifactsmmo.static.static_files import StaticFiles
from artifactsmmo.telegram.client import TelegramClient
from artifactsmmo.templates.template_processor import TemplateProcessor


class TelegramFunction:
    def __init__(self):
        if os.environ.get('AWS_LAMBDA_FUNCTION_NAME') is None:
            from dotenv import load_dotenv

            load_dotenv()

        self.account_name = account_name()
        self.character_1_name = character_1_name()
        self.character_2_name = character_2_name()
        self.character_3_name = character_3_name()
        self.character_4_name = character_4_name()
        self.character_5_name = character_5_name()
        self.telegram_chat_id = int(os.environ.get('TELEGRAM_CHAT_ID'))
        self.client: Client = Client()
        self.service: Service = Service(self.client)
        self.food_service: FoodService = FoodService(self.service)
        self.fight_simulator = FightSimulator(self.service)
        self.report = Report(self.service, self.fight_simulator)
        self.dispatcher_queue = DispatcherQueue()
        self.telegram_client = TelegramClient()
        self.withdraw_table = WithdrawTable()
        self.counters_table = CountersTable()
        self.character_table = CharacterTable()
        self.follower_service = FollowerService()
        self.action_processor = ActionProcessor(
            ActionsClient(),
            self.service,
            CountersTable(),
            self.telegram_client,
            TaskProgressTable(),
            SkillStatsTable(),
            self.food_service,
            self.character_table,
        )
        self.template_processor = TemplateProcessor(self.client, self.service, self.telegram_client, self.food_service)
        worker_queue: WorkerQueue = WorkerQueue()
        self.dispatch_service = DispatchService(self.service, self.character_table, worker_queue)

    def handler(self, event: SQSEvent = None, context: LambdaContext = None):
        for record in event.records:
            self.handle_record(record)

        return {'statusCode': 200, 'body': json.dumps({'status': 'ok'})}

    def handle_record(self, record: SQSRecord):
        update = Update.de_json(record.json_body)
        chat = update.effective_chat
        if chat.id == self.telegram_chat_id:
            self.handle_message(update.message)
        else:
            logger.error(
                f'Received message from foreign chat_id: {chat.id}. Only the owner is allowed to interact with this API: {self.telegram_chat_id}'
            )

    def handle_message(self, message: Message):
        text: str = message.text
        if text:
            parts = text.split()
            command: str = parts[0]
            parameters: List[str] = parts[1:] if len(parts) > 1 else []
            logger.info(f'Received {command} command with parameters={parameters}')
            match command:
                case '/dispatch':  # parameters are characters
                    self.dispatcher_queue.invoke(parameters)

                case '/reset':  # parameters are characters
                    self.dispatcher_queue.reset(parameters)

                case '/restart':  # parameters are characters
                    self.dispatcher_queue.restart(parameters)

                case '/release':  # parameters are characters
                    self.dispatcher_queue.release(parameters)

                case '/clear':  # parameters are characters
                    self.handle_clear_command(parameters)

                case '/join':  # parameters are characters
                    self.dispatcher_queue.join(parameters)

                case '/buy':
                    self.handle_buy_command(parameters)

                case '/buys':
                    self.handle_buys_command(parameters)

                case '/fill':
                    self.handle_fill_command(parameters)

                case '/init':
                    self.handle_init_command(parameters)

                case '/status':
                    self.handle_status_command()

                case '/status2':
                    self.handle_status_v2_command()

                case '/events':
                    self.handle_events_command()

                case '/resolve':
                    self.handle_resolve_command(parameters)

                case '/bank':  # parameter is item category
                    self.handle_bank_command(parameters)

                case '/ge':
                    self.handle_ge_command(parameters)

                case '/char':  # parameters are characters
                    self.handle_char_command(parameters)

                case '/level' | '/levels':  # parameters are characters
                    self.handle_level_command(parameters)

                case '/follow':  # parameters are characters
                    self.handle_follow_command(parameters)

                case '/monitor':  # parameters are characters
                    self.handle_follow_command(parameters, 'monitor')

                case '/achievement':
                    self.handle_achievement_command(parameters)

                case '/achievements':
                    self.handle_achievements_command(parameters)

                case '/leaderboard' | '/leaders':
                    self.handle_leaderboard_command(parameters)

                case '/item':
                    self.handle_item_command(parameters)

                case '/compare':
                    self.handle_compare_command(parameters)

                case '/monster':
                    self.handle_monster_command(parameters)

                case '/npc':
                    self.handle_npc_command(parameters)

                case '/matrix':
                    self.handle_matrix_command(parameters)

                case '/solve':  # parameters are characters
                    self.handle_solve_command(parameters)

                case '/patch':  # parameters are characters
                    self.handle_patch_command(parameters)

                case '/bring' | '/deliver':  # parameters are characters
                    self.handle_deliver_command(parameters)

                case '/task' | '/tasks':  # parameters are characters
                    self.handle_tasks_command(parameters)

                case '/current':  # parameters are characters
                    self.handle_tasks_command(parameters, skip_done=True, skip_next=False)

                case '/res' | '/reservations':  # parameters are characters
                    self.handle_reservations_command(parameters)

                case '/pending':
                    self.handle_pending_command(parameters)

                case '/test':  # parameters are characters
                    self.handle_test_command(parameters)

                case '/tools':  # parameters are characters
                    self.handle_tools_command(parameters)

                case _:
                    if self.service.get_item(command):
                        self.handle_item_command(parts)
                    elif self.service.get_monster(command):
                        self.handle_monster_command(parts)
                    elif self.service.get_npc(command):
                        self.handle_npc_command(parts)

    def handle_init_command(self, parameters: List[str]):
        pass

    def handle_status_command(self):
        all_character_details = self.service.get_all_character_details()
        message: str = self.report.create_report(all_character_details)
        if message:
            self.telegram_client.send_notification(message)

    def handle_status_v2_command(self):
        all_character_details = self.service.get_all_character_details()
        message: str = self.report.create_report_v2(all_character_details)
        if message:
            self.telegram_client.send_notification(message)

    def handle_events_command(self):
        lines = []
        active_events = self.service.get_active_events()
        now = datetime.now(UTC).replace(microsecond=0)
        for event in active_events:
            etc = event.expiration.replace(microsecond=0) - now
            time = self.telegram_client.format_time_at_user_timezone(event.expiration)
            line = f'{event.name} ({event.map.interactions.content.code}) ⏱️ {etc} @ {time}'
            lines.append(escape_string(line))

        if lines:
            message = '\n'.join(['*Active Events*', *lines])
        else:
            message = 'Currently no active events\\.'

        self.telegram_client.send_notification(message, parse_mode=ParseMode.MARKDOWN_V2)

    def handle_bank_command(self, parameters: List[str]):
        bank_items_map = self.service.get_bank_items_map(ignore_reservations=True)
        bank_reservations_map = self.service.get_bank_reservations_map()

        bank_items = [self.service.get_item(i) for i in bank_items_map.keys()]
        processed_food_codes = []
        unprocessed_food_codes = []
        if parameters:
            if 'food' in parameters:
                processed_food_codes = [f.code for f in self.service.get_processed_food()]
                unprocessed_food_codes = [f.code for f in self.service.get_unprocessed_food()]

            bank_items = [
                item
                for item in bank_items
                if self.item_matches_filter(item, parameters) or item.code in processed_food_codes or item.code in unprocessed_food_codes
            ]

        items = sorted(bank_items, key=lambda i: (-i.level, i.code))
        withdrawal_stats = self.withdraw_table.get_all_stats()
        withdrawal_stats_map: Dict[str, datetime] = {item.item_code: item.last_withdrawn_at for item in withdrawal_stats}
        line_map: Dict[str, List[str]] = defaultdict(list)

        for item in items:
            item_code = escape_string(item.code)
            level = escape_string(format_level(item.level))
            if item.code in bank_reservations_map:
                reservations = escape_string(f' (+{bank_reservations_map[item.code]}x 🔒)')
                quantity = bank_items_map[item.code] - bank_reservations_map[item.code]
            else:
                reservations = ''
                quantity = bank_items_map[item.code]
            quantity_str = escape_string(f'{quantity}x')
            emoji = self.format_stale_items(item, withdrawal_stats_map)

            if item.code in processed_food_codes:
                item_type = 'food'
            elif item.code in unprocessed_food_codes:
                item_type = 'unprocessed food'
            else:
                item_type = str(item.type)
            line_map[item_type].append(f'{quantity_str} *{item_code}* {level}{reservations}{emoji}')

        lines: List[str] = []
        bank_details = self.service.get_bank_details()
        lines.append(f'🏦 Current Balance: *{escape_string(format_number(bank_details.gold))}*g')
        lines.append(
            f'Slots: {len(bank_items_map.keys())}/*{bank_details.slots}* \\| '
            f'Next: *{escape_string(format_number(bank_details.next_expansion_cost))}*g'
        )
        lines.append('')

        for item_type, item_str in sorted(line_map.items()):
            lines.append(f'*{escape_string(item_type)}*')
            lines.extend(item_str)
            lines.append('')

        self.send_message(lines)

    def handle_ge_command(self, parameters: List[str]):
        ge_sell_orders: List[GEOrderSchema] = self.service.get_ge_sell_orders()
        sorted_orders = sorted(ge_sell_orders, key=lambda order: order.code)
        grouped_orders = {key: list(group) for key, group in groupby(sorted_orders, key=lambda order: order.code)}

        all_character_details = self.service.get_all_character_details()
        bank_items_map = self.service.get_bank_items_map()
        all_task_items: Dict[str, int] = defaultdict(int)
        for c in all_character_details:
            if c.task_type == 'items' and c.current_task.task_remaining > 0:
                recipe = self.service.resolve_item_recipe(c.task, bank_items_map, c.task_total - c.task_progress)
                for code, qty in recipe.missing_items.items():
                    all_task_items[code] += qty

        line_map: Dict[str, List[str]] = defaultdict(list)
        for item_code, orders in grouped_orders.items():
            item = self.service.get_item(item_code)
            if len(parameters) == 0 or self.item_matches_filter(item, parameters):
                orders_str, below_threshold = self.format_sell_orders(orders)
                emoji = self.format(below_threshold, item, all_task_items)
                line_map[str(item.type)].append(
                    f'{sum(o.quantity for o in orders)}x *{escape_string(item_code)}* {orders_str}{escape_string(emoji)}'
                )

        lines: List[str] = []
        bank_details = self.service.get_bank_details()
        lines.append(f'🏦 Current Balance: *{escape_string(format_number(bank_details.gold))}*g')
        lines.append('')

        for item_type, item_str in sorted(line_map.items()):
            lines.append(f'*{escape_string(item_type)}*')
            lines.extend(item_str)
            lines.append('')

        self.send_message(lines)

    def handle_char_command(self, parameters: List[str]):
        characters: List[CharacterSchemaExtension] = self.service.get_characters_by_param(parameters)
        if len(characters) == 0:
            self.telegram_client.send_notification('Please specify at least one character or use "all" parameter.')

        lines: List[str] = []
        for character in characters:
            lines.append(f'*{escape_string(character.name)}*')
            lines.append(f'HP: {character.hp}/{character.max_hp}')
            lines.append(f'Weapon: {escape_string(character.weapon_slot)}')
            lines.append(f'Shield: {escape_string(character.shield_slot)}')
            lines.append(f'Helmet: {escape_string(character.helmet_slot)}')
            lines.append(f'Body Armor: {escape_string(character.body_armor_slot)}')
            lines.append(f'Leg Armor: {escape_string(character.leg_armor_slot)}')
            lines.append(f'Boots: {escape_string(character.boots_slot)}')
            rings = []
            if character.ring1_slot:
                rings.append(escape_string(character.ring1_slot))
            if character.ring2_slot:
                rings.append(escape_string(character.ring2_slot))
            if len(rings) == 2 and rings[0] == rings[1]:
                rings = [f'{rings[0]} {escape_string("(2x)")}']
            lines.append(f'Rings: {", ".join(rings)}')
            lines.append(f'Amulet: {escape_string(character.amulet_slot)}')
            lines.append(f'Rune: {escape_string(character.rune_slot)}')
            artifacts = []
            if character.artifact1_slot:
                artifacts.append(escape_string(character.artifact1_slot))
            if character.artifact2_slot:
                artifacts.append(escape_string(character.artifact2_slot))
            if character.artifact3_slot:
                artifacts.append(escape_string(character.artifact3_slot))
            lines.append(f'Artifacts: {", ".join(artifacts)}')
            lines.append(f'Bag: {escape_string(character.bag_slot)}')
            if character.utility1_slot:
                lines.append(escape_string(f'Utility 1: {character.utility1_slot} ({character.utility1_slot_quantity}x)'))
            if character.utility2_slot:
                lines.append(escape_string(f'Utility 2: {character.utility2_slot} ({character.utility2_slot_quantity}x)'))
            lines.append('')

            lines.append('*Stats*')
            lines.append(f'Wisdom: {character.wisdom}')
            lines.append(f'Prospecting: {character.prospecting}')
            lines.append('')

            inventory_quantity = sum(i.quantity for i in character.inventory)
            inventory_count = escape_string(f'({inventory_quantity}/{character.inventory_max_items})')
            lines.append(f'*Inventory* {inventory_count}')
            for inventory in character.inventory:
                if inventory.code:
                    lines.append(escape_string(f'{inventory.code} ({inventory.quantity}x)'))

            lines.append('')
            lines.append('*Skills*')
            if character.level < game_constants.MAX_LEVEL:
                lines.append(escape_string(f'Combat: {character.level} ({character.xp}/{character.max_xp})'))
            else:
                lines.append(escape_string(f'Combat: {character.level}'))

            for skill in game_constants.SKILLS:
                lines.append(escape_string(self.format_skill_level(character, skill)))
            lines.append('')
            lines.append('*Task*')
            if character.current_task.task:
                lines.append(escape_string(f'Type: {character.current_task.task_type}'))
                lines.append(escape_string(f'Target: {character.current_task.task}'))
                lines.append(escape_string(f'Progress: {character.current_task.task_progress}/{character.current_task.task_total}'))
            else:
                lines.append(escape_string('Currently no active task.'))
            lines.append('')
            lines.append('*Position*')
            map_tile = self.service.get_map_by_id(character.map_id)
            lines.append(
                escape_string(
                    f'{map_tile.layer}, {map_tile.x}, {map_tile.y} ({map_tile.name}, {
                        map_tile.interactions.content.code if map_tile.interactions.content else ""
                    })'
                )
            )
            lines.append('')
            now = datetime.now(UTC).replace(microsecond=0)
            cooldown: timedelta = character.cooldown_expiration.replace(microsecond=0) - now
            if cooldown.total_seconds() > 0:
                lines.append('*Cooldown*')
                time = self.telegram_client.format_time_at_user_timezone(character.cooldown_expiration)
                lines.append(f'⏱️ {cooldown} @ {time}')
                lines.append('')

        self.send_message(lines)

    def handle_clear_command(self, parameters: List[str]):
        characters: List[CharacterSchemaExtension] = self.service.get_characters_by_param(parameters)
        if not characters:
            self.telegram_client.send_notification('Please specify at least one character or use "all" parameter.')
        else:
            self.service.delete_bank_reservations(character_list=characters)
            msg = f'Cleared Bank Reservations of {list_to_string([c.name for c in characters], "*")}'
            self.telegram_client.send_notification(msg, parse_mode=ParseMode.MARKDOWN_V2)

    def handle_level_command(self, parameters: List[str]):
        characters: List[CharacterSchemaExtension] = self.service.get_all_character_details()

        lines: List[str] = [
            '```',
            f'{"".ljust(12)}{"1".rjust(2)}   {"2".rjust(2)}   {"3".rjust(2)}   {"4".rjust(2)}   {"5".rjust(2)}',
            f'{"Level".ljust(12)}{str(characters[0].level).rjust(2)} | {str(characters[1].level).rjust(2)} | {str(characters[2].level).rjust(2)} | {str(characters[3].level).rjust(2)} | {str(characters[4].level).rjust(2)}',
            f'{"Mining".ljust(12)}{str(characters[0].mining_level).rjust(2)} | {str(characters[1].mining_level).rjust(2)} | {str(characters[2].mining_level).rjust(2)} | {str(characters[3].mining_level).rjust(2)} | {str(characters[4].mining_level).rjust(2)}',
            f'{"Woodcutting".ljust(12)}{str(characters[0].woodcutting_level).rjust(2)} | {str(characters[1].woodcutting_level).rjust(2)} | {str(characters[2].woodcutting_level).rjust(2)} | {str(characters[3].woodcutting_level).rjust(2)} | {str(characters[4].woodcutting_level).rjust(2)}',
            f'{"Fishing".ljust(12)}{str(characters[0].fishing_level).rjust(2)} | {str(characters[1].fishing_level).rjust(2)} | {str(characters[2].fishing_level).rjust(2)} | {str(characters[3].fishing_level).rjust(2)} | {str(characters[4].fishing_level).rjust(2)}',
            f'{"Cooking".ljust(12)}{str(characters[0].cooking_level).rjust(2)} | {str(characters[1].cooking_level).rjust(2)} | {str(characters[2].cooking_level).rjust(2)} | {str(characters[3].cooking_level).rjust(2)} | {str(characters[4].cooking_level).rjust(2)}',
            f'{"Alchemy".ljust(12)}{str(characters[0].alchemy_level).rjust(2)} | {str(characters[1].alchemy_level).rjust(2)} | {str(characters[2].alchemy_level).rjust(2)} | {str(characters[3].alchemy_level).rjust(2)} | {str(characters[4].alchemy_level).rjust(2)}',
            f'{"Weaponcraf.".ljust(12)}{str(characters[0].weaponcrafting_level).rjust(2)} | {str(characters[1].weaponcrafting_level).rjust(2)} | {str(characters[2].weaponcrafting_level).rjust(2)} | {str(characters[3].weaponcrafting_level).rjust(2)} | {str(characters[4].weaponcrafting_level).rjust(2)}',
            f'{"Gearcrafti.".ljust(12)}{str(characters[0].gearcrafting_level).rjust(2)} | {str(characters[1].gearcrafting_level).rjust(2)} | {str(characters[2].gearcrafting_level).rjust(2)} | {str(characters[3].gearcrafting_level).rjust(2)} | {str(characters[4].gearcrafting_level).rjust(2)}',
            f'{"Jewelrycra.".ljust(12)}{str(characters[0].jewelrycrafting_level).rjust(2)} | {str(characters[1].jewelrycrafting_level).rjust(2)} | {str(characters[2].jewelrycrafting_level).rjust(2)} | {str(characters[3].jewelrycrafting_level).rjust(2)} | {str(characters[4].jewelrycrafting_level).rjust(2)}',
            '```',
        ]

        self.send_message(lines)

    def handle_follow_command(self, parameters: List[str], subscription_type: str = 'follow'):
        characters: List[CharacterSchemaExtension] = self.service.get_characters_by_param(parameters)
        if not characters:
            self.telegram_client.send_notification('Please specify at least one character or use "all" parameter.')

        minutes = 5
        for parameter in parameters:
            if self.is_numeric(parameter):
                number = int(parameter)
                if number < 0:
                    minutes = abs(number)

        character_list: List[str] = []
        if subscription_type != 'follow':
            self.telegram_client.unpin_all_messages()
        for character in characters:
            self.follower_service.add_follower_subscription(character.name, minutes, subscription_type)
            character_list.append(character.name)

        if character_list:
            action = 'Following' if subscription_type == 'follow' else 'Monitoring'
            message = (
                f'🔍 {action} {list_to_string(character_list, fmt="*")} for {minutes} minutes until *'
                f'{escape_string(self.telegram_client.format_time_at_user_timezone(datetime.now(UTC) + timedelta(minutes=minutes)))}*\\.'
            )
            self.telegram_client.send_notification(message, parse_mode='MarkdownV2')

    def handle_solve_command(self, parameters: List[str]):
        characters: List[CharacterSchemaExtension] = self.service.get_characters_by_param(parameters)
        if not characters:
            self.telegram_client.send_notification('Please specify at least one character or use "all" parameter.')

        count = 1
        for parameter in parameters:
            if self.is_numeric(parameter):
                number = int(parameter)
                if number < 0:
                    count = abs(number)

        character_list: List[str] = []
        for character in characters:
            self.dispatcher_queue.solve_tasks(character.name, count)
            character_list.append(character.name)

        if character_list:
            message = f'⚜️ Dispatched {list_to_string(character_list, fmt="*")} to solve tasks {escape_string(f"({count}x).")}'
            self.telegram_client.send_notification(message, parse_mode='MarkdownV2')

    def handle_patch_command(self, parameters: List[str]):
        characters: List[CharacterSchemaExtension] = self.service.get_characters_by_param(parameters)
        if not characters:
            self.telegram_client.send_notification('Please specify at least one character or use "all" parameter.')

        character_list: List[str] = []
        for character in characters:
            params = [param for param in parameters if '=' in param]
            character_list.append(character.name)
            task = Task.from_kwargs(params)

            quest_id = Quest.generate_quest_id()
            active_quest = self.character_table.get_quest(character.name)
            self.dispatch_service.dispatch(
                task_list=[task],
                quest_id=quest_id,
                is_new_quest_id=True,
                character=character,
                skip_pre_tasks=True,
                skip_post_tasks=False,
                active_quest=active_quest,
            )

        if character_list:
            message = f'✂️ Patched {list_to_string(character_list, fmt="*")}\\.'
            self.telegram_client.send_notification(message, parse_mode='MarkdownV2')

    def handle_deliver_command(self, parameters: List[str]):
        characters: List[CharacterSchemaExtension] = self.service.get_characters_by_param(parameters)
        if not characters:
            self.telegram_client.send_notification('Please specify at least one character or use "all" parameter.')

        character_list: List[str] = []
        for character in characters:
            self.dispatcher_queue.deliver_food_tasks(character.name)
            character_list.append(character.name)
            break

        if character_list:
            message = f'🍱 Dispatched {list_to_string(character_list, fmt="*")} to deliver food\\.'
            self.telegram_client.send_notification(message, parse_mode='MarkdownV2')

    def handle_tasks_command(self, parameters: List[str], skip_done: bool = False, skip_next: bool = False):
        characters: List[CharacterSchemaExtension] = self.service.get_characters_by_param(parameters)
        if not characters:
            self.telegram_client.send_notification('Please specify at least one character or use "all" parameter.')

        lines: List[str] = []
        now = datetime.now(UTC).replace(microsecond=0)
        for character in characters:
            if character.cooldown_expiration > now:
                etc: timedelta = character.cooldown_expiration.replace(microsecond=0) - now
                time = self.telegram_client.format_time_at_user_timezone(character.cooldown_expiration)
                cooldown_str = f' ⏱️ {etc} @ {time}'
            else:
                cooldown_str = ''

            lines.append(f'*{escape_string(character.name)}*{escape_string(cooldown_str)}')
            active_quest = self.character_table.get_quest(character.name)
            if not active_quest:
                lines.append('No active quest\\.')
            else:
                current_task_id: Optional[str] = None
                for task in active_quest.tasks:
                    task_description = self.__describe_task(task)

                    until_str = ''
                    if task.until:
                        if task.until.date_time:
                            etc: timedelta = task.until.date_time.replace(microsecond=0) - now
                            time = self.telegram_client.format_time_at_user_timezone(task.until.date_time)
                            until_str = f' ⏱️ {etc} @ {time}'
                        until_str += f' [{task.until.status}]'

                    task_id_str = escape_string(f' [{task.task_id}]') if task.task_id else ''
                    escaped_description = escape_string(f' {task_description}') if task_description else ''
                    escaped_description += escape_string(until_str)
                    if (not skip_done or task.ttl > 0) and (not skip_next or not current_task_id or task.task_id == current_task_id):
                        if not current_task_id and task.task_id:
                            current_task_id = task.task_id
                        lines.append(f'└ {"☑️ " if task.ttl == 0 else ""}*{escape_string(task.action)}*{task_id_str}{escaped_description}')

            if len(characters) > 1:
                lines.append('')

        if lines:
            self.send_message(lines)

    def handle_reservations_command(self, parameters: List[str]):
        characters: List[CharacterSchemaExtension] = self.service.get_characters_by_param(parameters)
        if not characters:
            characters = self.service.get_all_character_details()

        lines: List[str] = ['*🔒 Bank Reservations*']

        bank_reservations = self.service.get_bank_reservations()
        grouped_reservations: Dict[str, List[BankReservation]] = defaultdict(list)
        for bank_reservation in bank_reservations:
            grouped_reservations[bank_reservation.character].append(bank_reservation)

        if grouped_reservations:
            lines.append('')

            for character in characters:
                character_reservations = grouped_reservations.pop(character.name, [])
                if len(character_reservations):
                    lines.append(f'*{escape_string(character.name)}*')
                    for character_reservation in character_reservations:
                        lines.append(
                            f' └ {character_reservation.quantity}x {escape_string(character_reservation.item_code)}, '
                            f'{character_reservation.task_id}'
                        )

                    if grouped_reservations:
                        lines.append('')

            for character_reservation_list in grouped_reservations.values():
                for character_reservation in character_reservation_list:
                    lines.append(
                        f' └ {character_reservation.quantity}x {escape_string(character_reservation.item_code)}, {character_reservation.task_id}'
                    )
        else:
            lines.append('Currently no reservations\\.')

        if len(lines) > 1:
            self.send_message(lines)

    def handle_pending_command(self, parameters: List[str]):

        lines: List[str] = ['*🎁 Pending Items*']
        pending_items: List[PendingItemSchema] = self.service.get_pending_items()
        if pending_items:
            for pending_item in pending_items:
                parts = []
                if pending_item.gold:
                    parts.append(f'{pending_item.gold} gold')
                parts.extend(f'{pi.quantity}x {pi.code}' for pi in pending_item.items)
                parts_str = ', '.join(parts)
                line = f'From _{escape_string(pending_item.description)}_: *{escape_string(parts_str)}*'
                lines.append(line)
                lines.append(f'ID: {pending_item.id}')
                lines.append('')
        else:
            lines.append('Currently no pending items to claim\\.')

        if len(lines) > 1:
            self.send_message(lines)

    def handle_test_command(self, parameters: List[str]):
        lines: List[str] = []

        static_files = StaticFiles()
        lines.append(f'Maps: {len(static_files.read_file("maps").get("data"))}')
        lines.append(f'Items: {len(static_files.read_file("items").get("data"))}')
        lines.append(f'Monsters: {len(static_files.read_file("monsters").get("data"))}')

        if len(lines) > 1:
            self.send_message(lines)

    def handle_tools_command(self, parameters: List[str]):
        lines: List[str] = ['🧰 *Tools*']

        global_quantity_map = self.service.get_global_quantity_map()

        for skill in GATHERING_SKILLS:
            lines.append('')
            lines.append(f'*{escape_string(skill.capitalize())}*')
            tools = self.service.get_tools(skill)
            for tool in tools:
                lines.append(escape_string(f' └ {tool.code} ({tool.level}): {global_quantity_map.get(tool.code, 0)}x'))

        if len(lines) > 1:
            self.send_message(lines)

    @staticmethod
    def item_matches_filter(item: ItemSchemaExtension, parameters: List[str]):
        for parameter in parameters:
            if parameter == 'food':
                parameter = 'consumable'
            elif parameter == 'potion':
                parameter = 'utility'
            elif parameter == 'task':
                if item.subtype and parameter.startswith(item.subtype):
                    return True
                parameter = 'currency'
            if item.type and parameter.startswith(item.type):
                return True
        return False

    @staticmethod
    def format_skill_level(character: CharacterSchemaExtension, skill: str) -> str:
        skill_obj = character.skills[skill]
        if 1 < skill_obj.level < game_constants.MAX_LEVEL:
            return f'{skill.capitalize()}: {skill_obj.level} ({skill_obj.xp}/{skill_obj.max_xp})'
        else:
            return f'{skill.capitalize()}: {skill_obj.level}'

    def handle_buy_command(self, parameters: List[str]):
        quantity: Optional[int] = None
        item_code: Optional[str] = None
        order_id: Optional[str] = None

        for parameter in parameters:
            if self.is_numeric(parameter):
                quantity = int(parameter)
            else:
                item = self.service.get_item(parameter)
                if item:
                    item_code = item.code
                else:
                    order = self.service.get_ge_order(parameter)
                    if order:
                        order_id = order.id

        if item_code and not order_id and quantity is None:
            quantity = 1

        basket = ShoppingBasket(quantity, item_code, order_id)
        self.dispatcher_queue.buy(basket)

    def handle_buys_command(self, parameters: List[str]):
        lines: List[str] = ['🙋‍♂️ *Buy Orders*']
        buy_orders = self.service.get_ge_buy_orders()

        if not buy_orders:
            lines.append('Currently no buy orders\\.')
        else:
            bank_items_map = self.service.get_bank_items_map()
            global_quantity_map = self.service.get_global_quantity_map(bank_items_map=bank_items_map)

            for buy_order in buy_orders:
                bank_qty = bank_items_map.get(buy_order.code, 0)
                bank_str = f' ({bank_qty} at bank).' if bank_qty > 0 else '.'
                prefix = '◉' if bank_qty > 0 else '○'

                line = (
                    f'{prefix} {buy_order.id}: {buy_order.quantity}x {buy_order.code} for {format_long_number(buy_order.price)}g each. '
                    f'You have {global_quantity_map.get(buy_order.code, 0)}{bank_str}'
                )
                lines.append(escape_string(line))
        if lines:
            self.send_message(lines)

    def handle_fill_command(self, parameters: List[str]):
        characters: List[CharacterSchemaExtension] = self.service.get_characters_by_param(parameters)

        buy_orders = self.service.get_ge_buy_orders()
        all_buy_order_ids = [order.id for order in buy_orders]
        buy_order_ids = set()

        for parameter in parameters:
            if parameter in all_buy_order_ids:
                buy_order_ids.add(parameter)

        if characters and buy_order_ids:
            filtered_buy_orders = [order for order in buy_orders if order.id in buy_order_ids]
            buy_order_str = [f'{o.id} ({o.quantity}x {o.code} for {o.price}g each)' for o in filtered_buy_orders]
            character = next(c for c in characters)
            buy_orders_str = ', '.join(buy_order_str)
            message = f'{character.name} will fill order(s) {buy_orders_str}'

            fill_tasks = [Task.fill_order(order.id) for order in filtered_buy_orders]

            quest_id = Quest.generate_quest_id()
            active_quest = self.character_table.get_quest(character.name)
            self.dispatch_service.dispatch(
                task_list=fill_tasks,
                quest_id=quest_id,
                is_new_quest_id=True,
                character=character,
                skip_pre_tasks=True,
                skip_post_tasks=True,
                active_quest=active_quest,
            )

        else:
            message = 'Could not determine buy order ID and character.'

        self.telegram_client.send_notification(message)

    def handle_resolve_command(self, parameters: List[str]):
        quantity = 1
        items: List[ItemSchemaExtension] = []
        for parameter in parameters:
            if self.is_numeric(parameter):
                quantity = int(parameter)
            else:
                i = self.service.get_item(parameter.replace("'", ''))
                if i:
                    items.append(i)

        lines: List[str] = []
        if items:
            global_quantity_map = self.service.get_global_quantity_map()

            resolved_recipes: List[ResolvedItemRecipeDetails] = []
            for item in items:
                if quantity < 0:
                    global_quantity = global_quantity_map.get(item.code, 0)
                    item_quantity = abs(quantity) - global_quantity
                else:
                    item_quantity = quantity

                if item_quantity > 0:
                    resolved_recipe = self.service.resolve_item_recipe(item.code, global_quantity_map, item_quantity, read_only=False)
                    resolved_recipes.append(ResolvedItemRecipeDetails(item.code, item_quantity, resolved_recipe))

            combined_resolved_recipe = ResolvedItemRecipe(defaultdict(int), defaultdict(int), {})
            quantity_item_pairs: List[str] = []
            items_to_craft: List[str] = []
            for recipe in resolved_recipes:
                quantity_item_pairs.append(f'{recipe.quantity}x *{escape_string(recipe.code)}*')
                items_to_craft.append(recipe.code)
                for code, qty in recipe.resolved_recipe.available_items.items():
                    combined_resolved_recipe.available_items[code] += qty

                for code, qty in recipe.resolved_recipe.missing_items.items():
                    combined_resolved_recipe.missing_items[code] += qty

            if len(resolved_recipes) > 0:
                lines.extend([f'Resolved recipe for {list_to_string(quantity_item_pairs)}', ''])

                if len(combined_resolved_recipe.available_items) > 0:
                    lines.append('*Available parts*')
                for part_code, part_quantity in combined_resolved_recipe.available_items.items():
                    global_qty = global_quantity_map.get(part_code, 0) + part_quantity
                    lines.append(escape_string(f'{part_code}: {part_quantity} ({global_qty}){" ❕" if part_quantity == global_qty else ""}'))

                if len(lines) > 2:
                    lines.append('')

                if combined_resolved_recipe.missing_items:
                    lines.append('*Missing parts*')
                for part_code, part_quantity in combined_resolved_recipe.missing_items.items():
                    origin = self.service.get_item_origin(part_code)
                    if origin.is_task_exclusive():
                        item_icon = ' ⚜️'
                    elif origin.is_npc_exclusive():
                        item_icon = ' 🧑‍🌾'
                    elif origin.is_event_exclusive() and origin.is_boss_exclusive():
                        item_icon = ' ⚡️🐲'
                    elif origin.is_event_exclusive():
                        item_icon = ' ⚡️'
                    elif origin.is_boss_exclusive():
                        item_icon = ' 🐲'
                    else:
                        item_icon = ''

                    lines.append(escape_string(f'{part_code}: {part_quantity}{item_icon}'))

                lines.append('')
                all_character_details = self.service.get_all_character_details()
                for item in items:
                    if item.code in items_to_craft and item.craft:
                        required_skill = str(item.craft.skill)
                        required_skill_level = item.craft.level
                        can_craft: List[str] = []
                        for character in all_character_details:
                            if character.skills[required_skill].level >= required_skill_level:
                                can_craft.append(character.name)
                        if len(can_craft) > 0:
                            lines.append(f'*{escape_string(item.code)}* can be crafted by {list_to_string(can_craft, fmt="*")} ✅')
                        else:
                            lines.append(
                                f'*{escape_string(item.code)}* requires *{escape_string(required_skill)}* '
                                f'level *{escape_string(str(required_skill_level))}*'
                            )
                    elif item.is_npc_item:
                        npc_list = [n.code for n in self.service.get_npcs_by_item_code(item.code)]
                        lines.append(f'*{escape_string(item.code)}* needs to be traded with {list_to_string(npc_list, fmt="*")} ✅')

            else:
                lines.append('No further items to craft\\.')
        else:
            lines.append('No valid items provided\\.')

        self.send_message(lines)

    @staticmethod
    def is_numeric(parameter: str):
        try:
            int(parameter)
            return True
        except ValueError:
            return False

    @staticmethod
    def format_sell_orders(orders: List[GEOrderSchema]) -> Tuple[str, bool]:
        order_map: Dict[int, int] = defaultdict(int)
        for order in orders:
            order_map[order.price] += order.quantity
        sorted_orders = sorted(order_map.items())
        lowest_price, lowest_quantity = sorted_orders[0]
        if len(sorted_orders) > 1:
            highest_price, highest_quantity = sorted_orders[-1]
            result = escape_string(f'[{format_number(lowest_price)}g: {lowest_quantity}x, {format_number(highest_price)}g: {highest_quantity}x]')
        else:
            result = escape_string(f'[{format_number(lowest_price)}g]')
        return result, lowest_price <= game_constants.GE_RECYCLING_THRESHOLD

    @staticmethod
    def format(below_threshold: bool, item: ItemSchemaExtension, all_task_items: Dict[str, int]):
        if below_threshold and item.is_recyclable:
            return ' ♻️'
        elif item.code in all_task_items:
            return f' ⚜️ ({all_task_items[item.code]}x)'
        else:
            return ''

    @staticmethod
    def format_stale_items(item: ItemSchemaExtension, withdrawal_stats_map: Dict[str, datetime]):
        last_withdrawn_at: Optional[datetime] = withdrawal_stats_map.get(item.code)
        if not last_withdrawn_at or (last_withdrawn_at + timedelta(days=3)) > datetime.now(UTC):
            return ''
        else:
            stale_icon = ' ♻️' if item.is_recyclable else ' 🕸️'
            suffices = []
            if 'prospecting' in item.item_effects:
                suffices.append('🔵')
            if 'wisdom' in item.item_effects:
                suffices.append('🟣')
            stale_icon = stale_icon + ' ' + ''.join(suffices)
            return stale_icon

    def handle_achievement_command(self, parameters: List[str]):
        achievement_codes: Set[str] = set()
        for parameter in parameters:
            if not self.is_numeric(parameter):
                achievement_codes.add(parameter)

        bank_items_map = self.service.get_bank_items_map()

        lines: List[str] = ['🥇 *Achievement descriptions*', '']
        for achievement in self.service.get_account_achievements():
            if achievement.code not in achievement_codes:
                continue

            event_required = self.__is_event_required(achievement, bank_items_map)
            achievement_format = ' ⚡️' if event_required else ''
            lines.append(f'*{escape_string(achievement.name)}* {escape_string(f"({achievement.code}){achievement_format}")}')
            lines.append(escape_string(achievement.description))

            for objective in achievement.objectives:
                lines.append(
                    f'└ Progress {escape_string(objective.target)}: {objective.progress}/{objective.total} '
                    f'{"✅ " if objective.progress == objective.total else ""}'
                )

            rewards = [
                f'{achievement.points} achievement {"points" if achievement.points > 1 else "point"}',
                f'{achievement.rewards.gold} gold',
            ]
            if achievement.rewards.items:
                for item in achievement.rewards.items:
                    rewards.append(f'{item.quantity}x {item.code}')
            lines.append(f'{escape_string(f"Rewards: {", ".join(rewards)}")}')
            lines.append('')

        if lines:
            self.send_message(lines)

    def handle_achievements_command(self, categories: List[str]):
        player_name = next((c[1:] for c in categories if c.startswith('@')), None)

        if player_name:
            categories = [c for c in categories if not c.startswith('@')]
        else:
            player_name = self.account_name

        achievements: List[AccountAchievementSchemaExtension] = self.service.get_account_achievements(player_name)
        achievements_by_type: Dict[str, List[AccountAchievementSchemaExtension]] = defaultdict(list)
        bank_items_map = self.service.get_bank_items_map(ignore_reservations=True)

        points_achieved = 0
        points_total = 0
        for achievement in achievements:
            if (not categories or achievement.type in categories) and not achievement.completed_at:
                achievements_by_type[str(achievement.type)].append(achievement)
            points_total += achievement.points
            if achievement.completed_at:
                points_achieved += achievement.points

        for ach_type in achievements_by_type:
            achievements_by_type[ach_type].sort(key=lambda x: (-x.total_progress, x.points))

        title = '*Achievements Progress*'
        subtitle = escape_string(f'{player_name} ({points_achieved}/{points_total})')

        lines: List[str] = [title, subtitle, '']
        lines.extend(self.service.format_achievement_process(achievements_by_type, bank_items_map))

        if len(lines) > 1:
            self.send_message(lines)

    def handle_leaderboard_command(self, parameters: List[str]):
        # account_details: MyAccountDetails = self.service.get_account_details()
        account_leaderboard: List[AccountLeaderboardSchema] = self.service.get_account_leaderboard()
        lines: List[str] = ['*Leaderboard*']
        rankings = ['🥇', '🥈', '🥉'] + [f' {i}. ' for i in range(4, 10)] + ['10.']
        account_found = False
        for rank, account in zip(rankings, account_leaderboard[:10]):
            line = escape_string(f'{rank} {account.account}: {account.achievements_points} pts, {format_number(account.gold)}g')
            if account.account == self.account_name:
                lines.append('*' + line + '*')
                account_found = True
            else:
                lines.append(line)

        if not account_found:
            for account in account_leaderboard[10:]:
                if account.account == self.account_name:
                    line = escape_string(
                        f'{account.position}. {account.account}: {account.achievements_points} pts, {format_number(account.gold)}g'
                    )
                    if account.position > 11:
                        lines.append(escape_string('...'))
                    lines.append('*' + line + '*')
                    break

        if len(lines) > 1:
            self.send_message(lines)

    def handle_item_command(self, parameters: List[str]):
        bank_items_map = self.service.get_bank_items_map(ignore_reservations=True)
        bank_reservations_map = self.service.get_bank_reservations_map()
        all_character_details = self.service.get_all_character_details()
        all_characters_inventory_map = self.service.get_all_characters_inventory_map(all_character_details)
        global_quantity_map = self.service.get_global_quantity_map(
            bank_items_map=bank_items_map, all_characters_inventory_map=all_characters_inventory_map
        )
        skill_map = self.service.get_skill_map(all_character_details)

        quantity = 1
        items: List[ItemSchemaExtension] = []
        for parameter in parameters:
            if self.is_numeric(parameter):
                quantity = int(parameter)
            else:
                i = self.service.get_item(parameter)
                if i:
                    items.append(i)

        account_achievements = self.service.get_account_achievements()
        account_achievements_map = defaultdict(list)
        rewards_map = defaultdict(list)
        for achievement in account_achievements:
            for objective in achievement.objectives:
                account_achievements_map[objective.target].append(achievement)
            if achievement.rewards and achievement.rewards.items:
                for reward in achievement.rewards.items:
                    rewards_map[reward.code].append(achievement)

        lines: List[str] = []
        for item in items:
            lines.append(f'📦 *{escape_string(item.name)}* {escape_string(f"({item.code}, {item.level})")}')
            parts = [item.type, item.subtype] if item.subtype else [item.type]
            lines.append(', '.join(escape_string(p) for p in parts))

            if item.craft:
                lines.append('')
                lines.append(f'*Parts* {escape_string(f"({item.craft.skill}, {item.craft.level})")}')
                for craft in item.craft.items:
                    required_quantity = craft.quantity * quantity

                    if craft.code in bank_reservations_map:
                        reservations = escape_string(f' (+{bank_reservations_map[craft.code]}x 🔒)')
                        bank_quantity = max(bank_items_map.get(craft.code, 0) - bank_reservations_map[craft.code], 0)
                    else:
                        reservations = ''
                        bank_quantity = bank_items_map.get(craft.code, 0)

                    lines.append(f' ∟ {required_quantity}x {escape_string(craft.code + " |")} {bank_quantity}x{reservations}')

            lines.append('')
            lines.append('*Availability*')
            if item.code in bank_reservations_map:
                reservations = escape_string(f' (+{bank_reservations_map[item.code]}x 🔒)')
                bank_quantity = max(bank_items_map.get(item.code, 0) - bank_reservations_map[item.code], 0)
            else:
                reservations = ''
                bank_quantity = bank_items_map.get(item.code, 0)
            lines.append(f' ∟ Bank: {bank_quantity}x{reservations}')
            for character in all_character_details:
                equip_count = 0
                for slot, code in character.equipment.items():
                    if code == item.code:
                        if slot.startswith('utility'):
                            equip_count += character.utilities.get(item.code, 0)
                        else:
                            equip_count += 1

                if item.code in character.equipment.values():
                    lines.append(escape_string(f' ∟ {character.name}: {equip_count}x (equipped)'))

                inventory_count = character.inventory_map.get(item.code, 0)
                if inventory_count > 0:
                    lines.append(escape_string(f' ∟ {character.name}: {inventory_count}x (inventory)'))

            filtered_sell_orders = self.service.get_ge_sell_orders(item.code)
            if filtered_sell_orders:
                orders_str, below_threshold = self.format_sell_orders(filtered_sell_orders)
                lines.append(f' ∟ GE: {sum(o.quantity for o in filtered_sell_orders)}x{orders_str}')

            if item.craft or item.is_npc_item:
                craftable_qty = self.service.get_craftable_recipe_count(item.code, global_quantity_map)
                craftable_str = f' ∟ Craftable: {craftable_qty}x'
                if not craftable_qty:
                    recipe = self.service.resolve_item_recipe(item_code=item.code, bank_items_map=global_quantity_map, quantity=1)
                    if recipe:
                        craftable_str += escape_string(f' (Missing: {format_dict(recipe.missing_items)})')

                if item.craft:
                    required_skill = str(item.craft.skill)
                    skill_level = skill_map.get(required_skill, 1)
                    if item.craft.level > skill_level:
                        craftable_str += escape_string(f' ⚠️ {required_skill.lower()} level {item.craft.level} not met.')

                lines.append(craftable_str)

            origin = self.service.get_item_origin(item.code)
            if origin and (origin.resources or origin.monsters or origin.tasks):
                lines.append('')
                lines.append('*Origin*')

                if origin.resources:
                    lines.extend(
                        escape_string(f' ∟ {code} ({item_drop.drop_rate}{" ⚡" if item_drop.is_event else ""})')
                        for code, item_drop in origin.resources.items()
                    )
                if origin.monsters:
                    lines.extend(
                        escape_string(f' ∟ {code} ({item_drop.drop_rate}{" ⚡" if item_drop.is_event else ""})')
                        for code, item_drop in origin.monsters.items()
                    )
                if origin.tasks:
                    lines.extend(escape_string(f' ∟ tasks_master ({item_drop.drop_rate})') for item_drop in origin.tasks)

            products = self.service.get_item_products(item.code)
            if products:
                lines.append('')
                lines.append('*Products*')
                for product in products:
                    lines.append(escape_string(f' ∟ {product.code} {format_level(product.level)}'))

            if item.item_effects:
                lines.append('')
                lines.append('*Effects*')
                for effect_name, effect_value in item.item_effects.items():
                    lines.append(escape_string(f' ∟ {effect_name}: {effect_value}'))

            npcs = self.service.get_npcs_by_item_code(item.code)
            if npcs:
                lines.append('')
                lines.append('*Market*')

            for npc in npcs:
                lines.append(f' └ {escape_string(f"{npc.code}{' ⚡' if npc.is_event_npc else ''}")}')
                npc_item = npc.items[item.code]
                if npc_item.buy_price is not None:
                    if npc_item.currency == 'gold':
                        lines.append(escape_string(f' └─ 🛒 Buy for {format_number(npc_item.buy_price)}g'))
                    else:
                        lines.append(escape_string(f' └─ 🛒 Exchange for {format_number(npc_item.buy_price)} {npc_item.currency}'))
                if npc_item.sell_price is not None:
                    lines.append(escape_string(f' └─ 💰 Sell for {format_number(npc_item.sell_price)}g'))

            if item.code in account_achievements_map:
                lines.append('')
                lines.append('*Achievements*')
                achievements = account_achievements_map[item.code]
                for achievement in achievements:
                    progress = ''
                    if achievement.completed_at:
                        progress = ' ✅'
                    else:
                        for objective in achievement.objectives:
                            if objective.target == item.code:
                                if objective.progress == objective.total:
                                    progress = ' ☑️'
                                else:
                                    progress = escape_string(f' ({objective.progress}/{objective.total})')
                                break
                    lines.append(f' ∟ {escape_string(achievement.code)}{progress}')

            if item.code in rewards_map:
                lines.append('')
                lines.append('*Rewards*')
                achievements = rewards_map[item.code]
                for achievement in achievements:
                    reward_quantity = escape_string(f'({sum(i.quantity for i in achievement.rewards.items if i.code == item.code)}x)')
                    progress = ' ✅' if achievement.completed_at else ''
                    lines.append(f' ∟ {escape_string(achievement.code)} {reward_quantity}{progress}')

            if item.type == ItemType.SHIELD:
                lines.append('')
                lines.append('*Affinity*')

                for monster in self.service.get_all_monsters():
                    all_elements = False
                    for element, element_attack in monster.attack_elem.items():
                        if element_attack > 0:
                            if item.item_effects.get(f'res_{element}', 0) > 0:
                                all_elements = True
                            else:
                                all_elements = False
                                break

                    if all_elements:
                        lines.append(f' ∟ {escape_string(monster.code)}')

            if len(items) > 1:
                lines.append('')

        if lines:
            self.send_message(lines)

    def handle_compare_command(self, parameters: List[str]):

        items: List[ItemSchemaExtension] = []
        for parameter in parameters:
            if not self.is_numeric(parameter):
                i = self.service.get_item(parameter)
                if i:
                    items.append(i)

        shared_effects = set.intersection(*(set(item.item_effects.keys()) for item in items if item.item_effects))

        lines: List[str] = []
        items_str = ', '.join(i.code for i in items)
        lines.append(f'🧮 Comparing {escape_string(items_str)}')
        lines.append('')
        for item in items:
            if item.item_effects:
                lines.append(f'*{escape_string(item.code)}*')
                for effect_name, effect_value in item.item_effects.items():
                    prefix = '◉' if effect_name in shared_effects else '○'
                    lines.append(escape_string(f' {prefix} {effect_name}: {effect_value}'))

            if len(items) > 1:
                lines.append('')

        if lines:
            self.send_message(lines)

    def handle_monster_command(self, parameters: List[str]):
        monsters: List[MonsterSchemaExtension] = []
        for parameter in parameters:
            if not self.is_numeric(parameter):
                i = self.service.get_monster(parameter)
                if i:
                    monsters.append(i)

        lines: List[str] = []

        account_achievements = self.service.get_account_achievements()
        account_achievements_map = defaultdict(list)
        for achievement in account_achievements:
            for objective in achievement.objectives:
                account_achievements_map[objective.target].append(achievement)

        for monster in monsters:
            lines.append(
                f'*{escape_string(monster.name)}* {
                    escape_string(
                        f"({monster.code}, {monster.level}{' ⚡' if monster.is_event_monster else ''}{' 🐲' if monster.is_boss_monster else ''})"
                    )
                }'
            )

            lines.append('')
            lines.append('*Drops*')
            lines.append(escape_string(f' ∟ gold: {monster.min_gold}-{monster.max_gold}g'))
            for drop in monster.drops:
                if drop.min_quantity != drop.max_quantity:
                    lines.append(escape_string(f' ∟ {drop.code}: {drop.rate} ({drop.min_quantity}-{drop.max_quantity})'))
                else:
                    lines.append(escape_string(f' ∟ {drop.code}: {drop.rate} ({drop.min_quantity})'))

            lines.append('')
            lines.append('*Stats*')
            lines.append(escape_string(f' ∟ hp: {monster.hp}'))
            for attack_elem, attack_elem_value in monster.attack_elem.items():
                if attack_elem_value > 0:
                    lines.append(escape_string(f' ∟ attack_{attack_elem}: {attack_elem_value}'))
            lines.append(escape_string(f' ∟ critical_strike: {monster.critical_strike}'))

            for res_elem, res_elem_value in monster.res_elem.items():
                if res_elem_value != 0:
                    lines.append(escape_string(f' ∟ res_{res_elem}: {res_elem_value}'))

            if monster.effect:
                lines.append('')
                lines.append('*Effects*')
                for effect_name, effect_value in monster.effect.items():
                    lines.append(escape_string(f' ∟ {effect_name}: {effect_value}'))

            if monster.code in account_achievements_map:
                lines.append('')
                lines.append('*Achievements*')
                achievements = account_achievements_map[monster.code]
                for achievement in achievements:
                    lines.append(f' ∟ {escape_string(achievement.code)}')

            if len(monsters) > 1:
                lines.append('')

        if lines:
            self.send_message(lines)

    def handle_npc_command(self, parameters: List[str]):
        npcs: List[NPCSchemaExtension] = []
        for parameter in parameters:
            if not self.is_numeric(parameter):
                i = self.service.get_npc(parameter)
                if i:
                    npcs.append(i)

        lines: List[str] = []
        for npc in npcs:
            lines.append(f'🧑‍🌾 *{escape_string(npc.name)}* {escape_string(f"({npc.code}{' ⚡' if npc.is_event_npc else ''})")}')

            lines.append('')
            lines.append('*Items*')
            for npc_item in npc.items.values():
                buysell_strings: List[str] = []
                if npc_item.buy_price is not None:
                    if npc_item.currency == 'gold':
                        buysell_strings.append(f'🛒 Buy for {format_number(npc_item.buy_price)}g')
                    else:
                        buysell_strings.append(f'🛒 Exchange for {format_number(npc_item.buy_price)} {npc_item.currency}')
                if npc_item.sell_price is not None:
                    buysell_strings.append(f'💰 Sell for {format_number(npc_item.sell_price)}g')

                lines.append(escape_string(f' ∟ {npc_item.code}: {", ".join(buysell_strings)}'))

            if len(npcs) > 1:
                lines.append('')

        if lines:
            self.send_message(lines)

    def handle_matrix_command(self, parameters: List[str]):
        min_monster_level = 1
        for parameter in parameters:
            if self.is_numeric(parameter):
                min_monster_level = abs(int(parameter))
                break
        self.report.print_fight_matrix(
            min_monster_level=min_monster_level,
            print_console=False,
            send_message=True,
            skip_boss_monsters=True,
        )

    def __describe_task(self, task: Task):
        if task.kind == 'action':
            action_task_description = self.action_processor.describe_task(task)
            return f'{task.ttl}x {action_task_description}' if task.ttl > 1 else action_task_description
        elif task.kind == 'template':
            return self.template_processor.describe_task(task)
        else:
            return 'No description available'

    def __is_event_required(self, achievement: AccountAchievementSchemaExtension, bank_items_map: Dict[str, int]):
        return any(self.__is_event_required_objective(o, bank_items_map) for o in achievement.objectives)

    def __is_event_required_objective(self, objective: AccountAchievementObjectiveSchema, bank_items_map: Dict[str, int]):
        result = False
        match objective.type:
            case AchievementType.COMBAT_DROP:
                origin = self.service.get_item_origin(objective.target)
                result = origin.is_event_exclusive()
            case AchievementType.COMBAT_KILL:
                monster = self.service.get_monster(objective.target)
                result = monster.is_event_monster
            case AchievementType.CRAFTING:
                resolved_recipe = self.service.resolve_item_recipe(
                    item_code=objective.target,
                    bank_items_map=bank_items_map,
                    quantity=objective.total - objective.progress,
                )
                for item_code in resolved_recipe.missing_items:
                    item_origin = self.service.get_item_origin(item_code)
                    if item_origin.is_event_exclusive():
                        result = True
                        break
            case AchievementType.GATHERING:
                origin = self.service.get_item_origin(objective.target)
                result = origin.is_event_exclusive()
            case AchievementType.USE:
                resolved_recipe = self.service.resolve_item_recipe(
                    item_code=objective.target,
                    bank_items_map=bank_items_map,
                    quantity=objective.total - objective.progress,
                )
                for item_code in resolved_recipe.missing_items:
                    item_origin = self.service.get_item_origin(item_code)
                    if item_origin.is_event_exclusive():
                        result = True
                        break

        return result

    def send_message(self, lines: List[str]):
        if lines:
            messages: List[str] = []
            message = ''
            for line in lines:
                if len(message + '\n' + line) > 3000:
                    messages.append(message)
                    message = ''
                message += line + '\n'

            if message:
                messages.append(message)

            for m in messages:
                self.telegram_client.send_notification(m, parse_mode=ParseMode.MARKDOWN_V2)


telegram_function = TelegramFunction()


@event_source(data_class=SQSEvent)
def handler(event: SQSEvent, context: LambdaContext):
    telegram_function.handler(event, context)


if __name__ == '__main__':
    telegram_function.handler()
