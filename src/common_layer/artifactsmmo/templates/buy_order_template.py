from artifactsmmo.extensions import CharacterSchemaExtension
from artifactsmmo.log.logger import logger
from artifactsmmo.models import GEOrderSchema
from artifactsmmo.service.execution_context import ExecutionContext
from artifactsmmo.service.helpers import BucketFiller
from artifactsmmo.service.tasks import NextMove, Task
from artifactsmmo.templates.template_result import TemplateResult
from artifactsmmo.templates.template_strategy import TemplateStrategy


class BuyOrderTemplate(TemplateStrategy):
    def template(self) -> str:
        return 'buy-order'

    def render(self, character: CharacterSchemaExtension, task: Task, quest_id: str = None, context: ExecutionContext = None) -> TemplateResult:
        template_result: TemplateResult = TemplateResult()
        extra = task.extra
        order_id = extra.get('order_id')
        max_quantity = extra.get('max_quantity')

        teleport_item_codes = self.service.get_teleport_item_codes()
        ge_buy_bucket: BucketFiller = BucketFiller(character.inventory_capacity(teleport_item_codes))
        sell_order: GEOrderSchema = self.service.get_ge_order(order_id)
        if max_quantity is not None and max_quantity > 0:
            quantity = min(sell_order.quantity, max_quantity)
        else:
            quantity = sell_order.quantity

        withdraw_gold = sell_order.price * quantity
        next_move = NextMove(content_type='grand_exchange')
        inventory_task = Task.ensure_inventory(deposit_gold=False, gold=withdraw_gold, task_id=task.task_id, next_move=next_move)
        template_result.append(inventory_task)

        for bucket in ge_buy_bucket.generate_buckets(quantity):
            template_result.append(Task.buy_ge(order_id=order_id, quantity=bucket.quantity))
            if bucket.full:
                template_result.append(Task.ensure_inventory(deposit_gold=False, task_id=task.task_id, next_move=next_move))
        logger.info(f'Plan to buy {quantity}x from order_id={order_id}, gold={withdraw_gold}')

        return template_result
