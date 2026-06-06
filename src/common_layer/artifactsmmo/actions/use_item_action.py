from artifactsmmo import game_constants
from artifactsmmo.actions.action_result import ActionResult
from artifactsmmo.actions.action_strategy import ActionStrategy
from artifactsmmo.extensions import CharacterSchemaExtension
from artifactsmmo.log.logger import logger
from artifactsmmo.service.execution_context import ExecutionContext
from artifactsmmo.service.tasks import Task


class UseItemAction(ActionStrategy):
    def action(self) -> str:
        return 'use-item'

    @staticmethod
    def describe_task(task: Task) -> str:
        return f'{task.extra.get("quantity", 1)}x {task.extra.get("item", 1)}'

    def process(self, character: CharacterSchemaExtension, task: Task, quest_id: str = None, context: ExecutionContext = None) -> ActionResult:
        action_result: ActionResult = ActionResult()
        extra = task.extra
        item_code = extra.get('item')
        quantity = int(extra.get('quantity', 1))

        item = self.service.get_item(item_code)
        heal_amount = item.item_effects.get('heal', 0)

        if heal_amount > 0 and (
            character.hp == character.max_hp or (character.max_xp - character.hp) / (quantity * heal_amount) < game_constants.HEAL_LEEWAY_FACTOR
        ):
            logger.warning(
                f'Preventing character from using {quantity}x {item_code} to heal {quantity * heal_amount}hp; '
                f'current_hp={character.hp}, max_hp={character.max_hp}'
            )
        else:
            inventory_map = {item.code: item.quantity for item in character.inventory}
            available_quantity = inventory_map.get(item_code, 0)
            if available_quantity >= quantity:
                status_code, result, error = self.actions_client.use_item(character, item_code, quantity)

                match status_code:
                    case 200:
                        hp_healed = item.item_effects.get('heal', 0)
                        if hp_healed > 0:
                            logger.info(
                                f'Used {quantity}x {item_code} to heal {quantity * hp_healed}hp '
                                f'from {character.hp}hp to {result.character.hp}/{result.character.max_hp}hp.'
                            )
                        else:
                            logger.info(f'Used {quantity}x {item_code}.')

                        self.counters_table.increment(item_code, 'items', quantity, result.cooldown.total_seconds)

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
            else:
                logger.warning(f'Requested quantity of item={item_code} unavailable. ({available_quantity}/{quantity})')
        return action_result
