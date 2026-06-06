from artifactsmmo import game_constants
from artifactsmmo.extensions import CharacterSchemaExtension
from artifactsmmo.game_constants import TASK_COINS_RESERVE
from artifactsmmo.log.logger import logger
from artifactsmmo.service.execution_context import ExecutionContext
from artifactsmmo.service.helpers import BucketFiller
from artifactsmmo.service.tasks import NextMove, Task
from artifactsmmo.templates.template_result import TemplateResult
from artifactsmmo.templates.template_strategy import TemplateStrategy


class ExchangeTaskCoinsTemplate(TemplateStrategy):
    def template(self) -> str:
        return 'exchange-task-coins'

    @staticmethod
    def describe_task(task: Task) -> str:
        return f'for {task.extra.get("reward")}' if task.extra.get('reward') else ''

    def render(self, character: CharacterSchemaExtension, task: Task, quest_id: str = None, context: ExecutionContext = None) -> TemplateResult:
        template_result: TemplateResult = TemplateResult()
        reward_code = task.extra.get('reward')

        bank_item_map = self.service.get_bank_items_map(task_id=task.task_id, character_name=character.name)
        task_coin_count = bank_item_map.get('tasks_coin', 0)
        task_coin_count -= TASK_COINS_RESERVE
        exchange_rate = game_constants.TASK_COIN_EXCHANGE_RATE
        if task_coin_count >= exchange_rate:
            if reward_code:
                origin = self.service.get_item_origin(reward_code)
                if origin and origin.npcs:
                    for npc_code, npc_item in origin.npcs.items():
                        if npc_item.currency == 'tasks_coin' and not npc_item.is_event:
                            quantity = task_coin_count // npc_item.price
                            template_result.append(Task.buy_from_npc(item=reward_code, npc=npc_code, quantity=quantity))
                            logger.info(
                                f'Plan to buy {quantity}x {reward_code} from {npc_code} for {quantity * npc_item.price} {npc_item.currency}'
                            )
                            break
                else:
                    logger.error(f'Supplied reward_code={reward_code} cannot be obtained from NPCs.')
            else:
                teleport_item_codes = self.service.get_teleport_item_codes()
                character_capacity = character.inventory_capacity(teleport_item_codes)
                inventory_max_items = character_capacity - exchange_rate
                bucket_max_size = inventory_max_items - inventory_max_items % exchange_rate
                bucket_filler = BucketFiller(bucket_max_size)

                for bucket in bucket_filler.generate_buckets(task_coin_count):
                    quantity = bucket.quantity - bucket.quantity % exchange_rate
                    item_map = {'tasks_coin': quantity}
                    task = Task.ensure_inventory(item_map=item_map, task_id=task.task_id, next_move=NextMove(content_type='tasks_master'))
                    template_result.append(task)
                    template_result.append(Task.exchange(ttl=quantity // exchange_rate))

        return template_result
