from typing import Optional

from artifactsmmo.extensions import CharacterSchemaExtension
from artifactsmmo.log.logger import logger
from artifactsmmo.service.execution_context import ExecutionContext
from artifactsmmo.service.tasks import Task
from artifactsmmo.templates.template_result import TemplateResult
from artifactsmmo.templates.template_strategy import TemplateStrategy


class PrepareRecipeTemplate(TemplateStrategy):
    def template(self) -> str:
        return 'prepare-recipe'

    @staticmethod
    def describe_task(task: Task) -> str:
        if task.extra['max_quantity']:
            return f'max {task.extra["max_quantity"]}x {task.extra["item"]}'
        else:
            return task.extra['item']

    def render(self, character: CharacterSchemaExtension, task: Task, quest_id: str = None, context: ExecutionContext = None) -> TemplateResult:
        template_result: TemplateResult = TemplateResult()

        item_code: str = task.extra['item']
        max_quantity: Optional[int] = task.extra['max_quantity']

        item = self.service.get_item(item_code)

        if item.craft:
            bank_items_map = self.service.get_bank_items_map(task_id=task.task_id, character_name=character.name)

            craftable_recipes = 0
            for craft in item.craft.items:
                current_stock = bank_items_map.get(craft.code, 0)
                recipe_quantity = current_stock // craft.quantity
                craftable_recipes = max(craftable_recipes, recipe_quantity)

            if max_quantity:
                craftable_recipes = min(max_quantity, craftable_recipes)

            if craftable_recipes:
                recipe_id = Task.generate_task_id()
                template_result.append(
                    Task.gather_recipe(
                        task_id=recipe_id,
                        item=item_code,
                        quantity=craftable_recipes,
                        add_sleep_task=False,
                        reserve_target_product=False,
                    )
                )
                logger.info(f'Plan to gather parts for {craftable_recipes}x {item_code}.')

        return template_result
