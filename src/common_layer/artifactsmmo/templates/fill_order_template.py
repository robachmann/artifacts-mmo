from artifactsmmo.extensions import CharacterSchemaExtension
from artifactsmmo.log.logger import logger
from artifactsmmo.service.execution_context import ExecutionContext
from artifactsmmo.service.tasks import NextMove, Task
from artifactsmmo.templates.template_result import TemplateResult
from artifactsmmo.templates.template_strategy import TemplateStrategy


class FillOrderTemplate(TemplateStrategy):
    def template(self) -> str:
        return 'fill-order'

    def render(self, character: CharacterSchemaExtension, task: Task, quest_id: str = None, context: ExecutionContext = None) -> TemplateResult:
        template_result: TemplateResult = TemplateResult()
        buy_order_id = task.extra['buy_order_id']

        buy_order = self.service.get_ge_order(buy_order_id)

        if buy_order:
            bank_items_map = self.service.get_bank_items_map(context=context)
            available_qty = bank_items_map.get(buy_order.code, 0) + character.inventory_map.get(buy_order.code, 0)
            sell_qty = min(available_qty, buy_order.quantity)
            if sell_qty:
                ge_map = NextMove(content_type='grand_exchange')
                template_result.append(Task.ensure_inventory({buy_order.code: sell_qty}, next_move=ge_map, deposit_gold=False))
                template_result.append(Task.fill_ge(buy_order_id, sell_qty))
                logger.info(f'Plan to fill buy order {buy_order_id} by selling {sell_qty}x {buy_order.code}')

        return template_result
