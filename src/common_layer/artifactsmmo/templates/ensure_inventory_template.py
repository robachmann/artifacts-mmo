from itertools import islice
from typing import Dict, List, Optional

from artifactsmmo.client.client import Client
from artifactsmmo.dynamodb.character_table import CharacterTable
from artifactsmmo.dynamodb.equipment_lock_table import EquipmentLockTable
from artifactsmmo.dynamodb.skill_stats_table import SkillStatsTable
from artifactsmmo.extensions import CharacterSchemaExtension
from artifactsmmo.extensions.MapSchemaExtension import MapSchemaExtension
from artifactsmmo.game_constants import SUCCESS_POSITION_ID
from artifactsmmo.log.logger import logger
from artifactsmmo.queue.dispatcher_queue import DispatcherQueue
from artifactsmmo.queue.worker_queue import WorkerQueue
from artifactsmmo.service.dispatch_service import DispatchService
from artifactsmmo.service.execution_context import ExecutionContext
from artifactsmmo.service.fight_simulator import FightSimulator
from artifactsmmo.service.food_service import FoodService
from artifactsmmo.service.helpers import format_dict
from artifactsmmo.service.service import Service
from artifactsmmo.service.tasks import Task
from artifactsmmo.telegram.client import TelegramClient
from artifactsmmo.templates.template_result import TemplateResult
from artifactsmmo.templates.template_strategy import TemplateStrategy


class EnsureInventoryTemplate(TemplateStrategy):
    def __init__(
        self,
        client: Client,
        service: Service,
        equipment_lock_table: EquipmentLockTable,
        telegram_client: TelegramClient,
        character_table: CharacterTable,
        skill_stats_table: SkillStatsTable,
        dispatch_service: DispatchService,
        dispatcher_queue: DispatcherQueue,
        worker_queue: WorkerQueue,
        food_service: FoodService,
        fight_simulator: FightSimulator,
    ):
        super().__init__(
            client,
            service,
            equipment_lock_table,
            telegram_client,
            character_table,
            skill_stats_table,
            dispatch_service,
            dispatcher_queue,
            worker_queue,
            food_service,
            fight_simulator,
        )
        self.consumable_codes: List[str] = [c.code for c in self.service.get_processed_food()]
        self.teleport_codes: List[str] = self.service.get_teleport_item_codes()

    def template(self) -> str:
        return 'ensure-inventory'

    @staticmethod
    def describe_task(task: Task) -> str:
        if task.extra.get('items'):
            return format_dict(task.extra.get('items'))
        else:
            return f'is empty{" and return" if task.extra.get("return_previous_position") else ""}'

    def render(self, character: CharacterSchemaExtension, task: Task, quest_id: str = None, context: ExecutionContext = None) -> TemplateResult:
        template_result: TemplateResult = TemplateResult()

        item_map = task.extra['items']
        keep_consumables = bool(task.extra['keep_consumables'])
        keep_teleport_items = bool(task.extra['keep_teleport_items'])
        return_previous_position = bool(task.extra['return_previous_position'])
        use_city_bank = bool(task.extra['use_city_bank'])
        deposit_gold = bool(task.extra['deposit_gold'])
        gold = task.extra['gold']
        next_target: Dict[str, str | int] = task.extra['next_move'] or {}
        keep_item_codes = task.extra['keep_items'] or []

        bank_items_map = self.service.get_bank_items_map(task_id=task.task_id, character_name=character.name)
        all_codes = set(item_map) | set(character.inventory_map)
        withdraw_items_map: Dict[str, int] = {}
        deposit_items_map: Dict[str, int] = {}

        for code in all_codes:
            desired = item_map.get(code, 0)
            have = character.inventory_map.get(code, 0)
            bank_qty = bank_items_map.get(code, 0)

            diff = desired - have
            logger.debug(f'code={code}, desired={desired}, have={have}, bank_qty={bank_qty}, diff={diff}')
            if diff > 0:
                withdraw_qty = min(diff, bank_qty)
                if withdraw_qty > 0:
                    withdraw_items_map[code] = withdraw_qty
                else:
                    logger.warning(f'Desired quantity {diff} of item {code} not available in bank.')

            elif diff < 0:
                if code in keep_item_codes:
                    continue

                item_level = self.service.get_item(code).level
                if item_level <= character.level:
                    if keep_consumables and code in self.consumable_codes:
                        continue
                    if keep_teleport_items and code in self.teleport_codes:
                        if diff < -1:
                            diff += 1  # deposit all except one
                        else:
                            continue

                deposit_items_map[code] = -diff

        if withdraw_items_map or deposit_items_map:
            teleport_items: Dict[str, int] = self.__add_teleport_items(character, item_map, bank_items_map)
            if teleport_items:
                logger.info(f'Adding teleport_items={teleport_items} to withdraw_items_map')
                withdraw_items_map.update(teleport_items)

        bank_interaction_actions = []
        if deposit_items_map:
            deposit_action = Task.deposit(items=deposit_items_map, task_id=task.task_id)
            bank_interaction_actions.append(deposit_action)

        if withdraw_items_map:
            withdraw_action = Task.withdraw(items=withdraw_items_map, task_id=task.task_id)
            bank_interaction_actions.append(withdraw_action)

        gold_task, gold_str = self.__generate_gold_action(gold, character, deposit_gold)
        if gold_task:
            bank_interaction_actions.append(gold_task)

        if bank_interaction_actions:
            logger.info(f'Planned bank interactions: deposit_items_map={deposit_items_map}, withdraw_items_map={withdraw_items_map}{gold_str}')
            bank_move, next_move = self.generate_moves(use_city_bank, return_previous_position, next_target, character)
            if bank_move:
                template_result.append(bank_move)
                template_result.extend(bank_interaction_actions)

            if next_move:
                template_result.append(next_move)
        elif next_target:
            move_task = Task.move(
                map_id=next_target.get('map_id'),
                content_type=next_target.get('content_type'),
                content_code=next_target.get('content_code'),
            )
            template_result.append(move_task)

        return template_result

    def generate_moves(
        self,
        use_city_bank: bool,
        return_previous_position: bool,
        next_target: Dict[str, int | str],
        character: CharacterSchemaExtension,
    ) -> tuple[Task, Optional[Task]]:
        character_map = self.service.get_map_by_id(character.map_id)
        bank_maps = self.__get_bank_maps(use_city_bank)
        next_maps = self.__get_next_maps(return_previous_position, character, next_target)
        if return_previous_position or next_target:
            logger.info(f'Found {len(next_maps)} maps for next_target={next_target}, return_previous_position={return_previous_position}')

        move_options = []
        for bank_map in bank_maps:
            bank_distance = self.service.get_distance_between(current_map=character_map, destination_map=bank_map)
            if bank_distance >= 10_000:
                continue
            bank_gold = self.service.get_cost_between(current_map=character_map, location=bank_map)
            if next_maps:
                for next_map in next_maps:
                    next_distance = self.service.get_distance_between(current_map=bank_map, destination_map=next_map)
                    if next_distance >= 10_000:
                        continue
                    next_gold = self.service.get_cost_between(current_map=bank_map, location=next_map)
                    move_options.append(
                        dict(
                            bank={'map_id': bank_map.map_id},
                            next={'map_id': next_map.map_id},
                            total_gold=bank_gold + next_gold,
                            total_distance=bank_distance + next_distance,
                            same_tile=bank_map.map_id == character_map.map_id,
                        )
                    )
            else:
                move_options.append(
                    dict(
                        bank={'map_id': bank_map.map_id},
                        total_gold=bank_gold,
                        total_distance=bank_distance,
                        same_tile=bank_map.map_id == character_map.map_id,
                    )
                )

        if move_options:
            move_options.sort(key=lambda x: (x['total_gold'], x['total_distance'], -x['same_tile']))
            best_move_option = move_options[0]
            bank_move = Task.move(map_id=best_move_option['bank']['map_id'])
            if 'next' in best_move_option:
                next_move = Task.move(map_id=best_move_option['next']['map_id'])
            else:
                next_move = None
        else:
            bank_move = next_move = None
        return bank_move, next_move

    def __generate_gold_action(self, desired_gold: Optional[int], character: CharacterSchemaExtension, deposit_gold: bool):
        if desired_gold is not None:
            have_gold = character.gold
            diff_gold = desired_gold - have_gold
            if diff_gold > 0:
                withdraw_gold = min(diff_gold, self.service.get_bank_details().gold)
                if withdraw_gold > 0:
                    return Task.withdraw_gold(withdraw_gold), f', withdraw_gold={withdraw_gold}'
            elif diff_gold < 0 and deposit_gold:
                deposit_gold = -diff_gold
                return Task.deposit_gold(deposit_gold), f', deposit_gold={deposit_gold}'
        return None, ''

    def __get_bank_maps(self, use_city_bank: bool, check_access: bool = True) -> List[MapSchemaExtension]:
        if use_city_bank:
            success_map = self.service.get_map_by_id(SUCCESS_POSITION_ID)
            location = self.service.get_closest_location(content_type='bank', current_map=success_map)
            return [location]
        else:
            banks = self.service.get_maps('bank')
            if check_access:
                achievements = self.service.get_account_achievements()
                achievements_map = {a.code: a for a in achievements}
                accessible_banks = []
                for bank in banks:
                    if bank.access.conditions:
                        for condition in bank.access.conditions:
                            if condition.operator == 'achievement_unlocked':
                                if achievements_map[condition.code].completed_at:
                                    accessible_banks.append(bank)
                            else:
                                logger.warning(
                                    f'Unknown condition to access bank {bank.name}: {condition.code}, {condition.operator}, {condition.value}'
                                )
                    else:
                        accessible_banks.append(bank)
                return accessible_banks
            else:
                return banks

    def __get_next_maps(self, return_previous_position: bool, character: CharacterSchemaExtension, next_target: Dict[str, int | str]):
        if return_previous_position:
            return [self.service.get_map_by_id(character.map_id)]
        elif 'content_type' in next_target:
            return self.service.get_maps(content_type=next_target.get('content_type'), content_code=next_target.get('content_code'))
        elif 'x' in next_target and 'y' in next_target:
            logger.warning(f'Used deprecated x/y coordinates in next_target: {next_target}')
            return [self.service.get_map(next_target.get('x'), next_target.get('y'))]
        elif 'map_id' in next_target:
            logger.info(f'map_id: {next_target["map_id"]}, next_target={next_target}')
            return [self.service.get_map_by_id(next_target['map_id'])]
        else:
            return []

    def __add_teleport_items(
        self, character: CharacterSchemaExtension, item_map: Dict[str, int], bank_items_map: Dict[str, int]
    ) -> Dict[str, int]:
        remaining_space = character.inventory_capacity(self.teleport_codes) - sum(item_map.values())
        if remaining_space <= 0:
            return {}

        available_teleports = (code for code in self.teleport_codes if code in bank_items_map and code not in character.inventory_map)
        return {code: 1 for code in islice(available_teleports, remaining_space)}
