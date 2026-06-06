from artifactsmmo.actions.action_result import ActionResult
from artifactsmmo.actions.action_strategy import ActionStrategy
from artifactsmmo.extensions import CharacterSchemaExtension
from artifactsmmo.log.logger import logger
from artifactsmmo.service.execution_context import ExecutionContext
from artifactsmmo.service.tasks import Task


class SellItemAction(ActionStrategy):
    def action(self) -> str:
        return 'sell'

    @staticmethod
    def describe_task(task: Task) -> str:
        return f'{task.extra.get("quantity")}x {task.extra.get("item")} for {task.extra.get("sell_price")}g'

    def process(self, character: CharacterSchemaExtension, task: Task, quest_id: str = None, context: ExecutionContext = None) -> ActionResult:
        action_result: ActionResult = ActionResult()

        item = task.extra['item']
        quantity = int(task.extra['quantity'])
        sell_price = int(task.extra['sell_price'])

        status_code, result, error = self.actions_client.sell_item(character, item, quantity, sell_price)

        match status_code:
            case 200:
                logger.info(
                    f'{character.name} has successfully sold {result.order.quantity} {result.order.code} '
                    f'for a total price of {result.order.total_price}, order_id={result.order.id}.'
                )

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

            case 433:
                logger.info('You cannot create more than 100 orders at the same time.')

            case _:
                logger.error(f'Unexpected response: {error}')
                action_result.abort(f'{task.action}: {error}')

        if result and result.character:
            action_result.update_character(result.character)
        return action_result
