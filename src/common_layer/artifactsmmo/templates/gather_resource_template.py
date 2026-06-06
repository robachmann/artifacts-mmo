import random
from typing import List

from artifactsmmo.extensions import CharacterSchemaExtension
from artifactsmmo.extensions.resource_schema_extension import ResourceSchemaExtension
from artifactsmmo.log.logger import logger
from artifactsmmo.service.execution_context import ExecutionContext
from artifactsmmo.service.tasks import Task
from artifactsmmo.templates.template_result import TemplateResult
from artifactsmmo.templates.template_strategy import TemplateStrategy


class GatherResourceTemplate(TemplateStrategy):
    def template(self) -> str:
        return 'gather-resource'

    @staticmethod
    def describe_task(task: Task) -> str:
        if task.until:
            if task.until.drop_item:
                return f'{task.until.drop_item} at {task.extra.get("resource")} ({task.until.progress}/{task.until.drop_count})'
            elif task.until.skill_name and task.until.skill_level:
                return f'{task.extra.get("resource")} until {task.until.skill_name} level {task.until.skill_level}'
            elif task.until.achievement_code:
                return f'{task.extra.get("resource")} until {task.until.achievement_code} is solved'
        return f'{task.extra.get("resource")}'

    def render(self, character: CharacterSchemaExtension, task: Task, quest_id: str = None, context: ExecutionContext = None) -> TemplateResult:
        template_result: TemplateResult = TemplateResult()
        extra = task.extra
        resource_code = extra.get('resource')
        quantity = int(extra.get('quantity') or 1)
        craft = extra.get('craft')

        if quantity > 0 or task.until:
            if resource_code:
                resource: ResourceSchemaExtension = self.service.get_resource(resource_code)

                required_skill = str(resource.skill)
                current_skill_level = character.skills[required_skill].level
                required_skill_level = resource.level

                if current_skill_level < required_skill_level:
                    template_result.append(Task.level_skill(required_skill, required_skill_level))
                    template_result.repeat(until=task.until)
                    logger.info(
                        f'Plan to level skill={required_skill} from current_skill_level={current_skill_level} '
                        f'to required_skill_level={required_skill_level} to gather from location={resource.code}.'
                        f' Repeat template afterwards.'
                    )
                else:
                    gather_tasks: List[Task] = []
                    start_gathering = True
                    if quantity > 15 or task.until:
                        gear_positions: List[str] = self.service.get_confining_gear_positions(character)
                        for gear_position in gear_positions:
                            template_result.append(Task.unequip(slot=gear_position))

                        lock_acquired = self.equipment_lock_table.acquire_lock(character.name)
                        if lock_acquired:
                            bank_items_map = self.service.get_bank_items_map(task_id=task.task_id, character_name=character.name)
                            equip_prospecting_gear = False if task.until and task.until.skill_name else True
                            equip_map = self.service.get_gather_equipment(resource.skill, character, bank_items_map, equip_prospecting_gear)

                            if equip_map:
                                reservation_id = self.service.reserve_equipment(character, equip_map)
                                logger.info(f'Plan to equip {equip_map} to gather {resource.code} more efficiently.')
                                gather_tasks.append(Task.equip_items(items_map=equip_map, task_id=reservation_id))
                            self.equipment_lock_table.release_lock(character.name)
                        else:
                            template_result.append(Task.sleep(seconds=random.randint(15, 20)))
                            template_result.repeat(until=task.until)
                            start_gathering = False

                    if start_gathering:
                        gather_tasks.append(Task.move(content_type='resource', content_code=resource_code))
                        gather_tasks.append(
                            Task.gather(
                                task_id=task.task_id,
                                skill=str(resource.skill),
                                resource=resource.code,
                                ttl=quantity,
                                until=task.until,
                                craft=craft,
                            )
                        )
                        if task.until is None:
                            logger.info(f'Plan to gather {quantity}x {resource.code}.')
                        else:
                            if task.until.date_time:
                                logger.info(f'Plan to gather {resource.code} until date_time={task.until.date_time}.')
                            elif task.until.drop_count:
                                logger.info(f'Plan to gather {resource.code} until drop_count={task.until.drop_count}.')
                            elif task.until.skill_name and task.until.skill_level:
                                logger.info(f'Plan to gather {resource.code} until skill_level={task.until.skill_level}.')
                            elif task.until.achievement_code:
                                template_result.status = 'Solving achievement ' + task.until.achievement_code
                                logger.info(f'Plan to gather {resource.code} until achievement={task.until.achievement_code} is solved.')

                        template_result.extend(gather_tasks)
            else:
                logger.warning('item is None, cannot create gather recipe')

        task.until = None
        return template_result
