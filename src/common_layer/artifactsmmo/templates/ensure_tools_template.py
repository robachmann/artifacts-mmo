from typing import Dict

from artifactsmmo.extensions import CharacterSchemaExtension
from artifactsmmo.log.logger import logger
from artifactsmmo.models import Skill
from artifactsmmo.service.execution_context import ExecutionContext
from artifactsmmo.service.tasks import Task
from artifactsmmo.templates.template_result import TemplateResult
from artifactsmmo.templates.template_strategy import TemplateStrategy


class EnsureToolsTemplate(TemplateStrategy):
    def template(self) -> str:
        return 'ensure-tools'

    @staticmethod
    def describe_task(task: Task) -> str:
        return (
            f'of level {task.extra.get("level")}; '
            f'mining: {task.extra.get("mining")}x, '
            f'woodcutting: {task.extra.get("woodcutting")}x, '
            f'fishing: {task.extra.get("fishing")}x, '
            f'alchemy: {task.extra.get("alchemy")}x'
        )

    def render(self, character: CharacterSchemaExtension, task: Task, quest_id: str = None, context: ExecutionContext = None) -> TemplateResult:
        template_result: TemplateResult = TemplateResult()

        tool_level = task.extra.get('level')
        mining_global_max = task.extra.get('mining')
        woodcutting_global_max = task.extra.get('woodcutting')
        fishing_global_max = task.extra.get('fishing')
        alchemy_global_max = task.extra.get('alchemy')
        gather_all_first = task.extra.get('gather_all_first')

        if tool_level is None:
            logger.warning('tool level cannot be None')

        if not any((mining_global_max, woodcutting_global_max, fishing_global_max, alchemy_global_max)):
            logger.warning('No global_max specified for any tool category.')

        craft_map: Dict[str, int] = {}
        if mining_global_max:
            for tool in self.service.get_tools(Skill.MINING, tool_level):
                craft_map[tool.code] = mining_global_max
                break

        if woodcutting_global_max:
            for tool in self.service.get_tools(Skill.WOODCUTTING, tool_level):
                craft_map[tool.code] = woodcutting_global_max
                break

        if fishing_global_max:
            for tool in self.service.get_tools(Skill.FISHING, tool_level):
                craft_map[tool.code] = fishing_global_max
                break

        if alchemy_global_max:
            for tool in self.service.get_tools(Skill.ALCHEMY, tool_level):
                craft_map[tool.code] = alchemy_global_max
                break

        if gather_all_first:
            template_result.append(Task.ensure_equipment(exact_map=craft_map))
        else:
            for item_code, global_max in craft_map.items():
                template_result.append(Task.ensure_item(item=item_code, global_max=global_max))

        return template_result
