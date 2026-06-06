from collections import Counter
from typing import Dict

from artifactsmmo.extensions import CharacterSchemaExtension, ItemSchemaExtension
from artifactsmmo.game_constants import MAX_LEVEL
from artifactsmmo.log.logger import logger
from artifactsmmo.service.execution_context import ExecutionContext
from artifactsmmo.service.tasks import NextMove, Task
from artifactsmmo.templates.template_result import TemplateResult
from artifactsmmo.templates.template_strategy import TemplateStrategy


class DeliverFoodTemplate(TemplateStrategy):
    def template(self) -> str:
        return 'deliver-food'

    def render(self, character: CharacterSchemaExtension, task: Task, quest_id: str = None, context: ExecutionContext = None) -> TemplateResult:
        template_result: TemplateResult = TemplateResult()

        map_id = task.extra.get('map_id')
        if map_id:
            bank_items_map: Dict[str, int] = self.service.get_bank_items_map(task_id=task.task_id, character_name=character.name)
            processed_food_map: Dict[str, ItemSchemaExtension] = {f.code: f for f in self.service.get_processed_food()}

            max_level = min((c.level for c in self.service.get_all_character_details() if c.map_id == map_id), default=MAX_LEVEL)
            available_food_list = []
            for item_code, item_qty in bank_items_map.items():
                if item_code in processed_food_map:
                    item = processed_food_map[item_code]
                    if item.level <= max_level:
                        available_food_list.append(dict(code=item_code, restore_hp=item.heal_value(), level=item.level, quantity=item_qty))

            if available_food_list:
                available_food_list.sort(key=lambda x: x['restore_hp'], reverse=True)
                remaining_space = character.inventory_capacity() - 3
                food_delivery_map: Counter[str] = Counter()
                for food_dict in available_food_list:
                    pack_qty = min(remaining_space, food_dict['quantity'])
                    food_delivery_map[food_dict['code']] = pack_qty
                    remaining_space -= pack_qty
                    if not remaining_space:
                        break

                logger.info(f'Plan to deliver food={food_delivery_map} to map_id={map_id}')
                template_result.append(Task.ensure_inventory(deposit_gold=False))
                template_result.append(Task.ensure_inventory(item_map=dict(food_delivery_map), next_move=NextMove(map_id=map_id)))
                template_result.append(Task.distribute_food())
            else:
                logger.warning(f'No available food found with max_level={max_level} for map_id={map_id}')
        else:
            logger.error('No map_id provided. Dynamic lookup not implemented yet.')

        return template_result
