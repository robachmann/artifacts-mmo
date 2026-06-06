from collections import defaultdict
from datetime import timedelta

from artifactsmmo.extensions import CharacterSchemaExtension
from artifactsmmo.game_constants import MAX_LEVEL
from artifactsmmo.log.logger import logger
from artifactsmmo.models import GatheringSkill
from artifactsmmo.service.execution_context import ExecutionContext
from artifactsmmo.service.tasks import Task
from artifactsmmo.service.until import Until
from artifactsmmo.templates.template_result import TemplateResult
from artifactsmmo.templates.template_strategy import TemplateStrategy


class EnsureHealingCapacityTemplate(TemplateStrategy):
    def template(self) -> str:
        return 'ensure-healing-capacity'

    @staticmethod
    def describe_task(task: Task) -> str:
        return ''

    def render(self, character: CharacterSchemaExtension, task: Task, quest_id: str = None, context: ExecutionContext = None) -> TemplateResult:
        template_result: TemplateResult = TemplateResult()
        gather_hours = task.extra.get('gather_hours', 4)
        gather_quantity = task.extra.get('gather_quantity', 250)
        min_level = task.extra.get('min_level') or 1
        max_level = task.extra.get('max_level') or MAX_LEVEL

        resources = self.service.get_resources_by_skill(GatheringSkill.FISHING)
        food_items = self.service.get_processed_food()

        food_resources = {}
        for food in food_items:
            for resource in resources:
                if food.craft and food.craft.items and len(food.craft.items) == 1:
                    for craft in food.craft.items:
                        for drop in resource.drops:
                            if craft.code == drop.code:
                                food_resources[food.level] = dict(resource=resource.code, food=food.code, skill=resource.skill)

        character_levels = defaultdict(int)
        for c in self.service.get_all_character_details():
            character_level = c.level
            if character_level < min_level:
                character_level = min_level
            elif character_level > max_level:
                character_level = max_level
            level_index = max(1, (character_level // 10) * 10)
            character_levels[level_index] += 1

        gather_duration = 0
        character_levels = dict(sorted(character_levels.items()))
        for idx, (level_index, level_count) in enumerate(character_levels.items(), 1):
            food = food_resources[level_index]
            if level_index <= character.skills[food['skill']].level:
                gather_duration += level_count * idx * gather_hours
                template_result.extend(
                    [
                        Task.gather_recipe(food['food'], quantity=gather_quantity * level_count, global_max=gather_quantity * level_count),
                        Task.gather_resource(food['resource'], until=Until(timespan=timedelta(hours=gather_duration))),
                    ]
                )
                logger.info(
                    f'Plan to ensure {gather_quantity * level_count}x {food["food"]} and gather from {food["resource"]} for '
                    f'{gather_duration} hours.'
                )
            else:
                template_result.append(Task.level_gathering_skill(food['skill'], level_index))
                logger.info(f'Plan to level skill {food["skill"]} to level {level_index}')
        return template_result
