from artifactsmmo.actions.action_result import ActionResult
from artifactsmmo.actions.action_strategy import ActionStrategy
from artifactsmmo.extensions import CharacterSchemaExtension
from artifactsmmo.log.logger import logger
from artifactsmmo.models import ItemType
from artifactsmmo.service.execution_context import ExecutionContext
from artifactsmmo.service.helpers import escape_string
from artifactsmmo.service.tasks import Task


class ExchangeAction(ActionStrategy):
    def action(self) -> str:
        return 'exchange'

    def process(self, character: CharacterSchemaExtension, task: Task, quest_id: str = None, context: ExecutionContext = None) -> ActionResult:
        action_result: ActionResult = ActionResult()

        status_code, result, error = self.actions_client.exchange(character)
        match status_code:
            case 200:
                reward_map = {item.code: item.quantity for item in result.rewards.items}
                logger.info(f'The tasks coins have been successfully exchanged for {reward_map} and {result.rewards.gold} gold')

                for code, qty in reward_map.items():
                    if self.service.is_item_rare_drop(code):
                        self.telegram_client.send_notification(
                            f'💎 *{escape_string(character.name)}* received {qty} *{escape_string(code)}*\\.', parse_mode='MarkdownV2'
                        )
                    item = self.service.get_item(code)
                    if item.type == ItemType.CONSUMABLE and item.subtype == 'bag':
                        action_result.append(Task.use_item(code, qty))
                        logger.info(f'Received {qty}x {code}. Plan to immediately use it.')

                self.counters_table.increment('exchange', 'tasks_coin')
                for reward in result.rewards.items:
                    self.counters_table.increment(reward.code, 'rewards.exchange.tasks_coin', reward.quantity)

            case 478:  # Missing item or insufficient quantity in your inventory.
                reloaded_character = self.service.get_character_details(character.name)
                action_result.update_character(reloaded_character)
                inventory_map = {item.code: item.quantity for item in character.inventory}
                message = f'Not enough task coins to exchange: {inventory_map.get("tasks_coin", 0)}'
                logger.warning(message)
                action_result.abort(message)

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
