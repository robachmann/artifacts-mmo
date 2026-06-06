from datetime import datetime, UTC

from telegram.constants import ParseMode

from artifactsmmo.actions.action_result import ActionResult
from artifactsmmo.actions.action_strategy import ActionStrategy
from artifactsmmo.extensions import CharacterSchemaExtension
from artifactsmmo.log.logger import logger
from artifactsmmo.service.execution_context import ExecutionContext
from artifactsmmo.service.helpers import escape_string, format_number
from artifactsmmo.service.tasks import Task


class SellNpcAction(ActionStrategy):
    def action(self) -> str:
        return 'sell-npc'

    @staticmethod
    def describe_task(task: Task) -> str:
        return f'{task.extra.get("quantity")}x {task.extra.get("item")} to {task.extra.get("npc")}'

    def process(self, character: CharacterSchemaExtension, task: Task, quest_id: str = None, context: ExecutionContext = None) -> ActionResult:
        action_result: ActionResult = ActionResult()
        extra = task.extra
        item_code = extra['item']
        quantity = extra.get('quantity', 1)
        npc_code = extra['npc']
        event_end_ts = extra.get('event_end_ts')

        if event_end_ts is not None and event_end_ts < datetime.now(UTC).timestamp():
            logger.info(f'NPC {npc_code} is not available anymore.')
            return action_result

        status_code, result, error = self.actions_client.sell_npc(character, item_code, quantity)

        match status_code:
            case 200:
                logger.info(
                    f'{character.name} has successfully sold {result.transaction.quantity}x '
                    f'{result.transaction.code} for total_price={result.transaction.total_price} to npc={npc_code}.'
                )
                self.counters_table.increment(result.transaction.code, 'sells', result.transaction.quantity)

                message = (
                    f'💰 *{escape_string(character.name)}* sold '
                    f'{result.transaction.quantity} *{escape_string(result.transaction.code)}* to '
                    f'{escape_string(npc_code)} for {escape_string(format_number(result.transaction.total_price))}g\\.'
                )
                self.telegram_client.send_notification(message, parse_mode=ParseMode.MARKDOWN_V2)

            case 499:  # The character is in cooldown.
                msg = error.get('message', '')
                character_cooldown = msg if msg else 'The character is in cooldown.'
                logger.info(f'{character_cooldown} Fetching current character again.')
                reloaded_character = self.service.get_character_details(character.name)
                action_result.update_character(reloaded_character)
                action_result.repeat()

            case 598:
                logger.warning(f'NPC {npc_code} not found on this map.')
                reloaded_character = self.service.get_character_details(character.name)
                action_result.update_character(reloaded_character)
                action_result.append(Task.move(content_type='npc', content_code=npc_code))
                action_result.repeat()

            case _:
                logger.error(f'Unexpected response: {error}.')
                action_result.abort(f'{task.action}: {error}')

        if result and result.character:
            action_result.update_character(result.character)
        return action_result
