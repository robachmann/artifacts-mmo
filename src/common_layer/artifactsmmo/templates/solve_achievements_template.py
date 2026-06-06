from typing import List

from artifactsmmo.extensions import CharacterSchemaExtension
from artifactsmmo.log.logger import logger
from artifactsmmo.models import AccountAchievementObjectiveSchema, AccountAchievementSchema, AchievementType
from artifactsmmo.service.execution_context import ExecutionContext
from artifactsmmo.service.tasks import Task
from artifactsmmo.service.until import Until
from artifactsmmo.templates.template_result import TemplateResult
from artifactsmmo.templates.template_strategy import TemplateStrategy


class SolveAchievementsTemplate(TemplateStrategy):
    def template(self) -> str:
        return 'solve-achievements'

    @staticmethod
    def describe_task(task: Task) -> str:
        return f'of type {task.extra.get("type")}' if task.extra.get('type') else ''

    def render(self, character: CharacterSchemaExtension, task: Task, quest_id: str = None, context: ExecutionContext = None) -> TemplateResult:
        template_result: TemplateResult = TemplateResult()
        achievement_type = task.extra.get('type')
        ignore_achievements = task.extra.get('ignore_achievements') or []

        achievements: List[AccountAchievementSchema] = self.client.get_account_achievements(character.account)

        for achievement in achievements:
            if not achievement.completed_at and achievement.code not in ignore_achievements:
                for objective in achievement.objectives:
                    if not achievement_type or str(objective.type) == achievement_type:
                        found = self.handle_incomplete_achievement(template_result, character, achievement, objective)
                        if found:
                            break

        return template_result

    def handle_incomplete_achievement(
        self,
        template_result: TemplateResult,
        character: CharacterSchemaExtension,
        achievement: AccountAchievementSchema,
        objective: AccountAchievementObjectiveSchema,
    ) -> bool:
        match objective.type:
            case AchievementType.GATHERING:
                return self.gathering_achievement(template_result, character, achievement, objective)
        return False

    def gathering_achievement(
        self,
        template_result: TemplateResult,
        character: CharacterSchemaExtension,
        achievement: AccountAchievementSchema,
        objective: AccountAchievementObjectiveSchema,
    ) -> bool:
        remaining_quantity = objective.total - objective.progress
        item = self.service.get_item(objective.target)

        if not self.service.is_event_content(item.code) and not self.service.is_event_resource_drop(item.code):
            if character.skills[item.subtype].level >= item.level:
                if item.type == 'resource':
                    origin = self.service.get_item_origin(item.code)
                    for resource_code, drop in sorted(origin.resources.items(), key=lambda i: i[1].drop_rate):
                        if not drop.is_event:
                            resource = self.service.get_resource(resource_code)
                            if character.skills[str(resource.skill)].level >= resource.level:
                                gather_task = Task.gather_resource(resource=resource_code, until=Until(achievement_code=achievement.code))
                                template_result.append(gather_task)
                                logger.info(f'Plan to gather resource {resource_code} until achievement {achievement.code} is solved.')
                                break
                else:
                    gather_task = Task.gather_recipe(
                        item=item.code,
                        quantity=remaining_quantity,
                        task_id=Task.generate_task_id(),
                        leader=character.name,
                    )
                    template_result.append(gather_task)
                return True

        return False
