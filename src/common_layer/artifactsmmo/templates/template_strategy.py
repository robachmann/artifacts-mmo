from abc import ABC, abstractmethod
from typing import List, Type

from artifactsmmo.client.client import Client
from artifactsmmo.dynamodb.character_table import CharacterTable
from artifactsmmo.dynamodb.equipment_lock_table import EquipmentLockTable
from artifactsmmo.dynamodb.fight_simulator_table import FightSimulatorTable
from artifactsmmo.dynamodb.skill_stats_table import SkillStatsTable
from artifactsmmo.extensions import CharacterSchemaExtension
from artifactsmmo.queue.dispatcher_queue import DispatcherQueue
from artifactsmmo.queue.fight_simulator_queue import FightSimulatorQueue
from artifactsmmo.queue.worker_queue import WorkerQueue
from artifactsmmo.service.async_fight_simulator_service import AsyncFightSimulatorService
from artifactsmmo.service.dispatch_service import DispatchService
from artifactsmmo.service.execution_context import ExecutionContext
from artifactsmmo.service.fight_simulator import FightSimulator
from artifactsmmo.service.food_service import FoodService
from artifactsmmo.service.service import Service
from artifactsmmo.service.tasks import Task
from artifactsmmo.telegram.client import TelegramClient
from artifactsmmo.templates.template_result import TemplateResult


class TemplateStrategy(ABC):
    _registry: List[Type['TemplateStrategy']] = []

    def __init_subclass__(cls, **kwargs):
        super().__init_subclass__(**kwargs)
        if cls.__name__ != 'TemplateStrategy':
            TemplateStrategy._registry.append(cls)

    @classmethod
    def all_templates(cls) -> List[Type['TemplateStrategy']]:
        return list(cls._registry)

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
        self.client = client
        self.service = service
        self.equipment_lock_table = equipment_lock_table
        self.telegram_client = telegram_client
        self.character_table = character_table
        self.skill_stats_table = skill_stats_table
        self.dispatch_service = dispatch_service
        self.dispatcher_queue = dispatcher_queue
        self.worker_queue = worker_queue
        self.food_service = food_service
        self.fight_simulator = fight_simulator
        self.fight_simulator_table = FightSimulatorTable()
        self.async_fight_simulator_service = AsyncFightSimulatorService(self.fight_simulator_table, FightSimulatorQueue())

    @abstractmethod
    def template(self) -> str:
        pass

    @abstractmethod
    def render(self, character: CharacterSchemaExtension, task: Task, quest_id: str = None, context: ExecutionContext = None) -> TemplateResult:
        pass

    @staticmethod
    def describe_task(task: Task) -> str:
        return str(task.extra or '')
