from artifactsmmo.extensions import CharacterSchemaExtension
from artifactsmmo.game_constants import MAX_LEVEL
from artifactsmmo.log.logger import logger
from artifactsmmo.models import ActionType, Skill
from artifactsmmo.service.execution_context import ExecutionContext
from artifactsmmo.service.tasks import Task
from artifactsmmo.templates.template_result import TemplateResult
from artifactsmmo.templates.template_strategy import TemplateStrategy


class LevelSkillTemplate(TemplateStrategy):
    def template(self) -> str:
        return 'level-skill'

    @staticmethod
    def describe_task(task: Task) -> str:
        stock_only_str = ' with available parts only' if bool(task.extra.get('stock_only', False)) else ''
        if task.extra.get('level'):
            return f'{task.extra.get("skill")} to {task.extra.get("level")}{stock_only_str}'
        else:
            return f'{task.extra.get("skill")} to the next level{stock_only_str}'

    def render(self, character: CharacterSchemaExtension, task: Task, quest_id: str = None, context: ExecutionContext = None) -> TemplateResult:
        template_result: TemplateResult = TemplateResult()
        extra = task.extra
        skill = extra['skill']
        target_level = extra.get('level')
        stock_only = bool(extra.get('stock_only', False))
        allow_task_parts = bool(extra.get('allow_task_parts', False))
        allow_event_parts = bool(extra.get('allow_event_parts', False))
        item_code = extra.get('item')
        request_support = bool(extra.get('request_support', False))
        level_approach = extra.get('level_approach') or ActionType.GATHERING

        current_level = character.skills[skill].level
        if target_level is None:
            target_level = min(current_level + 1, MAX_LEVEL)

        if current_level >= target_level:
            return template_result

        should_gather = True
        match skill:
            case Skill.MINING | Skill.WOODCUTTING | Skill.ALCHEMY:
                should_gather = level_approach == ActionType.GATHERING

            case Skill.WEAPONCRAFTING | Skill.GEARCRAFTING | Skill.JEWELRYCRAFTING | Skill.COOKING:
                should_gather = False

            case Skill.FISHING:
                should_gather = True

            case _:
                logger.error(f'Unknown skill to level: {skill}')

        if should_gather:
            template_result.append(Task.level_gathering_skill(skill, target_level))
        else:
            template_result.append(
                Task.level_crafting_skill(
                    skill=skill,
                    target_level=target_level,
                    request_support=request_support,
                    stock_only=stock_only,
                    allow_task_parts=allow_task_parts,
                    allow_event_parts=allow_event_parts,
                    item=item_code,
                )
            )

        return template_result
