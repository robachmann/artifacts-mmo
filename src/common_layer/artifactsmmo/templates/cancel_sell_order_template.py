from artifactsmmo.extensions import CharacterSchemaExtension
from artifactsmmo.log.logger import logger
from artifactsmmo.service.execution_context import ExecutionContext
from artifactsmmo.service.tasks import NextMove, Task
from artifactsmmo.templates.template_result import TemplateResult
from artifactsmmo.templates.template_strategy import TemplateStrategy


class CancelSellOrderTemplate(TemplateStrategy):
    def template(self) -> str:
        return 'cancel-sell-order'

    @staticmethod
    def describe_task(task: Task) -> str:
        return str(task.extra['order_id'])

    def render(self, character: CharacterSchemaExtension, task: Task, quest_id: str = None, context: ExecutionContext = None) -> TemplateResult:
        template_result: TemplateResult = TemplateResult()

        order_id = str(task.extra['order_id'])
        order = self.service.get_ge_order(order_id)
        if order:
            template_result.extend(
                [
                    Task.ensure_inventory(next_move=NextMove(content_type='grand_exchange')),
                    Task.cancel_order(order_id),
                ]
            )
            logger.info(f'Plan to cancel order {order_id}')
        else:
            logger.error(f'Order {order_id} not found')

        return template_result
