from typing import Optional

from artifactsmmo.extensions import CharacterSchemaExtension
from artifactsmmo.log.logger import logger
from artifactsmmo.service.execution_context import ExecutionContext
from artifactsmmo.service.helpers import BucketFiller
from artifactsmmo.service.tasks import NextMove, Task
from artifactsmmo.templates.template_result import TemplateResult
from artifactsmmo.templates.template_strategy import TemplateStrategy


class SellToNpcTemplate(TemplateStrategy):
    def template(self) -> str:
        return 'sell-to-npc'

    @staticmethod
    def describe_task(task: Task) -> str:
        return f'{task.extra.get("quantity")}x {task.extra.get("item")} to {task.extra.get("npc")}'

    def render(self, character: CharacterSchemaExtension, task: Task, quest_id: str = None, context: ExecutionContext = None) -> TemplateResult:
        template_result: TemplateResult = TemplateResult()
        extra = task.extra
        item_code = extra['item']
        quantity = extra['quantity']
        npc_code = extra['npc']
        map_id = extra['map_id']
        event_end_ts: Optional[int] = extra.get('event_end_ts')

        template_result.append(Task.ensure_inventory(task_id=task.task_id))
        teleport_item_codes = self.service.get_teleport_item_codes()
        sell_bucket: BucketFiller = BucketFiller(character.inventory_capacity(teleport_item_codes))

        if quantity > 0:
            bank_items_map = self.service.get_bank_items_map(task_id=task.task_id, character_name=character.name)
            npc = self.service.get_npc(npc_code)
            item = npc.items.get(item_code)
            if item:
                if item.sell_price is not None:
                    quantity_available = bank_items_map.get(item_code, 0)
                    if quantity > quantity_available:
                        logger.warning(
                            f'Insufficient quantity of item={item.code} available at bank, quantity to sell: {quantity}, quantity_available={quantity_available}. '
                            f'Setting quantity to {quantity_available}'
                        )
                        quantity = quantity_available

                    if map_id:
                        next_move = NextMove(map_id=map_id)
                    else:
                        next_move = NextMove(content_type='npc', content_code=npc_code)

                    if quantity > 0:
                        for bucket in sell_bucket.generate_buckets(quantity):
                            item_map = {item_code: bucket.quantity}
                            task = Task.ensure_inventory(item_map=item_map, task_id=task.task_id, next_move=next_move)
                            template_result.append(task)
                            sell_ttl = bucket.quantity // 100
                            remainder = bucket.quantity % 100
                            if sell_ttl > 0:
                                template_result.append(
                                    Task.sell_npc(item=item_code, quantity=100, ttl=sell_ttl, npc=npc_code, event_end_ts=event_end_ts)
                                )
                            if remainder > 0:
                                template_result.append(
                                    Task.sell_npc(item=item_code, quantity=remainder, ttl=1, npc=npc_code, event_end_ts=event_end_ts)
                                )

                        logger.info(f'Plan to sell {quantity}x {item_code} to npc={npc_code}, total_gold={quantity * item.sell_price}')
                else:
                    logger.error(f'Item={item_code} cannot be sold.')
        return template_result
