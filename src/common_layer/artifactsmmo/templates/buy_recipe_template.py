from typing import List

from artifactsmmo.extensions import CharacterSchemaExtension
from artifactsmmo.log.logger import logger
from artifactsmmo.models import SimpleItemSchema
from artifactsmmo.service.execution_context import ExecutionContext
from artifactsmmo.service.helpers import ResolvedItemRecipe
from artifactsmmo.service.tasks import Task
from artifactsmmo.templates.template_result import TemplateResult
from artifactsmmo.templates.template_strategy import TemplateStrategy


class BuyRecipeTemplate(TemplateStrategy):
    def template(self) -> str:
        return 'buy-recipe'

    def render(self, character: CharacterSchemaExtension, task: Task, quest_id: str = None, context: ExecutionContext = None) -> TemplateResult:
        template_result: TemplateResult = TemplateResult()

        extra = task.extra
        item = extra.get('item')
        quantity = int(extra.get('quantity', 1))
        force_buy = bool(extra.get('force_buy', False))

        if force_buy:
            buy_items: List[SimpleItemSchema] = self.service.generate_recipe_buy_list(item_code=item, quantity=quantity)
            for buy_item in buy_items:
                template_result.append(Task.buy_item(buy_item.code, buy_item.quantity, force_buy))
        else:
            bank_items_map = self.service.get_bank_items_map(task_id=task.task_id, character_name=character.name)
            resolved_item_recipe: ResolvedItemRecipe = self.service.resolve_item_recipe(item, bank_items_map, quantity)
            for item_code, qty in resolved_item_recipe.missing_items.items():
                i = self.service.get_item(item_code)
                if i.ge.stock > 0:
                    template_result.append(Task.buy_item(i.item.code, qty, force_buy))
                else:
                    logger.warning(f'Grand Exchange has no {item_code} in stock. Skipping purchase.')

        return template_result
