from collections import defaultdict
from typing import Dict, List

from artifactsmmo.extensions import CharacterSchemaExtension
from artifactsmmo.log.logger import logger
from artifactsmmo.service.execution_context import ExecutionContext
from artifactsmmo.service.tasks import Task
from artifactsmmo.templates.template_result import TemplateResult
from artifactsmmo.templates.template_strategy import TemplateStrategy


class RecycleExcessItemsTemplate(TemplateStrategy):
    def template(self) -> str:
        return 'recycle-excess-items'

    @staticmethod
    def describe_task(task: Task) -> str:
        return f'of skill {task.extra.get("skill")}' if task.extra.get('skill') else ''

    def render(self, character: CharacterSchemaExtension, task: Task, quest_id: str = None, context: ExecutionContext = None) -> TemplateResult:
        template_result: TemplateResult = TemplateResult()
        skill_filter = task.extra.get('skill')

        all_character_details: List[CharacterSchemaExtension] = self.service.get_all_character_details()
        min_character_level: int = min(c.level for c in all_character_details)
        min_character_level_threshold: int = max(1, min_character_level - 20)
        bank_items_map: Dict[str, int] = self.service.get_bank_items_map(ignore_reservations=True)
        all_characters_inventory_map = self.service.get_all_characters_inventory_map(include_equipment=True)

        available_items_map: Dict[str, int] = defaultdict(int)
        for item_code, item_qty in bank_items_map.items():
            available_items_map[item_code] += item_qty

        for item_code, item_qty in all_characters_inventory_map.items():
            available_items_map[item_code] += item_qty

        available_tools: Dict[str, Dict[int, int]] = self.service.get_available_tools(available_items_map)
        skill_map = self.service.get_skill_map([character])

        for item_code, bank_quantity in bank_items_map.items():
            disposal_quantity: int = self.service.get_disposal_quantity(
                item_code, available_tools, available_items_map, min_character_level_threshold, bank_quantity, skill_filter, skill_map
            )
            if disposal_quantity > 0:
                logger.info(f'Plan to recycle {disposal_quantity}x {item_code}.')
                template_result.append(Task.recycle_item(item_code, disposal_quantity))

        if len(template_result.new_tasks) > 0:
            template_result.repeat()

        return template_result
