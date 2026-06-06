from collections import Counter
from typing import Dict, List, Set

from telegram.constants import ParseMode

from artifactsmmo.actions.action_result import ActionResult
from artifactsmmo.actions.action_strategy import ActionStrategy
from artifactsmmo.client.actions import ActionsClient
from artifactsmmo.dynamodb.character_table import CharacterTable
from artifactsmmo.dynamodb.counters_table import CountersTable
from artifactsmmo.dynamodb.skill_stats_table import SkillStatsTable
from artifactsmmo.dynamodb.task_progress_table import TaskProgressTable
from artifactsmmo.extensions import CharacterSchemaExtension, MonsterSchemaExtension
from artifactsmmo.extensions.MapSchemaExtension import MapSchemaExtension
from artifactsmmo.log.logger import logger
from artifactsmmo.models import CharacterFightDataSchema
from artifactsmmo.service.execution_context import ExecutionContext
from artifactsmmo.service.food_service import FoodService
from artifactsmmo.service.helpers import escape_string
from artifactsmmo.service.service import Service
from artifactsmmo.service.tasks import Task
from artifactsmmo.telegram.client import TelegramClient


class MultiCharacterFightAction(ActionStrategy):
    def __init__(
        self,
        actions_client: ActionsClient,
        service: Service,
        counters_table: CountersTable,
        telegram_client: TelegramClient,
        task_progress_table: TaskProgressTable,
        skill_stats_table: SkillStatsTable,
        food_service: FoodService,
        character_table: CharacterTable,
    ):
        super().__init__(
            actions_client, service, counters_table, telegram_client, task_progress_table, skill_stats_table, food_service, character_table
        )
        self.spawn_map_id = service.get_map(0, 0).map_id

    def action(self) -> str:
        return 'multi-character-fight'

    @staticmethod
    def describe_task(task: Task) -> str:
        if task.until:
            if task.until.drop_item:
                return f'{task.extra.get("monster")} for {task.until.drop_item} ({task.until.progress}/{task.until.drop_count})'
            elif task.until.achievement_code:
                return f'{task.extra.get("monster")} to solve achievement {task.until.achievement_code}'
        return f'{task.extra.get("monster")}'

    def process(self, character: CharacterSchemaExtension, task: Task, quest_id: str = None, context: ExecutionContext = None) -> ActionResult:
        action_result: ActionResult = ActionResult()
        extra = task.extra
        monster_code = str(extra['monster'])
        monster = self.service.get_monster(monster_code)
        # required_hp = int(extra.get('required_hp') or 0)
        utilities: Dict[str, int] = extra.get('utilities', {})
        expected_win_rate = float(extra.get('expected_win_rate') or 0.0)
        utilities = utilities if utilities else {}

        leader = extra.get('leader') or character.name
        participants = extra.get('participants') or []

        if not monster_code:
            logger.error('Parameter monster_code is missing.')

        expected_map_id = extra.get('map_id')
        expected_map = self.service.get_map_by_id(expected_map_id)

        if utilities:
            expected_utilities = Counter(utilities.keys())
            equipped_utilities = Counter(character.utilities)

            if equipped_utilities < expected_utilities:
                logger.error(f'equipped utilities {dict(equipped_utilities)} is less than {dict(expected_utilities)}')
                action_result.abort(f'Required utilities ({dict(expected_utilities)}) are not provided.')
                return action_result

        if character.name == leader:
            self.__process_action_as_leader(character, leader, participants, monster, expected_map, action_result, expected_win_rate)
        elif character.name in participants:
            self.__process_action_as_participant(character, leader, monster_code, expected_map, action_result, task)
        else:
            logger.error(
                f'Role of character={character.name} in multi-character-fight against {monster_code} is unknown, '
                f'leader: {leader}, participants: {participants} '
            )
            action_result.abort(f'Role of character={character.name} in multi-character-fight against {monster_code} is unknown.')
        return action_result

    def __process_action_as_leader(
        self,
        character: CharacterSchemaExtension,
        leader: str,
        participants: List[str],
        monster: MonsterSchemaExtension,
        expected_map: MapSchemaExtension,
        action_result: ActionResult,
        expected_win_rate: float,
    ):
        characters: List[CharacterSchemaExtension] = []
        all_character_details = self.service.get_all_character_details()
        for fight_participant in all_character_details:
            if fight_participant.name == character.name:
                character = fight_participant
            if fight_participant.name == character.name or fight_participant.name in participants:
                characters.append(fight_participant)
        logger.info(f'Processing multi-character-fight as leader ({leader})')

        if character.map_id == self.spawn_map_id and character.hp == 1:
            self.__handle_character_at_spawn(expected_map, action_result)
        elif all(c.map_id == expected_map.map_id for c in characters):
            self.__all_characters_at_destination(character, characters, participants, monster, action_result, expected_win_rate)
        else:
            self.__not_all_characters_at_destination(characters, expected_map, action_result)

    def __all_characters_at_destination(
        self,
        character: CharacterSchemaExtension,
        characters: List[CharacterSchemaExtension],
        participants: List[str],
        monster: MonsterSchemaExtension,
        action_result: ActionResult,
        expected_win_rate: float,
    ):
        max_cooldown_seconds = max(c.get_remaining_cooldown() for c in characters)
        if max_cooldown_seconds < 1:
            if all(c.is_full_hp() for c in characters):
                self.__all_characters_full_hp(
                    character,
                    [c for c in characters if c.name in participants],
                    monster,
                    action_result,
                    expected_win_rate,
                )
            else:
                self.__not_all_characters_full_hp(characters, action_result)
        else:
            logger.info(f'Not all characters are ready yet. Sleeping for {max_cooldown_seconds} seconds.')
            action_result.append(Task.sleep(seconds=max_cooldown_seconds))
            action_result.repeat()

    def __not_all_characters_at_destination(
        self,
        characters: List[CharacterSchemaExtension],
        expected_map: MapSchemaExtension,
        action_result: ActionResult,
    ):
        distance_list: List[int] = []
        characters_enroute: List[bool] = []
        for fight_participant in characters:
            if fight_participant.map_id != expected_map.map_id:
                character_enroute = False
                character_map = self.service.get_map_by_id(fight_participant.map_id)
                distance = self.service.get_distance_between(current_map=character_map, destination_map=expected_map)
                distance_list.append(distance)

                participant_quest = self.character_table.get_quest(fight_participant.name)
                if participant_quest:
                    for task in participant_quest.tasks:
                        if task.ttl > 0 and task.action == 'multi-character-fight' and task.extra.get('map_id') == expected_map.map_id:
                            character_enroute = True
                            break
                characters_enroute.append(character_enroute)

        if len(characters_enroute) > 0 and not any(characters_enroute):
            message = 'Not all characters are on their way to the monster. Aborting.'
            logger.error(message)
            action_result.abort(message)
        else:
            distance_time = max(distance_list) * 5 if distance_list else 90
            logger.info(f'Not all characters are at expected map_id={expected_map.map_id} yet, sleeping {distance_time}s')
            action_result.append(Task.sleep(seconds=distance_time))
            action_result.repeat()

    def __process_action_as_participant(
        self,
        character: CharacterSchemaExtension,
        leader: str,
        monster_code: str,
        expected_map: MapSchemaExtension,
        action_result: ActionResult,
        task: Task,
    ):
        logger.info(f'Processing multi-character-fight as participant {character.name}')

        quest_leader = self.character_table.get_quest(leader)
        if quest_leader and quest_leader.status == f'boss-fight {monster_code}':
            reloaded_character = self.service.get_character_details(character.name)
            action_result.update_character(character=reloaded_character)
            character = action_result.character

            if character.map_id == self.spawn_map_id and character.hp == 1:
                self.__handle_character_at_spawn(expected_map, action_result)
            else:
                logger.info(
                    f'Participant {character.name} stands at map ({character.layer}, {character.x}, {character.y}) '
                    f'with map_id={character.map_id} (expected: {expected_map.map_id}) '
                    f'with {character.hp}/{character.max_hp} hp. Will sleep and await leader to command.'
                )
                action_result.append(Task.sleep(seconds=30))
                action_result.repeat()
        else:
            logger.info(
                f'Leader={leader} finished multi-character-fight against monster={monster_code}, '
                f'status={quest_leader.status if quest_leader else "None"}'
            )
            task.ttl = 0

    @staticmethod
    def __handle_character_at_spawn(expected_map: MapSchemaExtension, action_result: ActionResult):
        action_result.append(Task.move(map_id=expected_map.map_id))
        action_result.repeat()

    def __process_drops(
        self,
        result: CharacterFightDataSchema,
        monster: MonsterSchemaExtension,
        action_result: ActionResult,
    ):
        drop_rates: Dict[str, int] = {drop.code: drop.rate for drop in monster.drops}
        self.counters_table.increment(result.fight.opponent, 'monsters', len(result.fight.characters), duration=result.cooldown.total_seconds)
        for character in result.fight.characters:
            for drop in character.drops:
                self.counters_table.increment(drop.code, f'drops.monsters.{result.fight.opponent}', drop.quantity)
                action_result.drops[drop.code] += drop.quantity

                if drop_rates[drop.code] >= 50:
                    self.telegram_client.send_notification(
                        f'💎 *{escape_string(character.character_name)}* collected {drop.quantity} *{escape_string(drop.code)}*\\.',
                        parse_mode='MarkdownV2',
                    )

    def __all_characters_full_hp(
        self,
        character: CharacterSchemaExtension,
        participants: List[CharacterSchemaExtension],
        monster: MonsterSchemaExtension,
        action_result: ActionResult,
        expected_win_rate: float,
    ):
        logger.info("All character's HP are full.")
        status_code, result, error = self.actions_client.fight(character, participants)

        match status_code:
            case 200:
                logger.info(f'Fight result: status_code={status_code}, result={result.fight.result}')
                self.__process_drops(result, monster, action_result)

                if result.fight.result != 'win':
                    self.telegram_client.send_notification(
                        escape_string(f'☠️ {character.name} lost fight against {result.fight.opponent}'),
                        parse_mode=ParseMode.MARKDOWN_V2,
                    )

                    if expected_win_rate == 100:
                        action_result.abort('Lost a boss-fight with an expected win rate of 100%')
                else:
                    previous_characters = {c.name: c for c in [character, *participants]}
                    for c in result.characters:
                        if c.level != previous_characters[c.name].level:
                            self.telegram_client.send_notification(
                                f'🆙 *{escape_string(c.name)}* levelled up to level *{c.level}*\\.',
                                parse_mode='MarkdownV2',
                            )

            case 499:  # The character is in cooldown.
                msg = error.get('message', '')
                character_cooldown = msg if msg else 'The character is in cooldown.'
                logger.info(f'{character_cooldown} Fetching current character again.')
                reloaded_character = self.service.get_character_details(character.name)
                action_result.update_character(reloaded_character)
                action_result.repeat()

        if result and result.characters:
            action_result.update_character(result.characters[0])

    def __not_all_characters_full_hp(self, characters: List[CharacterSchemaExtension], action_result: ActionResult):
        cooldown_seconds: List[int] = []
        processed_food_codes: Set[str] = {f.code for f in self.service.get_processed_food()}

        injured_characters: List[CharacterSchemaExtension] = [c for c in characters if not c.is_full_hp()]
        if not injured_characters:
            logger.error('No injured characters found. This should have been caught higher up in the code logic.')
            return
        else:
            logger.info(f'Found injured characters: {[f"{c.name}: ({c.hp}/{c.max_hp})" for c in injured_characters]}')

        all_consumables: Counter[str] = Counter()
        for character in characters:
            for item_code, item_qty in character.inventory_map.items():
                if item_code in processed_food_codes:
                    all_consumables[item_code] += item_qty

        if not all_consumables:
            logger.info('No processed food found among all characters, all injured characters will rest.')
            for injured_character in injured_characters:
                status_code, result, error = self.actions_client.rest(injured_character)
                logger.info(f'Rest result for {injured_character.name}: status_code={status_code}. Cooldown: {result.cooldown.total_seconds}s')
                cooldown_seconds.append(result.cooldown.total_seconds)
            action_result.append(Task.sleep(seconds=max(cooldown_seconds)))
            action_result.repeat()
            return

        any_action = False
        already_acted: Set[CharacterSchemaExtension] = set()

        # --- STEP 1: Prioritize by absolute missing HP (descending) ---
        injured_characters.sort(key=lambda c: c.max_hp - c.hp, reverse=True)

        # --- STEP 2: Transfers ---
        needers = [c for c in injured_characters if not c.processed_food_count(processed_food_codes)]
        donors = sorted(
            [c for c in characters if c.processed_food_count(processed_food_codes)],
            key=lambda c: c.processed_food_count(processed_food_codes),
            reverse=True,
        )

        for receiver in needers:
            if not donors:  # no one to spare any processed food available
                logger.info(f'No available characters to give processed food to receiver={receiver.name}')
                break

            # pick a giver who hasn't acted yet
            giver = next((d for d in donors if d not in already_acted), None)
            if giver is None:
                logger.info(f"No characters that haven't acted yet to give processed food to receiver={receiver.name}")
                break

            # pick the giver’s best healing items
            consumable_map = self.food_service.get_best_food_to_consume(receiver, inventory_map=giver.inventory_map)
            logger.info(
                f'Determined best consumables to heal character={receiver.name} with consumables from the inventory of giver={giver.name}, consumable_map={consumable_map}'
            )

            if consumable_map:
                status_code, result, error = self.actions_client.give(giver, receiver, consumable_map)
                logger.info(f'Give result for {giver.name}: status_code={status_code}. Cooldown: {result.cooldown.total_seconds}s')
                cooldown_seconds.append(result.cooldown.total_seconds)

                any_action = True
                already_acted.add(giver)
                already_acted.add(receiver)  # receiver can’t act again this round
            else:
                logger.info(f'No consumables to transfer between giver={giver.name} and receiver={receiver.name}')

        # --- STEP 3: Eating phase ---
        for character in injured_characters:
            if character in already_acted:
                logger.info(f'Character={character.name} has already given or received items in this iteration.')
                continue  # skip those who gave or received this round
            if not character.processed_food_count(processed_food_codes):
                logger.info(f'Character={character.name} has no processed food to consume.')
                continue  # nothing to eat

            consumable_map = self.food_service.get_best_food_to_consume(character)
            if consumable_map:
                logger.info(f'Character {character.name} will consume first item of consumable_map={consumable_map} to heal.')
                for item_code, item_qty in consumable_map.items():
                    status_code, result, error = self.actions_client.use_item(character, item_code, item_qty)
                    if result:
                        logger.info(
                            f'Use item result for {character.name}: status_code={status_code}. '
                            f'Cooldown: {result.cooldown.total_seconds}s'
                        )
                        cooldown_seconds.append(result.cooldown.total_seconds)
                    break

                any_action = True
                already_acted.add(character)

        # --- STEP 4: Rest phase (only if no eating or giving happened) ---
        if not any_action:
            logger.info('No actions took place in this iteration, will rest for remainder of missing HP')
            for character in injured_characters:
                status_code, result, error = self.actions_client.rest(character)
                logger.info(f'Rest result for {character.name}: status_code={status_code}. Cooldown: {result.cooldown.total_seconds}s')
                cooldown_seconds.append(result.cooldown.total_seconds)
        action_result.append(Task.sleep(seconds=max(cooldown_seconds)))
        action_result.repeat()
