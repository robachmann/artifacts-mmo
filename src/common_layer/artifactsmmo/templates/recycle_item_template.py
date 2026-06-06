from typing import Dict

from artifactsmmo.extensions import CharacterSchemaExtension
from artifactsmmo.log.logger import logger
from artifactsmmo.service.execution_context import ExecutionContext
from artifactsmmo.service.helpers import BucketFiller
from artifactsmmo.service.tasks import NextMove, Task
from artifactsmmo.templates.template_result import TemplateResult
from artifactsmmo.templates.template_strategy import TemplateStrategy


class RecycleItemTemplate(TemplateStrategy):
    def template(self) -> str:
        return 'recycle-item'

    @staticmethod
    def describe_task(task: Task) -> str:
        item_code = task.extra.get('item')
        if task.extra.get('keep_quantity') and not task.extra.get('quantity'):
            return f'all of {item_code} except {task.extra.get("keep_quantity")}'
        elif task.extra.get('quantity'):
            return f'{task.extra.get("quantity")}x {item_code}'
        else:
            return item_code

    def render(self, character: CharacterSchemaExtension, task: Task, quest_id: str = None, context: ExecutionContext = None) -> TemplateResult:
        template_result: TemplateResult = TemplateResult()
        extra = task.extra
        item_code = extra.get('item')
        keep_quantity = extra.get('keep_quantity')
        should_recraft = bool(extra.get('recraft', False))
        if extra.get('quantity'):
            quantity = int(extra.get('quantity'))
        else:
            quantity = None
        keep_map: Dict[str, int] = task.extra.get('keep_map')
        if keep_map:
            for i, q in keep_map.items():
                template_result.append(Task.recycle_item(item=i, keep_quantity=q))
        else:
            if not quantity:
                if keep_quantity is not None:
                    global_quantity = self.service.get_global_quantity(item_code)
                    quantity = max(0, global_quantity - keep_quantity)
                    logger.info(f'item_code={item_code}, global_quantity: {global_quantity}, keep_quantity={keep_quantity}, quantity={quantity}')
                else:
                    quantity = 1
            else:
                global_quantity = self.service.get_global_quantity(item_code)
                quantity = min(global_quantity, quantity)

            bank_items_map = self.service.get_bank_items_map(context=context, task_id=task.task_id, character_name=character.name)
            quantity = min(quantity, bank_items_map.get(item_code, 0))

            if quantity > 0:
                item = self.service.get_item(item_code)
                if item.craft:
                    skill = str(item.craft.skill)
                    skill_level = item.craft.level
                    if character.skills[skill].level >= skill_level:
                        logger.info(f'Plan to recycle {quantity}x {item_code} at {skill} workshop.')
                        workshop_move = NextMove(content_type='workshop', content_code=skill)
                        divider = max(len(item.craft.items), 1)
                        teleport_item_codes = self.service.get_teleport_item_codes()
                        character_capacity = character.inventory_capacity(teleport_item_codes)
                        bank_withdraw_bucket: BucketFiller = BucketFiller(character_capacity // divider)
                        for bank_bucket in bank_withdraw_bucket.generate_buckets(quantity):
                            item_map = {item_code: bank_bucket.quantity}
                            task = Task.ensure_inventory(item_map=item_map, task_id=task.task_id, next_move=workshop_move)
                            template_result.append(task)
                            logger.info(f'Added ensure_inventory task: item_map={item_map}, next_move={workshop_move}')
                            template_result.append(Task.recycle(item=item_code, quantity=bank_bucket.quantity, recraft=should_recraft))
                    else:
                        logger.warning(
                            f'{character.name} cannot recycle {quantity}x {item_code} (required skill={skill} at level={skill_level}).'
                        )
                else:
                    logger.info(f'Item {item_code} cannot be recycled.')

        return template_result
