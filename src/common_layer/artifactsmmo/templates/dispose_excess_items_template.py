from typing import Dict, List

from artifactsmmo.extensions import CharacterSchemaExtension
from artifactsmmo.log.logger import logger
from artifactsmmo.models import GEOrderSchema
from artifactsmmo.service.execution_context import ExecutionContext
from artifactsmmo.service.tasks import Task
from artifactsmmo.templates.template_result import TemplateResult
from artifactsmmo.templates.template_strategy import TemplateStrategy


class DisposeExcessItemsTemplate(TemplateStrategy):
    def template(self) -> str:
        return 'dispose-excess-items'

    def render(self, character: CharacterSchemaExtension, task: Task, quest_id: str = None, context: ExecutionContext = None) -> TemplateResult:
        template_result: TemplateResult = TemplateResult()
        skill_filter = task.extra.get('skill')

        all_character_details: List[CharacterSchemaExtension] = self.service.get_all_character_details()
        min_character_level: int = min(c.level for c in all_character_details)
        min_character_level_threshold: int = max(1, min_character_level - 20)
        bank_items_map: Dict[str, int] = self.service.get_bank_items_map(task_id=task.task_id, character_name=character.name)
        all_characters_inventory_map = self.service.get_all_characters_inventory_map()
        ge_items_map: Dict[str, List[GEOrderSchema]] = self.service.get_ge_items_map()

        thresholds = {'weapon': 5, 'boots': 5, 'helmet': 5, 'shield': 5, 'leg_armor': 5, 'body_armor': 5, 'amulet': 5, 'ring': 10}

        for item_code, bank_quantity in bank_items_map.items():
            item = self.service.get_item(item_code)
            if item.type in thresholds.keys():
                if item.level < min_character_level_threshold and item.subtype != 'tool':
                    threshold = 0
                else:
                    threshold = thresholds.get(item.type)
                equipped_quantity = all_characters_inventory_map.get(item_code, 0)
                if bank_quantity + equipped_quantity > threshold:
                    dispose_quantity = min(bank_quantity + equipped_quantity - threshold, bank_quantity)
                    if item.craft:
                        skill = str(item.craft.skill)
                        skill_level = item.craft.level
                        if not skill_filter or skill == skill_filter:
                            if character.skills[skill].level >= skill_level:
                                logger.info(f'Plan to recycle {dispose_quantity}x {item_code} at {skill} workshop.')
                                template_result.append(Task.recycle_item(item_code, dispose_quantity))
                            else:
                                logger.warning(
                                    f'{character.name} cannot recycle {dispose_quantity}x {item_code} '
                                    f'(required skill={skill} at level={skill_level}).'
                                )
                    elif not skill_filter:
                        ge_items: List[GEOrderSchema] = ge_items_map.get(item_code, [])
                        if len(ge_items) > 0:
                            total_sell_price = dispose_quantity * min(ge_items, key=lambda i: i.price).price
                            logger.info(
                                f'Plan to sell item={item_code} ({dispose_quantity}x) at '
                                f'Grand Exchange for approx. {total_sell_price}g in total.'
                            )
                            # FIXME: implement
                            # template_result.append(Task.sell_item(item_code, dispose_quantity))
                        else:
                            logger.debug('Item %s cannot be sold.', item_code)

        return template_result
