from collections import Counter
import math

from artifactsmmo.extensions import CharacterSchemaExtension
from artifactsmmo.game_constants import SALES_TAX
from artifactsmmo.log.logger import logger
from artifactsmmo.models import MapContentType
from artifactsmmo.service.execution_context import ExecutionContext
from artifactsmmo.service.helpers import BucketFiller
from artifactsmmo.service.tasks import NextMove, Task
from artifactsmmo.templates.template_result import TemplateResult
from artifactsmmo.templates.template_strategy import TemplateStrategy


class SellItemTemplate(TemplateStrategy):
    def template(self) -> str:
        return 'sell-item'

    @staticmethod
    def describe_task(task: Task) -> str:
        item_code = task.extra.get('item')
        if task.extra.get('keep_quantity') and not task.extra.get('quantity'):
            return f'all of {item_code} except {task.extra.get("keep_quantity")} for {task.extra.get("sell_price")}g each'
        elif task.extra.get('quantity'):
            return f'{task.extra.get("quantity")}x {item_code} for {task.extra.get("sell_price")}g each'
        elif task.extra.get('quantity'):
            return f'all of {item_code} for {task.extra.get("sell_price")}g each'
        else:
            return item_code

    def render(self, character: CharacterSchemaExtension, task: Task, quest_id: str = None, context: ExecutionContext = None) -> TemplateResult:
        template_result: TemplateResult = TemplateResult()

        item_code = task.extra['item']
        sell_price = int(task.extra['sell_price'])
        keep_quantity = task.extra.get('keep_quantity')
        quantity = task.extra.get('quantity')
        global_quantity = self.service.get_global_quantity(item_code)

        if not sell_price:
            logger.error(f'Missing sell_price for {item_code}.')
            return template_result

        item = self.service.get_item(item_code)
        if not item.tradeable:
            logger.error(f'Item cannot be traded: {item_code}.')
            return template_result

        if keep_quantity is None:
            sell_quantity = min(global_quantity, quantity or 0)
        else:
            sell_quantity = max(0, global_quantity - keep_quantity)
            if quantity:
                sell_quantity = min(sell_quantity, quantity)

        if sell_quantity:
            bank_items_map = Counter(self.service.get_bank_items_map(task_id=task.task_id, character_name=character.name))
            bank_items_map.update(character.inventory_map)
            remaining_sell_slots = 100 - len(self.service.get_account_ge_sell_orders())
            remaining_sell_quantity = remaining_sell_slots * 100
            sell_quantity = min(sell_quantity, bank_items_map.get(item_code, 0), remaining_sell_quantity)

        if sell_quantity:
            if SALES_TAX > 0:
                required_gold = max(1, math.ceil(sell_price * sell_quantity * SALES_TAX))
                logger.info(
                    f'Plan to sell {sell_quantity}x {item_code} for a total of {sell_price * sell_quantity} gold '
                    f'which costs {required_gold} gold in taxes.'
                )
            else:
                required_gold = None
                logger.info(f'Plan to sell {sell_quantity}x {item_code} for a total of {sell_price * sell_quantity} gold.')

            teleport_item_codes = self.service.get_teleport_item_codes()

            withdraw_limit = character.inventory_capacity(teleport_item_codes)
            if withdraw_limit > 200:
                withdraw_limit = 200
            elif withdraw_limit > 100:
                withdraw_limit = 100

            bank_withdraw_bucket: BucketFiller = BucketFiller(withdraw_limit)
            runs = 0
            next_move = NextMove(content_type=MapContentType.GRAND_EXCHANGE)
            for bucket in bank_withdraw_bucket.generate_buckets(sell_quantity):
                template_result.append(
                    Task.ensure_inventory(
                        item_map={item_code: bucket.quantity},
                        gold=required_gold if not runs else None,
                        deposit_gold=False,
                        next_move=next_move,
                        task_id=task.task_id,
                    )
                )

                sell_ttl = bucket.quantity // 100
                remainder = bucket.quantity % 100
                if sell_ttl:
                    template_result.append(Task.sell_ge(item=item_code, quantity=100, ttl=sell_ttl, sell_price=sell_price))
                if remainder:
                    template_result.append(Task.sell_ge(item=item_code, quantity=remainder, ttl=1, sell_price=sell_price))
                runs += 1

        template_result.append(Task.ensure_inventory(task_id=task.task_id))
        return template_result
