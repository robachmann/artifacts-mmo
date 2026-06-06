from artifactsmmo.extensions import CharacterSchemaExtension
from artifactsmmo.service.execution_context import ExecutionContext
from artifactsmmo.service.tasks import Task
from artifactsmmo.templates.template_result import TemplateResult
from artifactsmmo.templates.template_strategy import TemplateStrategy


class FinishTaskTemplate(TemplateStrategy):
    def template(self) -> str:
        return 'finish-task'

    def render(self, character: CharacterSchemaExtension, task: Task, quest_id: str = None, context: ExecutionContext = None) -> TemplateResult:
        template_result: TemplateResult = TemplateResult()

        if character.is_task_complete():
            template_result.append(Task.move(content_type='tasks_master', content_code=character.current_task.task_type))
            template_result.append(Task.complete_task())

        return template_result
