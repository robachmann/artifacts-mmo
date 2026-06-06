from collections import defaultdict
from math import ceil
from typing import Dict, List

from artifactsmmo.extensions import CharacterSchemaExtension
from artifactsmmo.log.logger import logger
from artifactsmmo.models import GEOrderSchema
from artifactsmmo.service.execution_context import ExecutionContext
from artifactsmmo.service.tasks import Task
from artifactsmmo.templates.template_result import TemplateResult
from artifactsmmo.templates.template_strategy import TemplateStrategy


class CompactGrandExchangeOrdersTemplate(TemplateStrategy):
    def template(self) -> str:
        return 'compact-grand-exchange-orders'

    @staticmethod
    def describe_task(task: Task) -> str:
        return ''

    def render(self, character: CharacterSchemaExtension, task: Task, quest_id: str = None, context: ExecutionContext = None) -> TemplateResult:
        template_result: TemplateResult = TemplateResult()

        sell_orders: List[GEOrderSchema] = self.service.get_account_ge_sell_orders()

        order_stats_map = {}
        orders_map: Dict[str, List[GEOrderSchema]] = defaultdict(list)
        for order in sell_orders:
            if order.code not in order_stats_map:
                order_stats_map[order.code] = dict(quantity=0, orders=0)

            order_stats_map[order.code]['quantity'] += order.quantity
            order_stats_map[order.code]['orders'] += 1
            orders_map[order.code].append(order)

        for item_code, order_stat in order_stats_map.items():
            quantity = order_stat['quantity']
            count = order_stat['orders']

            min_orders = ceil(quantity / 100)

            if min_orders < count:
                # logger.warning(f'{item_code}: {quantity}x in {count} orders, could be compacted to {min_orders} orders.')
                max_price = 1
                total_quantity = 0
                cancelled_orders: List[str] = []
                for order in orders_map[item_code]:
                    if order.quantity < 100:
                        max_price = max(max_price, order.price)
                        total_quantity += order.quantity
                        template_result.append(Task.cancel_sell_order(order.id))
                        cancelled_orders.append(order.id)
                template_result.append(Task.sell_item(item_code, max_price, total_quantity))
                logger.info(
                    f'Plan to cancel {len(cancelled_orders)} orders {cancelled_orders} and sell again a total of '
                    f'{total_quantity}x {item_code} for {max_price} gold each.'
                )

        return template_result
