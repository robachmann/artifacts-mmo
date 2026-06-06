from artifactsmmo.actions.action_result import ActionResult
from artifactsmmo.actions.action_strategy import ActionStrategy
from artifactsmmo.extensions import CharacterSchemaExtension
from artifactsmmo.log.logger import logger
from artifactsmmo.service.execution_context import ExecutionContext
from artifactsmmo.service.tasks import Task


class TradeAction(ActionStrategy):
    def action(self) -> str:
        return 'trade'

    @staticmethod
    def describe_task(task: Task) -> str:
        return f'{task.extra.get("quantity")}x {task.extra.get("item")}'

    def process(self, character: CharacterSchemaExtension, task: Task, quest_id: str = None, context: ExecutionContext = None) -> ActionResult:
        action_result: ActionResult = ActionResult()
        extra = task.extra
        item = extra.get('item')
        quantity = int(extra.get('quantity', 1))

        logger.info(f'Plan to trade {quantity} of item={item}, carrying={character.inventory_map.get(item, 0)}')

        status_code, result, error = self.actions_client.trade(character, item, quantity)
        match status_code:
            case 200:
                logger.info(f'Successfully traded {quantity}x {item} to a Tasks Master.')

            case 499:  # The character is in cooldown.
                msg = error.get('message', '')
                character_cooldown = msg if msg else 'The character is in cooldown.'
                logger.info(f'{character_cooldown} Fetching current character again.')
                reloaded_character = self.service.get_character_details(character.name)
                action_result.update_character(reloaded_character)
                action_result.repeat()

            case 598:  # Tasks Master not found on this map.
                message = f'Tasks Master not found on this map: ({character.layer}/{character.x}/{character.y})'
                logger.error(message)
                action_result.abort(message)

            case _:
                logger.error(f'Unexpected response: {error}')
                action_result.abort(f'{task.action}: {error}')

        if result and result.character:
            action_result.update_character(result.character)
        return action_result
