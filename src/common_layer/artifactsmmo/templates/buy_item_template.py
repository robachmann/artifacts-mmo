from typing import Dict, List

from artifactsmmo.extensions import CharacterSchemaExtension
from artifactsmmo.log.logger import logger
from artifactsmmo.models import GEOrderSchema
from artifactsmmo.service.execution_context import ExecutionContext
from artifactsmmo.service.helpers import calculate_total_sell_price, get_sell_order_map
from artifactsmmo.service.tasks import Task
from artifactsmmo.templates.template_result import TemplateResult
from artifactsmmo.templates.template_strategy import TemplateStrategy


class BuyItemTemplate(TemplateStrategy):
    def template(self) -> str:
        return 'buy-item'

    def render(self, character: CharacterSchemaExtension, task: Task, quest_id: str = None, context: ExecutionContext = None) -> TemplateResult:
        template_result: TemplateResult = TemplateResult()
        extra = task.extra
        item_code = extra.get('item')
        quantity = int(extra.get('quantity', 1))
        force_buy = bool(extra.get('force_buy', False))

        sell_orders: List[GEOrderSchema] = self.service.get_ge_sell_orders(item_code)
        sell_order_map: Dict[str, int] = get_sell_order_map(sell_orders, quantity)
        total_sell_price, quantity_available = calculate_total_sell_price(sell_orders, quantity)
        bank_details = self.service.get_bank_details()

        if force_buy:
            gold_needed = total_sell_price
        else:
            items_map = self.service.get_bank_items_map(task_id=task.task_id, character_name=character.name)
            total_items = sum(items_map.values())

            if bank_details.slots - total_items >= 20:
                threshold = 0
            else:
                threshold = bank_details.next_expansion_cost

            gold_needed = total_sell_price + threshold

        if quantity_available > 0 and bank_details.gold > gold_needed:
            for order_id, order_quantity in sell_order_map.items():
                template_result.append(Task.buy_order(order_id=order_id, max_quantity=order_quantity))
                logger.info(f'Plan to buy {order_quantity}x {item_code} from order={order_id}')
        else:
            logger.info(
                f'Cannot afford buying desired item: {item_code} ({quantity}x). Required gold: {gold_needed},'
                f' gold available: {bank_details.gold}'
            )

        return template_result
