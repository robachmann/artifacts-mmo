from typing import Dict

from artifactsmmo.extensions import CharacterSchemaExtension
from artifactsmmo.log.logger import logger
from artifactsmmo.service.execution_context import ExecutionContext
from artifactsmmo.service.helpers import format_dict
from artifactsmmo.service.tasks import NextMove, Task
from artifactsmmo.templates.template_result import TemplateResult
from artifactsmmo.templates.template_strategy import TemplateStrategy


class EquipUtilityTemplate(TemplateStrategy):
    def template(self) -> str:
        return 'equip-utility'

    @staticmethod
    def describe_task(task: Task) -> str:
        return format_dict({task.extra.get('item'): task.extra.get('quantity', 1)})

    def render(self, character: CharacterSchemaExtension, task: Task, quest_id: str = None, context: ExecutionContext = None) -> TemplateResult:
        template_result: TemplateResult = TemplateResult()
        utility_code: str = task.extra.get('item')
        slot: str = task.extra.get('slot', 'utility1')
        quantity: int = task.extra.get('quantity', 1)
        return_previous_position: bool = task.extra.get('return_previous_position', False)

        bank_items_map: Dict[str, int] = self.service.get_bank_items_map(task_id=task.task_id, character_name=character.name)
        bank_available_quantity = bank_items_map.get(utility_code, 0)
        utility_equip_quantity = min(bank_available_quantity, quantity, 100)
        logger.info(
            f'item={utility_code}, utility_equip_quantity={utility_equip_quantity}, '
            f'bank_available_quantity={bank_available_quantity}, quantity={quantity}'
        )

        if 0 < utility_equip_quantity <= 100:
            equip_task = Task.equip(utility_code, slot, utility_equip_quantity)
            current_inventory_count = sum(character.inventory_map.values())
            if utility_equip_quantity + current_inventory_count > character.inventory_max_items:
                original_inventory_map = character.inventory_map
                sorted_dict = dict(sorted(original_inventory_map.items(), key=lambda item: item[1]))
                stripped_inventory_map = {utility_code: utility_equip_quantity}
                for item_code, item_quantity in sorted_dict.items():
                    if sum(stripped_inventory_map.values()) + item_quantity <= character.inventory_max_items:
                        stripped_inventory_map[item_code] = item_quantity
                    else:
                        break

                temp_inventory_task = Task.ensure_inventory(item_map=stripped_inventory_map, task_id=task.task_id, deposit_gold=False)
                next_move = NextMove(map_id=character.map_id) if return_previous_position else None
                original_inventory_task = Task.ensure_inventory(
                    item_map=original_inventory_map, task_id=task.task_id, deposit_gold=False, next_move=next_move
                )
                template_result.extend([temp_inventory_task, equip_task, original_inventory_task])
                logger.info(
                    f'Plan to equip {utility_equip_quantity}x {utility_code} to slot {slot}; '
                    f'will first ensure_inventory={stripped_inventory_map}, then ensure_inventory={original_inventory_map}'
                )
            else:
                task = Task.ensure_inventory(
                    item_map={utility_code: utility_equip_quantity},
                    task_id=task.task_id,
                    return_previous_position=return_previous_position,
                    keep_consumables=True,
                    deposit_gold=False,
                )
                template_result.extend([task, equip_task])
                logger.info(f'Plan to equip {utility_equip_quantity}x {utility_code} to slot {slot}')
        else:
            logger.error(f'utility_code={utility_code}, utility_equip_quantity={utility_equip_quantity}; must be between 0 and 100.')
        return template_result
