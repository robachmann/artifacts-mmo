from collections import defaultdict

from artifactsmmo.client.client import Client
from artifactsmmo.dynamodb.character_table import CharacterTable
from artifactsmmo.dynamodb.equipment_lock_table import EquipmentLockTable
from artifactsmmo.dynamodb.skill_stats_table import SkillStatsTable
from artifactsmmo.dynamodb.task_progress_table import TaskProgressTable
from artifactsmmo.extensions import CharacterSchemaExtension
from artifactsmmo.log.logger import logger
from artifactsmmo.queue.dispatcher_queue import DispatcherQueue
from artifactsmmo.queue.worker_queue import WorkerQueue
from artifactsmmo.service.dispatch_service import DispatchService
from artifactsmmo.service.execution_context import ExecutionContext
from artifactsmmo.service.fight_simulator import FightSimulator
from artifactsmmo.service.food_service import FoodService
from artifactsmmo.service.service import Service
from artifactsmmo.service.tasks import Task
from artifactsmmo.telegram.client import TelegramClient
from artifactsmmo.templates.template_result import TemplateResult
from artifactsmmo.templates.template_strategy import TemplateStrategy


class ClaimPendingItemsTemplate(TemplateStrategy):
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
        self.task_progress_table = TaskProgressTable()

    def template(self) -> str:
        return 'claim-pending-items'

    @staticmethod
    def describe_task(task: Task) -> str:
        return ''

    def render(self, character: CharacterSchemaExtension, task: Task, quest_id: str = None, context: ExecutionContext = None) -> TemplateResult:
        template_result: TemplateResult = TemplateResult()

        pending_items = self.service.get_pending_items()
        if pending_items:
            remaining_space = character.inventory_max_items - character.inventory_map.total()
            shopping_cart = defaultdict(int)
            for pending_item in pending_items:
                required_space = sum(i.quantity for i in pending_item.items)
                if required_space < remaining_space:
                    remaining_space -= required_space
                    template_result.append(Task.claim_pending_item(pending_item.id))
                    for item in pending_item.items:
                        shopping_cart[item.code] += item.quantity
                    shopping_cart['g'] += pending_item.gold

            logger.info(f'Plan to claim pending items: {shopping_cart}')

        return template_result
