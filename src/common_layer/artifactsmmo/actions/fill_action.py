from artifactsmmo.actions.action_result import ActionResult
from artifactsmmo.actions.action_strategy import ActionStrategy
from artifactsmmo.extensions import CharacterSchemaExtension
from artifactsmmo.log.logger import logger
from artifactsmmo.service.execution_context import ExecutionContext
from artifactsmmo.service.tasks import Task


class FillAction(ActionStrategy):
    def action(self) -> str:
        return 'fill'

    def process(self, character: CharacterSchemaExtension, task: Task, quest_id: str = None, context: ExecutionContext = None) -> ActionResult:
        action_result: ActionResult = ActionResult()

        order_id = task.extra['buy_order_id']
        quantity = task.extra['quantity']

        status_code, result, error = self.actions_client.fill_order(character, order_id, quantity)

        match status_code:
            case 200:
                if result:
                    logger.info(
                        f'{character.name} has successfully filled order {order_id} by selling {quantity}x {result.order.code} '
                        f'for {result.order.total_price}g.'
                    )
                self.counters_table.increment(result.order.code, 'sells', quantity)

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
