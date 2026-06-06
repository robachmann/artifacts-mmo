from telegram.constants import ParseMode

from artifactsmmo.actions.action_result import ActionResult
from artifactsmmo.actions.action_strategy import ActionStrategy
from artifactsmmo.extensions import CharacterSchemaExtension
from artifactsmmo.log.logger import logger
from artifactsmmo.service.execution_context import ExecutionContext
from artifactsmmo.service.helpers import escape_string
from artifactsmmo.service.tasks import Task


class DeleteInventoryAction(ActionStrategy):
    def action(self) -> str:
        return 'delete-inventory'

    @staticmethod
    def describe_task(task: Task) -> str:
        return f'{task.extra["quantity"]}x {task.extra["item"]}'

    def process(self, character: CharacterSchemaExtension, task: Task, quest_id: str = None, context: ExecutionContext = None) -> ActionResult:
        action_result: ActionResult = ActionResult()
        item_code = str(task.extra['item'])
        quantity = int(task.extra['quantity'])

        status_code, result, error = self.actions_client.delete_item(character, item_code, quantity)
        match status_code:
            case 200:
                logger.info(f'Successfully deleted {quantity}x {item_code}.')
                msg = f'🚮 *{escape_string(character.name)}* deleted {quantity}x *{escape_string(item_code)}*'
                self.telegram_client.send_notification(msg, parse_mode=ParseMode.MARKDOWN_V2)

            case 499:  # The character is in cooldown.
                msg = error.get('message', '')
                character_cooldown = msg if msg else 'The character is in cooldown.'
                logger.info(f'{character_cooldown} Fetching current character again.')
                reloaded_character = self.service.get_character_details(character.name)
                action_result.update_character(reloaded_character)
                action_result.repeat()

            case _:
                logger.error(f'Unexpected response: {error}')
                action_result.abort(f'{task.action}: {error}')

        if result and result.character:
            action_result.update_character(result.character)
        return action_result
