from copy import copy
from datetime import datetime, UTC
from math import ceil
from typing import Dict, List, Tuple

from telegram.constants import ParseMode

from artifactsmmo.actions.action_result import ActionResult
from artifactsmmo.actions.action_strategy import ActionStrategy
from artifactsmmo.client.actions import ActionsClient
from artifactsmmo.dynamodb.character_table import CharacterTable
from artifactsmmo.dynamodb.counters_table import CountersTable
from artifactsmmo.dynamodb.equipment_lock_table import EquipmentLockTable
from artifactsmmo.dynamodb.skill_stats_table import SkillStatsTable
from artifactsmmo.dynamodb.task_progress_table import TaskProgressTable
from artifactsmmo.extensions import CharacterSchemaExtension, ItemSchemaExtension, MonsterSchemaExtension
from artifactsmmo.fights.equipment_assembler import EquipmentAssembler
from artifactsmmo.game_constants import SUPPRESS_DROP_CODES
from artifactsmmo.log.logger import logger
from artifactsmmo.models import LogType, MapSchema
from artifactsmmo.service.execution_context import ExecutionContext
from artifactsmmo.service.fight_simulator import FightSimulator
from artifactsmmo.service.food_service import FoodService
from artifactsmmo.service.helpers import escape_string, get_next_move
from artifactsmmo.service.service import Service
from artifactsmmo.service.tasks import Task
from artifactsmmo.service.until import Status, Until
from artifactsmmo.telegram.client import TelegramClient


class FightAction(ActionStrategy):
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
        self.fight_simulator = FightSimulator(service)
        self.equipment_lock_table = EquipmentLockTable()
        self.equipment_assembler = EquipmentAssembler(service)
        self.risky_biscuit_factor = 3

    def action(self) -> str:
        return 'fight'

    @staticmethod
    def describe_task(task: Task) -> str:
        if task.until:
            if task.until.drop_item:
                return f'{task.extra.get("monster")} for {task.until.drop_item} ({task.until.progress}/{task.until.drop_count})'
            elif task.until.achievement_code:
                return f'{task.extra.get("monster")} to solve achievement {task.until.achievement_code}'
        return f'{task.extra.get("monster")}'

    def process(self, character: CharacterSchemaExtension, task: Task, quest_id: str = None, context: ExecutionContext = None) -> ActionResult:
        action_result = ActionResult()
        monster_code = task.extra['monster']
        required_hp = int(task.extra.get('required_hp') or 0)
        expected_win_rate = float(task.extra.get('expected_win_rate') or 0.0)
        is_force_fight = bool(task.extra.get('force_fight'))
        utilities: Dict[str, int] = task.extra.get('utilities') or {}
        current_map = self.service.get_map_by_id(character.map_id)

        if task.extra.get('expected_win_rate') is None:
            logger.warning('Parameter expected_win_rate is missing. Assuming 100%')
            expected_win_rate = 100

        if not character.equipment['weapon'] and not is_force_fight:
            message = 'No weapon equipped, aborting.'
            logger.error(message)
            action_result.abort(message)
            return action_result

        monster = self.service.get_monster(monster_code) if monster_code else None
        is_risky_biscuit, additional_hp_required = self.is_risky_biscuit(character, monster, required_hp, expected_win_rate)
        if character.hp < character.max_hp and is_risky_biscuit:
            heal_to_hp_or_max_hp = min(required_hp + additional_hp_required, character.max_hp)
            self.add_recovery_action(character, heal_to_hp_or_max_hp, action_result, task, monster, context, current_map)

            if is_risky_biscuit and additional_hp_required > 0:
                new_required_hp = additional_hp_required + required_hp
                logger.info(
                    f'Character {character.name} updated required_hp from {required_hp} to {new_required_hp}/{character.max_hp} against monster {monster_code}.'
                )
                task.extra['required_hp'] = new_required_hp
        else:
            if current_map.interactions.content or monster_code in current_map.event_content.values():
                if not monster_code and current_map.interactions.content.type == 'monster':
                    monster_code = current_map.interactions.content.code
                    logger.warning(f'Set monster_code={monster_code}')

                if monster and (
                    current_map.interactions.content
                    and current_map.interactions.content.code != monster.code
                    and monster.code not in current_map.event_content.values()
                ):
                    message = f'Expected monster code {monster.code} but got {current_map.interactions.content.code} at x={current_map.x}, y={current_map.y}'
                    logger.error(message)
                    action_result.abort(message)
                else:
                    utilities_ensured = self.check_utilities(monster_code, character, utilities)
                    if utilities_ensured:
                        self.conduct_fight(character, monster, action_result, task, expected_win_rate, required_hp, current_map, is_force_fight)
                    else:
                        self.handle_insufficient_utilities(character, monster_code, action_result, utilities, task)
            else:
                self.handle_empty_map(character, action_result)

        return action_result

    @staticmethod
    def check_utilities(monster_code, character, utilities) -> bool:
        result = True
        for idx, (item_code, quantity) in enumerate(utilities.items(), 1):
            currently_equipped_item = getattr(character, f'utility{idx}_slot')
            currently_equipped_quantity = getattr(character, f'utility{idx}_slot_quantity', 0)
            if currently_equipped_quantity < quantity or currently_equipped_item != item_code:
                result = False
                logger.info(
                    f'Utilities are not ensured against monster={monster_code}: utility={item_code}, '
                    f'slot={idx}, required={quantity}, equipped={currently_equipped_quantity}'
                )
        return result

    def conduct_fight(
        self,
        character: CharacterSchemaExtension,
        monster: MonsterSchemaExtension,
        action_result: ActionResult,
        task: Task,
        expected_win_rate: float,
        required_hp: int,
        current_map: MapSchema,
        is_force_fight: bool,
    ):
        status_code, result, error = self.actions_client.fight(character)

        match status_code:
            case 200:
                if character.utility1_slot_quantity - result.characters[0].utility1_slot_quantity > 0:
                    self.counters_table.increment(
                        character.utility1_slot,
                        'utilities',
                        character.utility1_slot_quantity - result.characters[0].utility1_slot_quantity,
                    )

                if character.utility2_slot_quantity - result.characters[0].utility2_slot_quantity > 0:
                    self.counters_table.increment(
                        character.utility2_slot,
                        'utilities',
                        character.utility2_slot_quantity - result.characters[0].utility2_slot_quantity,
                    )

                turns = result.fight.turns
                fight_result = result.fight.result
                fought_monster_code = result.fight.opponent
                if fight_result != 'win':
                    self.counters_table.increment(fought_monster_code, 'deaths')
                    if not is_force_fight:
                        self.telegram_client.send_notification(
                            escape_string(f'☠️ {character.name} lost fight against {fought_monster_code}'),
                            parse_mode=ParseMode.MARKDOWN_V2,
                        )

                    base_str = (
                        f'Character {character.name} lost fight against {fought_monster_code} after {turns} turns. '
                        f'Expected win_rate={expected_win_rate:.3f}, required_hp={required_hp}, '
                        f'hp_before_fight={character.hp}/{character.max_hp}, equipment={character.equipment}, '
                        f'logs={result.fight.logs}, '
                    )

                    new_required_hp = character.max_hp
                    if character.hp < character.max_hp:
                        monster = self.service.get_monster(fought_monster_code)
                        combat_result = self.fight_simulator.test_exact_config(
                            character=character,
                            monster=monster,
                            hp=character.hp,
                        )
                        base_str += f'simulated fight with hp={character.hp}: win_rate={combat_result.raw_result.win_rate:.3f}'
                        if combat_result:
                            new_required_hp = combat_result.raw_result.max_required_hp

                    if expected_win_rate == 100.0 and character.hp == character.max_hp:
                        logger.error(base_str + ', next_action=This seems to be a bug in the fight-simulator, aborting.')
                        action_result.abort()
                        self.telegram_client.send_notification(
                            f'🛑 {character.name} lost fight against {fought_monster_code} after {turns} turns. '
                            f'Expected win_rate={expected_win_rate}, required_hp={required_hp}, '
                            f'hp_before_fight={character.hp}/{character.max_hp}. This seems to be a bug, check logs for additional details.'
                        )
                    elif expected_win_rate > 0:
                        logger.info(
                            f'{base_str}, next_action=Plan to move back to ({character.x}, {character.y}) and repeat fight. '
                            f'New required_hp={new_required_hp}'
                        )
                        reloaded_character = self.service.get_character_details(character.name)
                        action_result.append(Task.move(map_id=character.map_id))
                        action_result.update_character(character=reloaded_character)
                        task.extra['required_hp'] = new_required_hp
                        action_result.repeat()
                    else:
                        logger.info(
                            f'{character.name} lost fight against {fought_monster_code}, will not try again because expected_win_rate={expected_win_rate}'
                        )

                else:
                    logger.debug('Fight result against monster=%s: %s after %d turns.', fought_monster_code, fight_result, turns)

                    received_xp = result.fight.characters[0].xp
                    if received_xp is not None and result.characters[0] and character:
                        self.skill_stats_table.put_skill_stats(
                            action=LogType.FIGHT,
                            skill='fight',
                            level=character.level,
                            subject=fought_monster_code,
                            gained_xp=received_xp,
                            cooldown=result.characters[0].cooldown,
                            subject_level=monster.level,
                            wisdom=character.wisdom,
                        )

                        previous_level = character.level
                        current_level = result.characters[0].level
                        if current_level != previous_level:
                            self.telegram_client.send_notification(
                                f'🆙 *{escape_string(character.name)}* levelled up to level *{current_level}*\\.',
                                parse_mode='MarkdownV2',
                            )

                    self.counters_table.increment(fought_monster_code, 'monsters', duration=result.cooldown.total_seconds)
                    drop_rates: Dict[str, int] = {drop.code: drop.rate for drop in monster.drops}
                    for character_result in result.fight.characters:
                        for drop in character_result.drops:
                            self.counters_table.increment(drop.code, f'drops.monsters.{fought_monster_code}', drop.quantity)
                            action_result.drops[drop.code] += drop.quantity

                            if result.fight.turns > 3 and drop_rates[drop.code] >= 50 and drop.code not in SUPPRESS_DROP_CODES:
                                self.telegram_client.send_notification(
                                    f'💎 *{escape_string(character_result.character_name)}* '
                                    f'collected {drop.quantity} *{escape_string(drop.code)}*\\.',
                                    parse_mode='MarkdownV2',
                                )
                if monster.code != fought_monster_code:
                    message = f'Unexpected monster code: {fought_monster_code} != {monster.code}, aborting.'
                    logger.error(message)
                    action_result.abort(message)
            case 497:
                logger.info('Character inventory is full. Adding tasks to deposit current inventory at bank and return to this location.')
                next_move = get_next_move(current_map, monster.is_event_monster)
                action_result.append(Task.ensure_inventory(keep_consumables=True, task_id=task.task_id, next_move=next_move, deposit_gold=False))
                action_result.repeat()

            case 499:  # The character is in cooldown.
                msg = error.get('message', '')
                character_cooldown = msg if msg else 'The character is in cooldown.'
                logger.info(f'{character_cooldown} Fetching current character again.')
                reloaded_character = self.service.get_character_details(character.name)
                action_result.update_character(reloaded_character)
                action_result.repeat()

            case 598:  # Monster not found on this map.
                reloaded_character = self.service.get_character_details(character.name)
                action_result.update_character(reloaded_character)
                dt_str = 'None'
                if task.until and task.until.date_time:
                    dt_str = f'{task.until.date_time}: {datetime.now(UTC).replace(microsecond=0) - task.until.date_time} ago.'

                message = (
                    f'Monster {monster.code} (event_monster={monster.is_event_monster}) not found on this map. '
                    f'Character expected to stand at x={character.x}, y={character.y}. '
                    f'Character stands at x={reloaded_character.x}, y={reloaded_character.y}, '
                    f'until.date_time={dt_str}'
                    f'Aborting.'
                )
                logger.error(message)
                action_result.abort(message)

            case _:
                logger.error(f'Unexpected response: {error}')
                action_result.abort(f'{task.action}: {error}')

        if result and result.characters:
            action_result.update_character(result.characters[0])

    def handle_insufficient_utilities(
        self,
        character: CharacterSchemaExtension,
        monster_code: str,
        action_result: ActionResult,
        utilities: Dict[str, int],
        task: Task,
    ):
        bank_item_map = self.service.get_bank_items_map(task_id=task.task_id, character_name=character.name)
        resupply_tasks: List[Task] = []

        max_ttl = self.calculate_max_ttl_until(task.ttl, task.until)
        equipped_utilities: Dict[str, int] = character.utilities
        available_utilities = self.calculate_available_utilities(utilities, bank_item_map, equipped_utilities)
        min_qty, unavailable_items = self.calculate_min_quantity(utilities, available_utilities)
        affordable_fights = min(max_ttl, min_qty)
        logger.debug(f'affordable_fights={affordable_fights}, max_ttl={max_ttl}, min_qty={min_qty}, unavailable_items={unavailable_items}')

        task_id = Task.generate_task_id() if task.task_id is None else task.task_id
        if affordable_fights > 0:
            for idx, (item_code, utility_quantity) in enumerate(utilities.items(), 1):
                utility_slot = f'utility{idx}'
                required_quantity = utility_quantity * affordable_fights
                currently_equipped_utility = getattr(character, f'{utility_slot}_slot')
                currently_equipped_quantity = getattr(character, f'{utility_slot}_slot_quantity', 0)
                logger.info(
                    f'slot={utility_slot}, '
                    f'currently_equipped_utility={currently_equipped_utility}, '
                    f'currently_equipped_quantity={currently_equipped_quantity}, '
                    f'required_utility={item_code}, required_quantity={required_quantity}, '
                    f'affordable_fights={affordable_fights}, max_ttl={max_ttl}, min_qty={min_qty}'
                )
                if currently_equipped_quantity < required_quantity:
                    missing_quantity = required_quantity - currently_equipped_quantity
                    resupply_task = Task.equip_utility(item_code, utility_slot, missing_quantity, task_id=task_id)
                    resupply_tasks.append(resupply_task)
                    self.service.add_bank_reservation(task_id, item_code, missing_quantity, character.name)

        if resupply_tasks and not unavailable_items:
            action_result.extend(resupply_tasks)
            action_result.append(Task.move(map_id=character.map_id))
            logger.info(f'Plan resupply run, move to map_id={character.map_id} and repeat fight.')
            action_result.repeat()
        else:
            action_result.append(Task.unequip_utilities())
            if monster_code:
                new_until = copy(task.until)
                if new_until:
                    new_until.status = Status.Todo
                new_ttl = copy(task.ttl)

                fight_monster_task = Task.fight_monster(
                    task_id=task_id,
                    reservation_id=task_id,
                    monster=monster_code,
                    until=new_until,
                    exclude_items=unavailable_items,
                    ttl=new_ttl,
                    map_id=character.map_id,
                )

                logger.info(
                    f'Added template to fight against monster={monster_code} without using '
                    f'items={unavailable_items}, task={fight_monster_task.to_dict()}'
                )
                action_result.append(fight_monster_task)

                # if task.until and task.until.date_time: # in this case, date_time wasn't set, hence task wasn't skipped
                action_result.skip()  # FIXME: Does this work?
            else:
                message = (
                    f'Character={character.name} cannot fight monster={monster_code} anymore, '
                    f'required_utilities={utilities}, unavailable_utilities={unavailable_items}, '
                    f'resupply_tasks={len(resupply_tasks)}. Abort.'
                )
                logger.warning(message)
                action_result.abort(message)

    def handle_empty_map(self, character: CharacterSchemaExtension, action_result: ActionResult):
        reloaded_character = self.service.get_character_details(character.name)
        if reloaded_character.map_id != character.map_id:
            logger.info(f'Character does not stand at x={character.x}, y={character.y} anymore. Add task to move there (again).')
            action_result.append(Task.move(map_id=character.map_id))
            action_result.update_character(character=reloaded_character)
            action_result.repeat()
        else:
            message = f'No monsters found at ({character.layer}/{character.x}/{character.y}).'
            logger.error(message)
            action_result.abort(message)

    def calculate_max_ttl_until(self, ttl: int, until: Until = None) -> int:
        if until:
            if until.date_time:
                return int((until.date_time - datetime.now(UTC)).total_seconds()) // 30
            elif until.drop_count is not None and until.progress is not None:
                remaining_qty = until.drop_count - until.progress
                if remaining_qty > 0:
                    drop_rates = self.service.get_drop_rate(item_code=until.drop_item)
                    for drop_rate in drop_rates:
                        if drop_rate.item_code == until.drop_item:
                            return drop_rate.drop_rate_min * remaining_qty
                else:
                    return 0
        else:
            return ttl
        return 1

    @staticmethod
    def calculate_available_utilities(
        utilities: Dict[str, int], bank_item_map: Dict[str, int], equipped_utilities: Dict[str, int]
    ) -> Dict[str, int]:
        result_map: Dict[str, int] = {}
        for required_utility in utilities.keys():
            result_map[required_utility] = bank_item_map.get(required_utility, 0) + equipped_utilities.get(required_utility, 0)
        return result_map

    @staticmethod
    def calculate_min_quantity(utilities: Dict[str, int], available_utilities: Dict[str, int]) -> Tuple[int, List[str]]:
        quantities: List[int] = []
        missing_utilities: List[str] = []
        for utility_code, utility_quantity in utilities.items():
            utility_min_quantity = min(available_utilities[utility_code], 100) // utility_quantity
            quantities.append(utility_min_quantity)
            if utility_min_quantity == 0:
                missing_utilities.append(utility_code)
        return min(quantities), missing_utilities

    def add_recovery_action(
        self,
        character: CharacterSchemaExtension,
        required_hp: int,  # heal up to at least this amount of HP
        action_result: ActionResult,
        task: Task,
        monster: MonsterSchemaExtension,
        context: ExecutionContext,
        current_map: MapSchema,
    ):
        eligible_consumables: List[ItemSchemaExtension] = self.service.get_processed_food_by_level(character.level)
        food_items = [i.code for i in eligible_consumables]

        consumable_map = self.food_service.get_best_food_to_consume(character, required_hp, is_event_monster=monster.is_event_monster)
        should_rest = True
        should_resupply = False

        if consumable_map:
            for food_code, food_quantity in consumable_map.items():
                use_item_task_id = Task.generate_task_id()
                action_result.append(Task.use_item(item=food_code, quantity=food_quantity, task_id=use_item_task_id))

            should_rest = False
        elif not any(item_code in food_items for item_code in character.inventory_map):
            should_resupply = True

        logger.info(
            f'Result of finding best consumables to ensure current_hp={character.hp} >= '
            f'required_hp={required_hp}, max_hp={character.max_hp}, character_inventory={character.inventory_map}: '
            f'consumable_map={consumable_map}, should_rest={should_rest}, should_resupply={should_resupply}, ttl={task.ttl}, '
            f'character.inventory_keys={character.inventory_map.keys()}, '
            f'carrying food={any(item_code in food_items for item_code in character.inventory_map)}'
        )

        if should_resupply:
            lock_acquired = self.equipment_lock_table.acquire_lock(character.name)
            if lock_acquired:
                fight_times = self.service.estimate_fight_times(task, task.ttl, monster, character)
                consumable_map = self.food_service.get_best_food_to_withdraw(
                    character=character,
                    required_hp=required_hp,
                    lost_hps_per_fight=[required_hp],
                    fight_times=fight_times,
                    is_event_monster=monster.is_event_monster,
                    is_boss_monster=monster.is_boss_monster,
                    task_id=task.task_id,
                    context=context,
                )
                logger.info(
                    f'Lock acquired: {character.name}, food_service.get_suitable_consumables_from_bank(): consumable_map={consumable_map}'
                )

                if consumable_map:
                    resupply_faster = self.is_resupplying_faster_than_resting(task, monster, required_hp, character)
                    if resupply_faster:
                        reservation_id = self.service.reserve_equipment(
                            character=character,
                            consumables=consumable_map,
                            reservation_id=task.task_id,
                        )

                        next_move = get_next_move(current_map, monster.is_event_monster)
                        action_result.append(
                            Task.ensure_inventory(
                                item_map=consumable_map,
                                keep_consumables=True,
                                task_id=reservation_id,
                                next_move=next_move,
                                deposit_gold=False,
                            )
                        )

                        logger.info(f'Added tasks to resupply consumable_map={consumable_map}')
                        should_rest = False
                    else:
                        logger.info('Resupplying is slower than just resting.')

                self.equipment_lock_table.release_lock(character.name)
            else:
                action_result.append(Task.sleep(seconds=3))

        if should_rest:
            action_result.append(Task.rest())
            logger.info(
                f'Insufficient HP remaining: required_hp={required_hp}, current_hp={character.hp}. Adding task to rest and repeat fight.'
            )

        if not task.until:
            action_result.repeat()
            logger.info(f'Set this task_id={task.task_id} to be repeated, current_ttl={task.ttl}, is_until_set={task.until is not None}')
            # what happens to a task with until=xy if we repeat the task?
            # Isn't it enough to add new steps and interrupt the current task?

    def is_risky_biscuit(
        self, character: CharacterSchemaExtension, monster: MonsterSchemaExtension, required_hp: int, expected_win_rate: float
    ) -> Tuple[bool, int]:
        if not monster or character.hp == character.max_hp:
            return False, 0

        if character.hp <= required_hp:
            return True, 0

        if character.hp <= required_hp * self.risky_biscuit_factor:
            character_stats = self.equipment_assembler.create_character_stats_from_equipment(character.level, list(character.equipment.values()))

            desired_win_rate = min(expected_win_rate, 99.99)

            low, high = required_hp, character.max_hp
            found_hp = None
            combat_cache = {}

            # Helper function to memoize simulations
            def simulate(hp: int) -> float:
                if hp not in combat_cache:
                    result = self.fight_simulator.test_exact_config(
                        monster=monster,
                        character_stats=character_stats,
                        utilities_list=list(character.utilities.keys()),
                        hp=hp,
                        rounds=1000,
                    )
                    combat_cache[hp] = result.raw_result.win_rate
                logger.info(f'Simulating fight result with hp={hp}, required_hp={required_hp}, win_rate={combat_cache[hp]}')
                return combat_cache[hp]

            # Binary search for minimal HP meeting desired win rate
            while low <= high:
                mid = (low + high) // 2
                win_rate = simulate(mid)

                if win_rate >= desired_win_rate:
                    found_hp = mid
                    high = mid - 1
                else:
                    low = mid + 1

            if found_hp is not None:
                if character.hp < found_hp:
                    current_result = self.fight_simulator.test_exact_config(
                        monster=monster,
                        character_stats=character_stats,
                        utilities_list=list(character.utilities.keys()),
                        hp=character.hp,
                    )
                    logger.info(
                        f'Current character_hp={character.hp}/{character.max_hp} is a risky biscuit 🍪 '
                        f'against monster={monster.code} with expected win_rate={current_result.raw_result.win_rate:.2f}. '
                        f'Initially required_hp={required_hp}, estimated_required_hp={found_hp}/{character.max_hp}, '
                        f'additional_hp_required={found_hp - required_hp} to have win_rate={combat_cache[found_hp]:.2f}, '
                        f'risky_biscuit_factor={character.hp / required_hp:.2f}, risky_biscuit_difference={character.hp - required_hp}'
                    )
                    return True, found_hp - required_hp
                else:
                    logger.info(
                        f'Current character_hp={character.hp}/{character.max_hp} is sufficient ☑️ '
                        f'to win fight against monster={monster.code}, '
                        f'required_hp={found_hp}, previously calculated required_hp={required_hp}, '
                        f'risky_biscuit_factor={character.hp / required_hp:.2f}, risky_biscuit_difference={character.hp - required_hp}'
                    )
                    return False, 0

            # No HP value met the win rate requirement
            logger.info(
                f'Current equipment and hp=({character.hp}/{character.max_hp}) does not seem to be sufficient '
                f'to win fight against monster={monster.code}. desired_win_rate={desired_win_rate}%, '
                f'best_win_rate={max(combat_cache.values()) if combat_cache else "N/A"}'
            )
            return True, min(0, character.max_hp - character.hp)

        return False, 0

    def is_resupplying_faster_than_resting(
        self, task: Task, monster: MonsterSchemaExtension, required_hp: int, character: CharacterSchemaExtension
    ) -> bool:
        fight_times = self.service.estimate_fight_times(task, task.ttl, monster, character)
        total_heal_required = fight_times * required_hp

        banks: List[MapSchema] = self.service.get_maps('bank')
        min_required_steps = 1000
        for bank in banks:
            x_steps = max(bank.x, character.x) - min(bank.x, character.x)
            y_steps = max(bank.y, character.y) - min(bank.y, character.y)
            total_steps = x_steps + y_steps
            if total_steps < min_required_steps:
                min_required_steps = total_steps

        resupply_seconds = min_required_steps * 5 + 3
        missing_hp_percent = (total_heal_required / character.max_hp) * 100
        rest_seconds = max(ceil(missing_hp_percent), 3) if missing_hp_percent > 0 else 0
        return resupply_seconds < rest_seconds
