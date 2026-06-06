from telegram.constants import ParseMode

from artifactsmmo.actions.action_result import ActionResult
from artifactsmmo.actions.action_strategy import ActionStrategy
from artifactsmmo.extensions import CharacterSchemaExtension
from artifactsmmo.log.logger import logger
from artifactsmmo.service.execution_context import ExecutionContext
from artifactsmmo.service.helpers import escape_string, format_number
from artifactsmmo.service.tasks import Task


class BuyBankExpansionAction(ActionStrategy):
    def action(self) -> str:
        return 'buy-bank-expansion'

    def process(self, character: CharacterSchemaExtension, task: Task, quest_id: str = None, context: ExecutionContext = None) -> ActionResult:
        action_result: ActionResult = ActionResult()
        status_code, result, error = self.actions_client.buy_bank_expansion(character)

        match status_code:
            case 200:
                logger.info(f'Bought expansion slot for bank for {result.transaction.price} gold')
                message = f'🏦 *{escape_string(character.name)}* bought another bank expansion for {escape_string(format_number(result.transaction.price))}g\\.'
                self.telegram_client.send_notification(message, parse_mode=ParseMode.MARKDOWN_V2)

            case 499:  # The character is in cooldown.
                msg = error.get('message', '')
                character_cooldown = msg if msg else 'The character is in cooldown.'
                logger.info(f'{character_cooldown} Fetching current character again.')
                reloaded_character = self.service.get_character_details(character.name)
                action_result.update_character(reloaded_character)
                action_result.repeat()

            case 598:
                logger.info('Bank not found on this map.')
                reloaded_character = self.service.get_character_details(character.name)
                action_result.update_character(reloaded_character)
                action_result.append(Task.move(content_type='bank'))
                action_result.repeat()

            case _:
                logger.error(f'Unexpected response: {error}')
                action_result.abort(f'{task.action}: {error}')

        if result and result.character:
            action_result.update_character(result.character)
        return action_result
