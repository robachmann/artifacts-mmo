from typing import Dict, List, Optional

from artifactsmmo.client.client import Client
from artifactsmmo.dynamodb.character_table import CharacterTable
from artifactsmmo.dynamodb.equipment_lock_table import EquipmentLockTable
from artifactsmmo.dynamodb.skill_stats_table import SkillStatsTable
from artifactsmmo.extensions import CharacterSchemaExtension
from artifactsmmo.log.logger import logger
from artifactsmmo.models import BankSchema, NPCItem
from artifactsmmo.queue.dispatcher_queue import DispatcherQueue
from artifactsmmo.queue.worker_queue import WorkerQueue
from artifactsmmo.service.dispatch_service import DispatchService
from artifactsmmo.service.execution_context import ExecutionContext
from artifactsmmo.service.fight_simulator import FightSimulator
from artifactsmmo.service.food_service import FoodService
from artifactsmmo.service.helpers import BucketFiller
from artifactsmmo.service.service import Service
from artifactsmmo.service.tasks import NextMove, Task
from artifactsmmo.telegram.client import TelegramClient
from artifactsmmo.templates.template_result import TemplateResult
from artifactsmmo.templates.template_strategy import TemplateStrategy


class BuyFromNpcTemplate(TemplateStrategy):
    def __init__(
        self,
        client: Client,
        service: Service,
        equipment_lock_table: EquipmentLockTable,
        telegram_client: TelegramClient,
        character_table: CharacterTable,
        skill_stats_table: SkillStatsTable,
        dispatch_service: DispatchService,
        dispatcher_queue: DispatcherQueue,
        worker_queue: WorkerQueue,
        food_service: FoodService,
        fight_simulator: FightSimulator,
    ):
        super().__init__(
            client,
            service,
            equipment_lock_table,
            telegram_client,
            character_table,
            skill_stats_table,
            dispatch_service,
            dispatcher_queue,
            worker_queue,
            food_service,
            fight_simulator,
        )
        self.max_items_per_interaction = 100

    def template(self) -> str:
        return 'buy-from-npc'

    def render(self, character: CharacterSchemaExtension, task: Task, quest_id: str = None, context: ExecutionContext = None) -> TemplateResult:
        template_result: TemplateResult = TemplateResult()
        extra = task.extra
        item_code = extra['item']
        quantity = extra['quantity']
        npc_code = extra['npc']
        map_id = extra['map_id']
        event_end_ts: Optional[int] = extra.get('event_end_ts')

        if quantity > 0:
            bank_details = self.service.get_bank_details()
            bank_items_map = self.service.get_bank_items_map(task_id=task.task_id, character_name=character.name)
            npc = self.service.get_npc(npc_code)
            item = npc.items.get(item_code)
            if item and item.buy_price is not None:
                result = self.add_buy_tasks(item, npc_code, quantity, character, event_end_ts, task, bank_details, bank_items_map, map_id)
                template_result.extend(result)
            else:
                logger.error(f'Item={item_code} cannot be purchased.')
        return template_result

    def add_buy_tasks(
        self,
        item: NPCItem,
        npc_code: str,
        quantity: int,
        character: CharacterSchemaExtension,
        event_end_ts: int,
        task: Task,
        bank_details: BankSchema,
        bank_items_map: Dict[str, int],
        map_id: int,
    ) -> List[Task]:
        result = []

        available_currency = self.__get_available_currency(item, bank_details, character, bank_items_map)
        if item.buy_price * quantity > available_currency:
            logger.info(
                f'Reduced purchase quantity of item={item.code} from {quantity} to {available_currency // item.buy_price} due to missing {item.currency}, '
                f'available={available_currency}, '
                f'initially_required={item.buy_price * quantity}'
            )
            quantity = available_currency // item.buy_price

        if quantity > 0:
            if map_id:
                next_move = NextMove(map_id=map_id)
            else:
                next_move = NextMove(content_type='npc', content_code=npc_code)

            if item.currency == 'gold':
                result.append(Task.ensure_inventory(gold=item.buy_price * quantity, deposit_gold=False, next_move=next_move))

            teleport_item_codes = self.service.get_teleport_item_codes()
            price_per_unit = 1 if item.currency == 'gold' else item.buy_price
            bucket_limit = (character.inventory_capacity(teleport_item_codes) - 1) // price_per_unit
            buy_bucket: BucketFiller = BucketFiller(bucket_limit)
            for bucket in buy_bucket.generate_buckets(quantity):
                if item.currency != 'gold':
                    item_map = {item.currency: item.buy_price * bucket.quantity}
                    result.append(Task.ensure_inventory(item_map, task_id=task.task_id, next_move=next_move))
                else:
                    result.append(Task.ensure_inventory(deposit_gold=False, task_id=task.task_id, next_move=next_move))

                quotient, remainder = divmod(bucket.quantity, self.max_items_per_interaction)
                if quotient:
                    result.append(Task.buy_npc(item.code, npc_code, event_end_ts, self.max_items_per_interaction, quotient))
                if remainder:
                    result.append(Task.buy_npc(item.code, npc_code, event_end_ts, remainder))

            logger.info(f'Plan to buy {quantity}x {item.code} from npc={npc_code}, total_{item.currency}={quantity * item.buy_price}')
        else:
            logger.warning(f'Cannot afford to buy any item={item.code}, required_{item.currency}={item.buy_price}')
        return result

    @staticmethod
    def __get_available_currency(item: NPCItem, bank_details: BankSchema, character: CharacterSchemaExtension, bank_items_map: Dict[str, int]):
        if item.currency == 'gold':
            return bank_details.gold + character.gold
        else:
            return bank_items_map.get(item.currency, 0) + character.inventory_map.get(item.currency, 0)
