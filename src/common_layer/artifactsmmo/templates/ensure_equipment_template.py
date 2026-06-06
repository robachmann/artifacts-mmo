from collections import Counter, defaultdict
from typing import Dict, List, Tuple

from artifactsmmo.extensions import CharacterSchemaExtension, ItemSchemaExtension
from artifactsmmo.game_constants import DEFAULT_SLEEP_TTL
from artifactsmmo.log.logger import logger
from artifactsmmo.models import GatheringSkill
from artifactsmmo.service.execution_context import ExecutionContext
from artifactsmmo.service.helpers import format_dict
from artifactsmmo.service.tasks import Task
from artifactsmmo.templates.template_result import TemplateResult
from artifactsmmo.templates.template_strategy import TemplateStrategy


class EnsureEquipmentTemplate(TemplateStrategy):
    def template(self) -> str:
        return 'ensure-equipment'

    @staticmethod
    def describe_task(task: Task) -> str:
        if task.extra.get('exact_map'):
            return format_dict(task.extra.get('exact_map'))
        elif task.extra.get('equipment_list') and task.extra.get('quantity'):
            if task.extra.get('equipment_list') and len(task.extra.get('equipment_list')) == 1:
                return f'{task.extra.get("quantity")}x {task.extra.get("equipment_list")[0]}'
            else:
                return f'{task.extra.get("quantity")}x {task.extra.get("equipment_list")}'
        return ''

    def render(self, character: CharacterSchemaExtension, task: Task, quest_id: str = None, context: ExecutionContext = None) -> TemplateResult:
        template_result: TemplateResult = TemplateResult()

        equipment_list: List[str] = task.extra.get('equipment_list') or []
        equipment_map: Dict[str, str] = task.extra.get('equipment_map') or {}
        desired_global_quantity: int = int(task.extra.get('quantity') or 1)
        exact_list: List[str] = task.extra.get('exact_list') or []
        exact_map: Dict[str, int] = task.extra.get('exact_map') or {}
        request_support: bool = bool(task.extra.get('request_support', False))
        craft_available_first: bool = bool(task.extra.get('craft_available_first', True))
        recipe_id = task.task_id or Task.generate_task_id()

        craft_map: Dict[str, int] = self.__create_craft_map(exact_map, exact_list, equipment_map, equipment_list, desired_global_quantity)

        logger.info(
            'equipment_list=%s, equipment_map=%s, quantity=%d, craft_map=%s',
            equipment_list,
            equipment_map,
            desired_global_quantity,
            craft_map,
        )

        bank_items_map = self.service.get_bank_items_map(task_id=task.task_id, context=context, character_name=character.name)
        bank_items_map_copy = bank_items_map.copy()

        resolved_item_recipe, immediately_craftable_recipes = self.service.resolve_recipes(craft_map, bank_items_map)

        subtract_map = defaultdict(int)
        if craft_available_first and immediately_craftable_recipes:
            for item_code, item_qty in immediately_craftable_recipes.items():
                item = self.service.get_item(item_code)
                if item.craft or item.is_npc_item:
                    template_result.append(Task.craft_recipe(task_id=recipe_id, item=item_code, quantity=item_qty, leader=character.name))
                    craft_map[item_code] -= item_qty

                    craftable_recipe, _ = self.service.resolve_recipes({item_code: item_qty}, bank_items_map_copy)
                    for available_code, available_qty in craftable_recipe.available_items.items():
                        subtract_map[available_code] += available_qty
                        logger.info(
                            f'Reduced total_quantity of {available_code} by {available_qty} since {item_code} will be '
                            f'immediately crafted {item_qty} times.'
                        )

        missing_items_list: List[dict] = []
        if resolved_item_recipe.missing_items:
            for item_code, item_quantity in resolved_item_recipe.missing_items.items():
                item = self.service.get_item(item_code)
                sort_id, is_monster = self.__get_sort_id(character, item)
                total_quantity = resolved_item_recipe.all_items[item.code]
                if item.is_task_reward:
                    item_quantity = total_quantity
                    logger.info(f'Adjusted item_quantity of item_code={item_code} to item_quantity={item_quantity}.')

                missing_items_list.append(
                    {
                        'item_code': item_code,
                        'item_quantity': item_quantity,
                        'total_quantity': total_quantity,
                        'sort_id': sort_id,
                        'is_monster': is_monster,
                    }
                )

            missing_items_list.sort(key=lambda i: i['sort_id'])

            for i in range(len(missing_items_list)):
                missing_item = missing_items_list[i]
                item_code = missing_item['item_code']
                item_quantity = missing_item['item_quantity']
                total_quantity = missing_item['total_quantity'] - subtract_map[item_code]
                next_is_monster = False
                if i + 1 < len(missing_items_list):
                    next_is_monster = missing_items_list[i + 1]['is_monster']
                template_result.append(
                    Task.gather_recipe(
                        item=item_code,
                        quantity=item_quantity,
                        missing_quantity=item_quantity,
                        total_quantity=total_quantity,
                        task_id=recipe_id,
                        leader=character.name,
                        request_support=request_support,
                        add_sleep_task=False,
                        keep_equipment=next_is_monster,
                    )
                )

            template_result.append(
                Task.sleep(
                    task_id=recipe_id,
                    leader=character.name,
                    items_map=resolved_item_recipe.all_items,
                    ttl=DEFAULT_SLEEP_TTL,
                )
            )
        if resolved_item_recipe.available_items:
            self.service.add_bank_reservations(
                reservation_id=recipe_id, equipment_map=resolved_item_recipe.available_items, character_name=character.name
            )

        for item_code, item_quantity in craft_map.items():
            item = self.service.get_item(item_code)
            if item_quantity > 0 and (item.craft or item.is_npc_item):
                template_result.append(Task.craft_recipe(task_id=recipe_id, item=item_code, quantity=item_quantity, leader=character.name))

        return template_result

    def __create_craft_map(
        self,
        exact_map: Dict[str, int],
        exact_list: List[str],
        equipment_map: Dict[str, str],
        equipment_list: List[str],
        desired_global_quantity: int,
    ):
        if exact_map:
            craft_map: Dict[str, int] = {}
            global_quantity_map = self.service.get_global_quantity_map()
            for item_code, max_qty in exact_map.items():
                delta = max_qty - global_quantity_map.get(item_code, 0)
                if delta > 0:
                    craft_map[item_code] = delta
        else:
            if exact_list:
                craft_map = Counter(exact_list)
            else:
                combined_list = list(equipment_map.values()) + equipment_list
                craft_map = Counter(
                    {item_code: item_count * desired_global_quantity for item_code, item_count in Counter(combined_list).items()}
                )

                global_quantity_map = self.service.get_global_quantity_map()
                for item_code in list(craft_map):
                    global_quantity = global_quantity_map.get(item_code, 0)
                    if global_quantity >= craft_map[item_code]:
                        del craft_map[item_code]
                    else:
                        craft_map[item_code] -= global_quantity
        return dict(craft_map)

    def __get_sort_id(self, character: CharacterSchemaExtension, item: ItemSchemaExtension) -> Tuple[int, bool]:
        sort_id = 0
        is_monster = False
        item_origin = self.service.get_item_origin(item.code)
        if item_origin:
            if item_origin.resources:
                sub_type_id = 0
                level_up_modifier = 0
                match item.subtype:
                    case GatheringSkill.WOODCUTTING:
                        sub_type_id = 100
                    case GatheringSkill.MINING:
                        sub_type_id = 200
                    case GatheringSkill.ALCHEMY:
                        sub_type_id = 300
                    case GatheringSkill.FISHING:
                        sub_type_id = 400
                if item.subtype in character.skills and character.skills[item.subtype].level < item.level:
                    level_up_modifier = 2000
                sort_id = item.level + sub_type_id + level_up_modifier
            elif item_origin.monsters:
                sort_id = item.level + sum(monster.drop_rate for monster in item_origin.monsters.values()) + 1000
                is_monster = True
            elif item_origin.tasks:
                sort_id = item.level + max(d.drop_rate for d in item_origin.tasks) + 2000
            elif item_origin.npcs:
                sort_id = item.level + 3000
        return sort_id, is_monster
