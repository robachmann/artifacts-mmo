from typing import List

from artifactsmmo.extensions import CharacterSchemaExtension
from artifactsmmo.models import AccountAchievementSchema, AchievementType, TaskType
from artifactsmmo.service.execution_context import ExecutionContext
from artifactsmmo.service.tasks import Task
from artifactsmmo.templates.template_result import TemplateResult
from artifactsmmo.templates.template_strategy import TemplateStrategy


class SolveTasksAchievementsTemplate(TemplateStrategy):
    def template(self) -> str:
        return 'solve-tasks-achievements'

    @staticmethod
    def describe_task(task: Task) -> str:
        return f'of type {task.extra.get("type")}' if task.extra.get('type') else ''

    def render(self, character: CharacterSchemaExtension, task: Task, quest_id: str = None, context: ExecutionContext = None) -> TemplateResult:
        template_result: TemplateResult = TemplateResult()

        task_type = task.extra.get('type')
        task_type = task_type or TaskType.MONSTERS

        achievements: List[AccountAchievementSchema] = self.service.get_account_achievements(character.account)
        remaining_tasks_count = 0
        for achievement in achievements:
            for objective in achievement.objectives:
                if objective.type == AchievementType.TASK:
                    remaining_tasks_count = max(remaining_tasks_count, objective.total - objective.progress)

        if remaining_tasks_count > 0:
            last_idx = min(10, remaining_tasks_count)
            for idx in range(last_idx):
                template_result.append(
                    Task.solve_task(
                        allow_cancellation=True,
                        task_type=task_type,
                        deposit_coins=idx == last_idx,
                        task_id=Task.generate_task_id(),
                    )
                )

        if len(template_result.new_tasks) == 10:
            template_result.repeat()

        return template_result
