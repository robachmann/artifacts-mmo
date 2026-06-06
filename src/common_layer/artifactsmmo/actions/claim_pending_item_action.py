from telegram.constants import ParseMode

from artifactsmmo.actions.action_result import ActionResult
from artifactsmmo.actions.action_strategy import ActionStrategy
from artifactsmmo.extensions import CharacterSchemaExtension
from artifactsmmo.log.logger import logger
from artifactsmmo.service.execution_context import ExecutionContext
from artifactsmmo.service.helpers import escape_string
from artifactsmmo.service.tasks import Task


class RestAction(ActionStrategy):
    def action(self) -> str:
        return 'claim-pending-item'

    @staticmethod
    def describe_task(task: Task) -> str:
        return task.extra.get('id', '')

    def process(self, character: CharacterSchemaExtension, task: Task, quest_id: str = None, context: ExecutionContext = None) -> ActionResult:
        action_result: ActionResult = ActionResult()

        pending_item_id = task.extra.get('id')
        if pending_item_id:
            status_code, result, error = self.actions_client.claim_pending_item(character, pending_item_id)

            match status_code:
                case 200:
                    claimed_items = ', '.join(f'{item.quantity}x {item.code}' for item in result.item.items)
                    logger.info(f'The character has successfully claimed {claimed_items}')
                    message = f'📬 *{escape_string(character.name)}* claimed {escape_string(claimed_items)}'
                    self.telegram_client.send_notification(message, parse_mode=ParseMode.MARKDOWN_V2)

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
