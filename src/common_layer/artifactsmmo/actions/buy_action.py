from artifactsmmo.actions.action_result import ActionResult
from artifactsmmo.actions.action_strategy import ActionStrategy
from artifactsmmo.extensions import CharacterSchemaExtension
from artifactsmmo.log.logger import logger
from artifactsmmo.service.execution_context import ExecutionContext
from artifactsmmo.service.tasks import Task


class BuyItemAction(ActionStrategy):
    def action(self) -> str:
        return 'buy'

    def process(self, character: CharacterSchemaExtension, task: Task, quest_id: str = None, context: ExecutionContext = None) -> ActionResult:
        action_result: ActionResult = ActionResult()
        extra = task.extra
        order_id = extra.get('order_id')
        quantity = extra.get('quantity', 1)

        status_code, result, error = self.actions_client.buy_item(character, order_id, quantity)

        match status_code:
            case 200:
                logger.info(
                    f'{character.name} has successfully bought {result.order.quantity}x '
                    f'{result.order.code} for total_price={result.order.total_price}.'
                )
                self.counters_table.increment(result.order.code, 'buys', result.order.quantity)

            case 499:  # The character is in cooldown.
                msg = error.get('message', '')
                character_cooldown = msg if msg else 'The character is in cooldown.'
                logger.info(f'{character_cooldown} Fetching current character again.')
                reloaded_character = self.service.get_character_details(character.name)
                action_result.update_character(reloaded_character)
                action_result.repeat()

            case 598:
                logger.info('Grand Exchange not found on this map.')
                reloaded_character = self.service.get_character_details(character.name)
                action_result.update_character(reloaded_character)
                action_result.append(Task.move(content_type='grand_exchange'))
                action_result.repeat()

            case _:
                logger.error(f'Unexpected response: {error}.')
                action_result.abort(f'{task.action}: {error}')

        if result and result.character:
            action_result.update_character(result.character)
        return action_result
