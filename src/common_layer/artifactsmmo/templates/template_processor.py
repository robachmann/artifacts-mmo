from typing import Dict

from artifactsmmo.client.client import Client
from artifactsmmo.dynamodb.character_table import CharacterTable
from artifactsmmo.dynamodb.equipment_lock_table import EquipmentLockTable
from artifactsmmo.dynamodb.skill_stats_table import SkillStatsTable
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
from artifactsmmo.templates import load_all_template_modules
from artifactsmmo.templates.template_result import TemplateResult
from artifactsmmo.templates.template_strategy import TemplateStrategy


class TemplateProcessor:
    def __init__(self, client: Client, service: Service, telegram_client: TelegramClient, food_service: FoodService):
        skill_stats_table = SkillStatsTable()
        dispatcher_queue = DispatcherQueue()
        equipment_lock_table = EquipmentLockTable()
        character_table = CharacterTable()
        worker_queue = WorkerQueue()
        dispatch_service = DispatchService(service, character_table, worker_queue)
        fight_simulator = FightSimulator(service)

        load_all_template_modules()
        strategies = []
        for cls in TemplateStrategy.all_templates():
            strategies.append(
                cls(
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
            )

        self.strategies: Dict[str, TemplateStrategy] = {s.template(): s for s in strategies}

    def process(self, task: Task, character: CharacterSchemaExtension, quest_id: str = None, context: ExecutionContext = None) -> TemplateResult:
        strategy = self.strategies.get(task.action)
        if strategy:
            logger.debug('Processing Template: action=%s, extra=%s, id=%s', task.action, task.extra, task.task_id)
            return strategy.render(character, task, quest_id, context)
        else:
            logger.error(f'No strategy implemented for template={task.action}')
            template_result: TemplateResult = TemplateResult()
            return template_result

    def describe_task(self, task: Task) -> str:
        strategy = self.strategies.get(task.action)
        if strategy is None:
            logger.error(f'No strategy implemented for template={task.action}')
            return ''
        else:
            return strategy.describe_task(task)
