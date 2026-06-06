from artifactsmmo.extensions import CharacterSchemaExtension
from artifactsmmo.log.logger import logger
from artifactsmmo.service.execution_context import ExecutionContext
from artifactsmmo.service.tasks import Task
from artifactsmmo.templates.template_result import TemplateResult
from artifactsmmo.templates.template_strategy import TemplateStrategy


class SellExcessPartsTemplate(TemplateStrategy):
    def template(self) -> str:
        return 'sell-excess-parts'

    def render(self, character: CharacterSchemaExtension, task: Task, quest_id: str = None, context: ExecutionContext = None) -> TemplateResult:
        template_result: TemplateResult = TemplateResult()
        extra = task.extra
        threshold = extra.get('threshold', 1000)
        item_type = extra.get('item_type', 'all')
        item_subtype = extra.get('item_subtype', 'all')
        max_level = extra.get('max_level')

        sell_items = self.service.generate_excess_sell_list(
            threshold=threshold, item_type=item_type, item_subtype=item_subtype, max_level=max_level
        )

        # for item in sell_items:
        #    template_result.append(Task.sell_item(item=item.code, quantity=item.quantity))
        logger.error('Unknown sell price.')
        return template_result
