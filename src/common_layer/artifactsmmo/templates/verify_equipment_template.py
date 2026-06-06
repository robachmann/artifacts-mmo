from typing import Dict

from artifactsmmo.extensions import CharacterSchemaExtension
from artifactsmmo.game_constants import GEAR_POSITIONS
from artifactsmmo.log.logger import logger
from artifactsmmo.service.execution_context import ExecutionContext
from artifactsmmo.service.tasks import Task
from artifactsmmo.templates.template_result import TemplateResult
from artifactsmmo.templates.template_strategy import TemplateStrategy


class VerifyEquipmentTemplate(TemplateStrategy):
    def template(self) -> str:
        return 'verify-equipment'

    @staticmethod
    def describe_task(task: Task) -> str:
        return ''

    def render(self, character: CharacterSchemaExtension, task: Task, quest_id: str = None, context: ExecutionContext = None) -> TemplateResult:
        template_result: TemplateResult = TemplateResult()
        items_map: Dict[str, str] = task.extra.get('items_map')
        retry_task = bool(task.extra.get('retry_task', True))

        diffs = []
        for position in GEAR_POSITIONS:
            if position in items_map:
                if items_map[position] != character.equipment.get(position):
                    diffs.append(dict(slot=position, expected=items_map[position], actual=character.equipment.get(position)))

        if not diffs:
            logger.info('Equipment verification succeeded')
        else:
            if retry_task:
                logger.warning(f'Equipment verification failed, will retry: {diffs}')
                template_result.append(Task.equip_items(items_map, task.task_id))
            else:
                logger.error(f'Equipment verification failed, will not retry: {diffs}')

        return template_result
