from typing import Iterator, List

from artifactsmmo.extensions import CharacterSchemaExtension, ItemSchemaExtension
from artifactsmmo.service.execution_context import ExecutionContext
from artifactsmmo.service.tasks import Task
from artifactsmmo.templates.template_result import TemplateResult
from artifactsmmo.templates.template_strategy import TemplateStrategy


class WithdrawTeleportItemTemplate(TemplateStrategy):
    def template(self) -> str:
        return 'withdraw-teleport-item'

    def render(self, character: CharacterSchemaExtension, task: Task, quest_id: str = None, context: ExecutionContext = None) -> TemplateResult:
        template_result: TemplateResult = TemplateResult()

        consumables: Iterator[ItemSchemaExtension] = self.service.get_items_by_type('consumable', character.level)
        teleport_items: List[ItemSchemaExtension] = []
        for consumable in consumables:
            if consumable.is_teleport_item:
                teleport_items.append(consumable)

        if teleport_items:
            carrying_teleport_item = any(item.code in character.inventory_map for item in teleport_items)
            if not carrying_teleport_item:
                bank_items_map = self.service.get_bank_items_map(task_id=task.task_id, character_name=character.name)
                for teleport_item in teleport_items:
                    if teleport_item.code in bank_items_map:
                        template_result.append(Task.withdraw(item=teleport_item.code))
                        break

        return template_result
