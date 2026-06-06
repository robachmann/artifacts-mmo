from artifactsmmo.extensions import CharacterSchemaExtension
from artifactsmmo.game_constants import MAX_LEVEL
from artifactsmmo.log.logger import logger
from artifactsmmo.service.execution_context import ExecutionContext
from artifactsmmo.service.tasks import Task
from artifactsmmo.service.until import Until
from artifactsmmo.templates.template_result import TemplateResult
from artifactsmmo.templates.template_strategy import TemplateStrategy


class LevelGatheringSkillTemplate(TemplateStrategy):
    def template(self) -> str:
        return 'level-gathering-skill'

    @staticmethod
    def describe_task(task: Task) -> str:
        if task.extra.get('level'):
            return f'{task.extra.get("skill")} to {task.extra.get("level")}'
        else:
            return f'{task.extra.get("skill")} to the next level'

    def render(self, character: CharacterSchemaExtension, task: Task, quest_id: str = None, context: ExecutionContext = None) -> TemplateResult:
        template_result: TemplateResult = TemplateResult()
        extra = task.extra
        skill = extra['skill']
        target_level = extra.get('level')

        current_level = character.skills[skill].level
        if target_level is None:
            target_level = min(current_level + 1, MAX_LEVEL)

        if current_level >= target_level:
            return template_result

        min_level = max(1, current_level - 10)
        target_level_step = target_level
        eligible_resources = self.service.get_resources_by_level(min_level, target_level - 1, skill, include_event_resources=False)
        gather_resource_tasks = []
        for resource in eligible_resources:
            level_step = min(resource.level + 10, target_level_step)

            resource_item = None
            for resource_item_candidate in self.service.get_items_by_type('resource', resource.level):
                if (
                    resource_item_candidate.level == resource.level
                    and resource_item_candidate.craft
                    and resource_item_candidate.craft.skill == resource.skill
                    and len(resource_item_candidate.craft.items) == 1
                ):
                    resource_item = resource_item_candidate
                    break

            craft_code = None
            if resource_item:
                craft = resource_item.craft.items[0]
                for drop in resource.drops:
                    if drop.rate == 1 and drop.code == craft.code:
                        craft_code = resource_item.code
                        break

            if current_level < level_step:
                gather_resource_tasks.insert(
                    0,
                    Task.gather_resource(resource=resource.code, until=Until(skill_name=skill, skill_level=level_step), craft=craft_code),
                )
                target_level_step = resource.level

        if not gather_resource_tasks:
            logger.warning(f'No eligible resources found for min_level={min_level}, max_level={current_level}, skill={skill}.')
        else:
            first_step_task: Task = gather_resource_tasks[0]
            if first_step_task.action == 'gather-resource' and first_step_task.until.skill_level - current_level > 10:
                template_result.append(Task.level_crafting_skill(skill=skill, target_level=first_step_task.until.skill_level - 10))
                logger.info(f'Plan to level crafting skill={skill} until level_step={first_step_task.until.skill_level - 10}')

            template_result.append(Task.equip_wisdom_gear(task_id=task.task_id))
            target_level_step = current_level
            next_skill_level = None
            for task in gather_resource_tasks:
                if task.until:
                    until_skill_level = task.until.skill_level
                    # if target_level_step < until_skill_level <= target_level_step + 10:
                    template_result.append(task)
                    logger.info(f'Plan to gather resource={task.extra.get("resource")} until level_step={until_skill_level}')
                    if not next_skill_level:
                        next_skill_level = until_skill_level
                    target_level_step = until_skill_level

            if next_skill_level:
                template_result.quest_status(f'Level {skill} to {next_skill_level}')

            if not template_result.new_tasks:
                logger.error(f'Cannot find resource to level skill={skill} from level={current_level} to target_level={target_level}.')

        return template_result
