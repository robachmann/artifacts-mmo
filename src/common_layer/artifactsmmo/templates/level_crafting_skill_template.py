import math
from typing import Dict, List, Optional, Tuple

from artifactsmmo.client.client import Client
from artifactsmmo.dynamodb.character_table import CharacterTable
from artifactsmmo.dynamodb.equipment_lock_table import EquipmentLockTable
from artifactsmmo.dynamodb.skill_stats_table import SkillStatsTable
from artifactsmmo.extensions import CharacterSchemaExtension, ItemSchemaExtension
from artifactsmmo.extensions.CharacterSchemaExtension import CharacterSkill
from artifactsmmo.game_constants import MAX_LEVEL, RECYCLING_SKILLS, RECYCLING_YIELD_FACTOR
from artifactsmmo.log.logger import logger
from artifactsmmo.models import CraftSkill
from artifactsmmo.queue.dispatcher_queue import DispatcherQueue
from artifactsmmo.queue.worker_queue import WorkerQueue
from artifactsmmo.service.dispatch_service import DispatchService
from artifactsmmo.service.execution_context import ExecutionContext
from artifactsmmo.service.fight_simulator import FightSimulator
from artifactsmmo.service.food_service import FoodService
from artifactsmmo.service.service import Service
from artifactsmmo.service.tasks import Task
from artifactsmmo.static.xp_maps import XpMaps
from artifactsmmo.telegram.client import TelegramClient
from artifactsmmo.templates.common_templates import gather_and_craft_recipe
from artifactsmmo.templates.template_result import TemplateResult
from artifactsmmo.templates.template_strategy import TemplateStrategy


class LevelCraftingSkillTemplate(TemplateStrategy):
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

        self.recycling_factor = 1 / (RECYCLING_YIELD_FACTOR + 1)
        xp_maps = XpMaps()
        self.xp_map_resources = xp_maps.read_file('resources')
        self.xp_map_gearcrafting = xp_maps.read_file('gearcrafting')

    def template(self) -> str:
        return 'level-crafting-skill'

    @staticmethod
    def describe_task(task: Task) -> str:
        stock_str = ''
        if bool(task.extra.get('stock_only', False)):
            stock_str = ' (stock)'
        if task.extra.get('level'):
            return f'{task.extra.get("skill")} to {task.extra.get("level")}{stock_str}'
        else:
            return f'{task.extra.get("skill")} to the next level{stock_str}'

    def render(self, character: CharacterSchemaExtension, task: Task, quest_id: str = None, context: ExecutionContext = None) -> TemplateResult:
        template_result: TemplateResult = TemplateResult()
        extra = task.extra
        skill = extra['skill']
        initial_target_level = extra.get('level')
        stock_only = bool(extra.get('stock_only', False))
        allow_task_parts = bool(extra.get('allow_task_parts', False))
        allow_event_parts = bool(extra.get('allow_event_parts', False))
        allow_boss_parts = bool(extra.get('allow_boss_parts', False))
        item_code = extra.get('item')
        request_support = bool(extra.get('request_support', False))
        recipe_id = task.task_id or Task.generate_task_id()

        current_level = character.skills[skill].level
        if initial_target_level is None:
            initial_target_level = min(current_level + 1, MAX_LEVEL)

        if current_level >= initial_target_level:
            return template_result

        if item_code:
            items = [self.service.get_item(item_code)]
        else:
            items = self.service.get_craftable_items(
                skill, current_level - 10, current_level, allow_task_parts, allow_event_parts, allow_boss_parts
            )

        wisdom_factor = self.get_wisdom_factor(character.level)
        bank_items_map = self.service.get_bank_items_map(context=context, task_id=task.task_id, character_name=character.name)

        craft_code, quantity, target_level = self.get_craft_item(
            current_level,
            initial_target_level,
            character.skills[skill],
            wisdom_factor,
            items,
            bank_items_map,
            stock_only,
        )

        if craft_code and quantity is not None and quantity > 0:
            is_recyclable = skill in RECYCLING_SKILLS

            if is_recyclable and quantity >= 10:
                crafting_quantity = math.ceil(quantity * self.recycling_factor)
            else:
                crafting_quantity = quantity

            target = 'recycle' if is_recyclable else 'bank'
            should_request_support = False if stock_only else request_support

            template_result.extend(
                gather_and_craft_recipe(
                    recipe_id=recipe_id,
                    item=craft_code,
                    quantity=crafting_quantity,
                    target=target,
                    allow_fewer=True,
                    leader=character.name,
                    request_support=should_request_support,
                )
            )

            logger.info(
                f'Plan to craft {craft_code} {quantity} times to level '
                f'skill={skill} from current level={current_level} to target level={target_level}'
            )
        else:
            log_msg = (
                f'No suitable items found to level skill={skill} from current level={current_level} to target level={target_level}, '
                f'item_candidates={[i.code for i in items]}'
            )
            if stock_only:
                logger.info(log_msg)
            else:
                logger.warning(log_msg)

        if template_result.new_tasks:
            new_task_target_level = max(initial_target_level, target_level)
            template_result.append(
                Task.level_crafting_skill(
                    # task_id=recipe_id,
                    skill=skill,
                    target_level=new_task_target_level,
                    stock_only=stock_only,
                    allow_task_parts=allow_task_parts,
                    allow_event_parts=allow_event_parts,
                    allow_boss_parts=allow_boss_parts,
                    item=item_code,
                    request_support=request_support,
                )
            )

        return template_result

    def get_wisdom_factor(self, character_level: int):
        wisdom_gear = self.service.get_best_wisdom_gear_by_level(character_level)
        wisdom_value = 0
        for gear_list in wisdom_gear.values():
            wisdom_value += max(i.wisdom_value() for i in gear_list)
        return 1 + wisdom_value * 0.001

    def get_craft_item(
        self,
        current_level: int,
        initial_target_level: int,
        character_skill: CharacterSkill,
        wisdom_factor: float,
        items: List[ItemSchemaExtension],
        bank_items_map: Dict[str, int],
        stock_only: bool,
    ) -> Tuple[str, int, int]:
        best_craft_item = None
        best_craft_qty = None
        lowest_drop_rate: Optional[int] = None
        res_target_level = initial_target_level

        xp_map: Dict[int, int] = self.service.get_xp_map()
        for item in items:
            target_level = min(current_level + 10, initial_target_level, item.level + 10 if item.level > 1 else 10)

            expected_qty = 0
            current_xp = character_skill.xp
            for lvl in range(current_level, target_level):
                item_xp = self.calculate_expected_xp(item, lvl, wisdom_factor)
                missing_xp = xp_map[lvl] - current_xp
                qty = math.ceil(missing_xp / item_xp)
                expected_qty += qty
                new_xp = (qty * item_xp) + current_xp
                current_xp = new_xp - xp_map[lvl]

            if expected_qty > 0:
                resolved_recipe = self.service.resolve_item_recipe(item.code, bank_items_map, expected_qty)
                if resolved_recipe:
                    if not resolved_recipe.missing_items:
                        if not lowest_drop_rate or (best_craft_qty is not None and expected_qty < best_craft_qty):
                            best_craft_item = item.code
                            best_craft_qty = expected_qty
                            res_target_level = target_level
                            lowest_drop_rate = 0
                    elif stock_only:
                        if resolved_recipe.available_items:
                            craftable_recipe_count = self.service.get_craftable_recipe_count(item.code, bank_items_map)
                            if craftable_recipe_count > 0:
                                best_craft_item = item.code
                                best_craft_qty = min(expected_qty, craftable_recipe_count)
                                res_target_level = target_level
                                # lowest_drop_rate = 0
                                break
                    else:
                        drop_rate = 0
                        for missing_code, missing_qty in resolved_recipe.missing_items.items():
                            drop_rates = self.service.get_drop_rate(item_code=missing_code)
                            for dr in drop_rates:
                                drop_rate += int((dr.drop_rate_min + dr.drop_rate_max) / 2 * missing_qty)

                        if not lowest_drop_rate or drop_rate < lowest_drop_rate:
                            best_craft_item = item.code
                            best_craft_qty = expected_qty
                            res_target_level = target_level
                            lowest_drop_rate = drop_rate

        return best_craft_item, best_craft_qty, res_target_level

    def calculate_expected_xp(self, item: ItemSchemaExtension, skill_level: int, wisdom_factor: float):
        expected_xp = 0
        item_level_str = str(item.level)
        skill_level_str = str(skill_level)
        match item.craft.skill:
            case CraftSkill.JEWELRYCRAFTING | CraftSkill.GEARCRAFTING | CraftSkill.WEAPONCRAFTING | CraftSkill.ALCHEMY | CraftSkill.COOKING:
                expected_xp = self.xp_map_gearcrafting.get(item_level_str, {}).get(skill_level_str, 0)
            case CraftSkill.WOODCUTTING | CraftSkill.MINING:
                expected_xp = self.xp_map_resources.get(item_level_str, {}).get(skill_level_str, 0)
            case _:
                logger.error(f'Cannot determine expected xp for item={item.code}, craft_skill={item.craft.skill}')

        return int(expected_xp * wisdom_factor) if expected_xp > 0 else 1
