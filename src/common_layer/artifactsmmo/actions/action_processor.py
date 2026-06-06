from typing import Dict

from artifactsmmo.actions import load_all_action_modules
from artifactsmmo.actions.action_result import ActionResult
from artifactsmmo.actions.action_strategy import ActionStrategy
from artifactsmmo.client.actions import ActionsClient
from artifactsmmo.dynamodb.character_table import CharacterTable
from artifactsmmo.dynamodb.counters_table import CountersTable
from artifactsmmo.dynamodb.skill_stats_table import SkillStatsTable
from artifactsmmo.dynamodb.task_progress_table import TaskProgressTable
from artifactsmmo.extensions import CharacterSchemaExtension
from artifactsmmo.log.logger import logger
from artifactsmmo.service.execution_context import ExecutionContext
from artifactsmmo.service.food_service import FoodService
from artifactsmmo.service.service import Service
from artifactsmmo.service.tasks import Task
from artifactsmmo.telegram.client import TelegramClient


class ActionProcessor:
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
        load_all_action_modules()
        strategies = []
        for cls in ActionStrategy.all_actions():
            strategies.append(
                cls(
                    actions_client,
                    service,
                    counters_table,
                    telegram_client,
                    task_progress_table,
                    skill_stats_table,
                    food_service,
                    character_table,
                )
            )

        self.strategies: Dict[str, ActionStrategy] = {s.action(): s for s in strategies}

    def process(self, task: Task, character: CharacterSchemaExtension, quest_id: str = None, context: ExecutionContext = None) -> ActionResult:
        strategy = self.strategies.get(task.action)
        if strategy:
            return strategy.process(character, task, quest_id, context)
        else:
            logger.error(f'No strategy implemented for action={task.action}')
            action_result: ActionResult = ActionResult()
            action_result.abort()
            return action_result

    def describe_task(self, task: Task) -> str:
        strategy = self.strategies.get(task.action)
        if strategy is None:
            logger.error(f'No strategy implemented for action={task.action}')
            return ''
        else:
            return strategy.describe_task(task)
