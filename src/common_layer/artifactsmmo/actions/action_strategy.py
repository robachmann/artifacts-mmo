from abc import ABC, abstractmethod
from typing import List, Type

from artifactsmmo.actions.action_result import ActionResult
from artifactsmmo.client.actions import ActionsClient
from artifactsmmo.dynamodb.character_table import CharacterTable
from artifactsmmo.dynamodb.counters_table import CountersTable
from artifactsmmo.dynamodb.skill_stats_table import SkillStatsTable
from artifactsmmo.dynamodb.task_progress_table import TaskProgressTable
from artifactsmmo.extensions import CharacterSchemaExtension
from artifactsmmo.service.execution_context import ExecutionContext
from artifactsmmo.service.food_service import FoodService
from artifactsmmo.service.service import Service
from artifactsmmo.service.tasks import Task
from artifactsmmo.telegram.client import TelegramClient


class ActionStrategy(ABC):
    _registry: List[Type['ActionStrategy']] = []

    def __init_subclass__(cls, **kwargs):
        super().__init_subclass__(**kwargs)
        if cls.__name__ != 'ActionStrategy':
            ActionStrategy._registry.append(cls)

    @classmethod
    def all_actions(cls) -> List[Type['ActionStrategy']]:
        return list(cls._registry)

    def __init__(
        self,
        actions_client: ActionsClient,
        service: Service,
        counters_table: CountersTable,
        telegram_client: TelegramClient,
        task_progress_table: TaskProgressTable,
        skill_stats_table: SkillStatsTable,
        food_service: FoodService,
        character_table: CharacterTable,
    ):
        self.actions_client = actions_client
        self.service = service
        self.counters_table = counters_table
        self.telegram_client = telegram_client
        self.task_progress_table = task_progress_table
        self.skill_stats_table = skill_stats_table
        self.food_service = food_service
        self.character_table = character_table

    @abstractmethod
    def action(self) -> str:
        pass

    @abstractmethod
    def process(self, character: CharacterSchemaExtension, task: Task, quest_id: str = None, context: ExecutionContext = None) -> ActionResult:
        pass

    @staticmethod
    def describe_task(task: Task) -> str:
        return str(task.extra or '')
