from artifactsmmo.actions.action_result import ActionResult
from artifactsmmo.actions.action_strategy import ActionStrategy
from artifactsmmo.extensions import CharacterSchemaExtension
from artifactsmmo.log.logger import logger
from artifactsmmo.service.execution_context import ExecutionContext
from artifactsmmo.service.helpers import escape_string
from artifactsmmo.service.tasks import Task


class RecycleAction(ActionStrategy):
    def action(self) -> str:
        return 'recycle'

    @staticmethod
    def describe_task(task: Task) -> str:
        return f'{task.extra.get("quantity") * task.ttl if task.ttl else task.extra.get("quantity")}x {task.extra.get("item")}'

    def process(self, character: CharacterSchemaExtension, task: Task, quest_id: str = None, context: ExecutionContext = None) -> ActionResult:
        action_result: ActionResult = ActionResult()
        extra = task.extra
        item_code = extra.get('item')
        quantity = int(extra.get('quantity', 1))
        should_recraft = bool(extra.get('recraft', False))

        logger.info(f'Recycle item {item_code} {quantity} times')
        if quantity > 0:
            status_code, result, error = self.actions_client.recycle(character, item_code, quantity)
            match status_code:
                case 200:
                    drop_map = {item.code: item.quantity for item in result.details.items}
                    logger.info(f'Recycled {quantity}x {item_code}, drop_map={drop_map}')
                    self.counters_table.increment(item_code, 'recycling', quantity, result.cooldown.total_seconds)

                    for code, qty in drop_map.items():
                        if self.service.is_item_rare_drop(code) or self.service.get_item(code).is_task_reward:
                            self.telegram_client.send_notification(
                                f'💎 *{escape_string(character.name)}* recovered {qty} *{escape_string(code)}* through recycling\\.',
                                parse_mode='MarkdownV2',
                            )

                    if quantity > 1 and should_recraft:
                        item_map = {item.code: item.quantity for item in result.character.inventory}
                        craftable_quantity = self.service.get_craftable_recipe_count(item_code, item_map)
                        if craftable_quantity > 0:
                            action_result.append(Task.craft(item_code, craftable_quantity, target='recycle', recraft=True))
                            logger.info(f'item_map={item_map} allows to craft another {craftable_quantity}x {item_code}. Adding tasks to do so.')

                case 473:
                    logger.info(f'Item {item_code} cannot be recycled.')

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
