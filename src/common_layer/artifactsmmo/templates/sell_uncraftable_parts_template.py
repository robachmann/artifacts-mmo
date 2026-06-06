from artifactsmmo.extensions import CharacterSchemaExtension
from artifactsmmo.log.logger import logger
from artifactsmmo.service.execution_context import ExecutionContext
from artifactsmmo.service.tasks import Task
from artifactsmmo.templates.template_result import TemplateResult
from artifactsmmo.templates.template_strategy import TemplateStrategy


class SellUncraftablePartsTemplate(TemplateStrategy):
    def template(self) -> str:
        return 'sell-uncraftable-parts'

    def render(self, character: CharacterSchemaExtension, task: Task, quest_id: str = None, context: ExecutionContext = None) -> TemplateResult:
        template_result: TemplateResult = TemplateResult()
        extra = task.extra
        threshold = int(extra.get('threshold', 500))

        sell_items = self.service.generate_uncraftable_sell_list(threshold=threshold)

        # for item in sell_items:
        #    template_result.append(Task.sell_item(item=item.code, quantity=item.quantity))
        logger.error('Unknown sell price.')
        return template_result
