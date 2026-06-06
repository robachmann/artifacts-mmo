from telegram.constants import ParseMode

from artifactsmmo.actions.action_result import ActionResult
from artifactsmmo.actions.action_strategy import ActionStrategy
from artifactsmmo.extensions import CharacterSchemaExtension
from artifactsmmo.log.logger import logger
from artifactsmmo.service.execution_context import ExecutionContext
from artifactsmmo.service.helpers import escape_string
from artifactsmmo.service.tasks import Task


class CancelTaskAction(ActionStrategy):
    def action(self) -> str:
        return 'cancel-task'

    def process(self, character: CharacterSchemaExtension, task: Task, quest_id: str = None, context: ExecutionContext = None) -> ActionResult:
        action_result: ActionResult = ActionResult()

        status_code, result, error = self.actions_client.cancel_task(character)

        match status_code:
            case 200:
                logger.info('Successfully cancelled a task.')
                self.counters_table.increment('cancel', 'tasks')
                self.telegram_client.send_notification(
                    f'💸 *{escape_string(character.name)}* cancelled a task {escape_string(f"({character.current_task.task_total}x {character.current_task.task}).")}',
                    parse_mode=ParseMode.MARKDOWN_V2,
                )

            case 499:  # The character is in cooldown.
                msg = error.get('message', '')
                character_cooldown = msg if msg else 'The character is in cooldown.'
                logger.info(f'{character_cooldown} Fetching current character again.')
                reloaded_character = self.service.get_character_details(character.name)
                action_result.update_character(reloaded_character)
                action_result.repeat()

            case 598:
                logger.info('Tasks Master not found on this map.')
                reloaded_character = self.service.get_character_details(character.name)
                action_result.update_character(reloaded_character)
                action_result.append(Task.move(content_type='tasks_master', content_code='monsters'))
                action_result.repeat()

            case _:
                logger.error(f'Unexpected response: {error}')
                action_result.abort(f'{task.action}: {error}')

        if result and result.character:
            action_result.update_character(result.character)
        return action_result
