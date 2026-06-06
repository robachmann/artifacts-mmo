from artifactsmmo.actions.action_result import ActionResult
from artifactsmmo.actions.action_strategy import ActionStrategy
from artifactsmmo.extensions import CharacterSchemaExtension
from artifactsmmo.log.logger import logger
from artifactsmmo.service.execution_context import ExecutionContext
from artifactsmmo.service.tasks import Task


class UnequipAction(ActionStrategy):
    def action(self) -> str:
        return 'unequip'

    @staticmethod
    def describe_task(task: Task) -> str:
        return f'slot {task.extra.get("slot")}'

    def process(self, character: CharacterSchemaExtension, task: Task, quest_id: str = None, context: ExecutionContext = None) -> ActionResult:
        action_result: ActionResult = ActionResult()
        slot = str(task.extra.get('slot', '')).removesuffix('_slot')
        quantity = int(task.extra.get('quantity', 1))

        currently_equipped_item_code = character.equipment.get(slot)
        if not currently_equipped_item_code:
            logger.info(f'Nothing to unequip from slot {slot}_slot')
        else:
            item = self.service.get_item(currently_equipped_item_code)
            if 'hp' in item.item_effects:
                additional_hp = item.item_effects.get('hp', 0)
                if additional_hp >= character.hp:
                    consumable_map = self.food_service.get_best_food_to_consume(character, additional_hp)
                    if consumable_map:
                        logger.info(
                            f'Plan to consume {consumable_map} to heal from {character.hp} to necessary HP before unequipping '
                            f'{currently_equipped_item_code} which provides {additional_hp} additional hp'
                        )
                        for item_code, item_qty in consumable_map.items():
                            action_result.append(Task.use_item(item_code, item_qty))
                    else:
                        logger.info(
                            f'No consumable(s) found to heal from {character.hp} to necessary HP before unequipping '
                            f'{currently_equipped_item_code} which provides {additional_hp} additional hp. '
                            f'Plan to rest.'
                        )
                        action_result.append(Task.rest())
                    action_result.repeat()

            if not action_result.new_tasks:
                status_code, result, error = self.actions_client.unequip(character, slot, quantity)
                match status_code:
                    case 200:
                        logger.debug('Unequipped slot=%s.', result.slot)

                    case 483:  # Character has not enough HP to unequip this item.
                        logger.error(
                            f'Character has not enough HP to unequip this item: {character.hp}/{character.max_hp}, '
                            f'{currently_equipped_item_code} provides {item.item_effects.get("hp", 0)} hp'
                        )
                        action_result.append(Task.rest())
                        action_result.repeat()

                    case 497:  # Character inventory is full.
                        logger.info(
                            f'Character inventory is full ({character.inventory_map.total() / character.inventory_max_items}). '
                            f'Adding tasks to deposit current inventory at bank and return to this location.'
                        )
                        action_result.append(Task.ensure_inventory(task_id=task.task_id, return_previous_position=True))
                        action_result.repeat()

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
