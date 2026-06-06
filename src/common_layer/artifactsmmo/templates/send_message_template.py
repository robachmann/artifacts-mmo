from telegram.constants import ParseMode

from artifactsmmo.extensions import CharacterSchemaExtension
from artifactsmmo.service.execution_context import ExecutionContext
from artifactsmmo.service.helpers import escape_string
from artifactsmmo.service.tasks import Task
from artifactsmmo.templates.template_result import TemplateResult
from artifactsmmo.templates.template_strategy import TemplateStrategy


class SendMessageTemplate(TemplateStrategy):
    def template(self) -> str:
        return 'send-message'

    @staticmethod
    def describe_task(task: Task) -> str:
        return f'«{task.extra.get("message")}»'

    def render(self, character: CharacterSchemaExtension, task: Task, quest_id: str = None, context: ExecutionContext = None) -> TemplateResult:
        message = task.extra.get('message')
        if message:
            self.telegram_client.send_notification(
                f'💬 *{escape_string(character.name)}*: «{escape_string(message)}»',
                parse_mode=ParseMode.MARKDOWN_V2,
            )
        return TemplateResult()
