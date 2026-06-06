from artifactsmmo.extensions import CharacterSchemaExtension
from artifactsmmo.models import ItemSlot
from artifactsmmo.service.execution_context import ExecutionContext
from artifactsmmo.service.tasks import Task
from artifactsmmo.templates.template_result import TemplateResult
from artifactsmmo.templates.template_strategy import TemplateStrategy


class UnequipUtilitiesTemplate(TemplateStrategy):
    def template(self) -> str:
        return 'unequip-utilities'

    @staticmethod
    def describe_task(task: Task) -> str:
        return ''

    def render(self, character: CharacterSchemaExtension, task: Task, quest_id: str = None, context: ExecutionContext = None) -> TemplateResult:
        template_result: TemplateResult = TemplateResult()
        extra = task.extra
        return_previous_position: bool = extra.get('return_previous_position', False)

        unequipped_utility = False
        for utility in [ItemSlot.UTILITY1, ItemSlot.UTILITY2]:
            equipped_quantity = getattr(character, f'{utility}_slot_quantity')
            if equipped_quantity > 0:
                template_result.append(Task.unequip(slot=utility, quantity=equipped_quantity))
                unequipped_utility = True

        if unequipped_utility:
            template_result.append(Task.ensure_inventory(task_id=task.task_id, return_previous_position=return_previous_position))

        return template_result
