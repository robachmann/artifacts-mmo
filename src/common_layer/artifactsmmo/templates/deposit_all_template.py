from typing import Dict

from artifactsmmo.extensions import CharacterSchemaExtension, ItemSchemaExtension
from artifactsmmo.game_constants import SUCCESS_POSITION_ID
from artifactsmmo.log.logger import logger
from artifactsmmo.service.execution_context import ExecutionContext
from artifactsmmo.service.tasks import Task
from artifactsmmo.templates.template_result import TemplateResult
from artifactsmmo.templates.template_strategy import TemplateStrategy


class DepositAllTemplate(TemplateStrategy):
    def template(self) -> str:
        return 'deposit-all'

    @staticmethod
    def describe_task(task: Task) -> str:
        return ''

    def render(self, character: CharacterSchemaExtension, task: Task, quest_id: str = None, context: ExecutionContext = None) -> TemplateResult:
        template_result: TemplateResult = TemplateResult()
        extra = task.extra
        return_previous_position = bool(extra.get('return_previous_position', False))
        exclude_processed_food = bool(extra.get('exclude_processed_food', False))
        exclude_teleport_items = bool(extra.get('exclude_teleport_items', True))
        exclude_items = extra.get('exclude_items') or []
        use_city_bank = bool(extra.get('use_city_bank', False))

        deposit_tasks = []
        processed_consumables_map: Dict[str, ItemSchemaExtension] = {
            f.code: f for f in self.service.get_processed_food_by_level(character.level)
        }
        deposit_map: Dict[str, int] = {}
        for item_code, item_quantity in character.inventory_map.items():
            if item_code and item_code not in exclude_items:
                deposit_quantity = item_quantity
                if exclude_processed_food and item_code in processed_consumables_map:
                    continue

                if exclude_teleport_items and self.service.get_item(item_code).is_teleport_item:
                    if deposit_quantity > 1:
                        deposit_quantity -= 1
                    else:
                        continue
                deposit_map[item_code] = deposit_quantity

        if deposit_map:
            deposit_tasks.append(Task.deposit(items=deposit_map, task_id=task.task_id))
            logger.info(f'Plan to deposit deposit_map={deposit_map}')

        gold_coins = character.gold
        if gold_coins > 0:
            deposit_tasks.append(Task.deposit_gold(quantity=gold_coins))

        if deposit_tasks:
            if use_city_bank:
                success_map = self.service.get_map_by_id(SUCCESS_POSITION_ID)
                location = self.service.get_closest_location(content_type='bank', current_map=success_map)
                if location:
                    template_result.append(Task.move(map_id=location.map_id))
                else:
                    template_result.append(Task.move(content_type='bank'))
            else:
                template_result.append(Task.move(content_type='bank'))
            template_result.extend(deposit_tasks)

            if return_previous_position:
                template_result.append(Task.move(map_id=character.map_id))

        return template_result
