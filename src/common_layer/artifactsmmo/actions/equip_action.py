from typing import List

from telegram.constants import ParseMode

from artifactsmmo.actions.action_result import ActionResult
from artifactsmmo.actions.action_strategy import ActionStrategy
from artifactsmmo.extensions import CharacterSchemaExtension
from artifactsmmo.log.logger import logger
from artifactsmmo.service.execution_context import ExecutionContext
from artifactsmmo.service.helpers import escape_string
from artifactsmmo.service.tasks import Task


class EquipAction(ActionStrategy):
    def action(self) -> str:
        return 'equip'

    @staticmethod
    def describe_task(task: Task) -> str:
        quantity = task.extra.get('quantity')
        if quantity and quantity > 1:
            return f'{quantity}x {task.extra.get("item")}'
        else:
            return task.extra.get('item')

    def process(self, character: CharacterSchemaExtension, task: Task, quest_id: str = None, context: ExecutionContext = None) -> ActionResult:
        action_result: ActionResult = ActionResult()
        item_code = task.extra.get('item')
        slot = str(task.extra.get('slot', '')).removesuffix('_slot')
        quantity = task.extra.get('quantity', 1)

        currently_equipped_item_code = character.equipment.get(slot)

        if currently_equipped_item_code and currently_equipped_item_code == item_code:
            already_equipped_quantity = getattr(character, f'{slot}_slot_quantity', 1)
            quantity = min(100 - already_equipped_quantity, quantity)
            logger.info(f'Item={item_code} is already equipped {already_equipped_quantity}x, will only equip another {quantity}x')

        status_code, result, error = self.actions_client.equip(character, item_code, slot, quantity)

        match status_code:
            case 200:
                logger.debug('Equipped item=%s to slot=%s', item_code, slot)

            case 478:  # Missing required item(s).
                reloaded_character = self.service.get_character_details(character.name)
                action_result.update_character(reloaded_character)
                error_log = f'{task.action}: {error} ({quantity}x {item_code} to {slot})'
                logger.error(error_log)
                action_result.abort(error_log)

                lines = [f'*Availability of {escape_string(item_code)}* for *{escape_string(character.name)}*']

                bank_items_map = self.service.get_bank_items_map(ignore_reservations=True)
                bank_reservations_map = self.service.get_bank_reservations_map()
                all_character_details = self.service.get_all_character_details()

                if item_code in bank_reservations_map:
                    reservations = escape_string(f' (+{bank_reservations_map[item_code]}x 🔒)')
                    bank_quantity = max(bank_items_map.get(item_code, 0) - bank_reservations_map[item_code], 0)
                else:
                    reservations = ''
                    bank_quantity = bank_items_map.get(item_code, 0)
                lines.append(f' ∟ Bank: {bank_quantity}x{reservations}')
                for character in all_character_details:
                    equip_count = 0
                    for slot, code in character.equipment.items():
                        if code == item_code:
                            if slot.startswith('utility'):
                                equip_count += character.utilities.get(item_code, 0)
                            else:
                                equip_count += 1

                    if item_code in character.equipment.values():
                        lines.append(escape_string(f' ∟ {character.name}: {equip_count}x (equipped)'))

                    inventory_count = character.inventory_map.get(item_code, 0)
                    if inventory_count > 0:
                        lines.append(escape_string(f' ∟ {character.name}: {inventory_count}x (inventory)'))

                if lines:
                    messages: List[str] = []
                    message = ''
                    for line in lines:
                        if len(message + '\n' + line) > 3000:
                            messages.append(message)
                            message = ''
                        message += line + '\n'

                    if message:
                        messages.append(message)

                    for m in messages:
                        self.telegram_client.send_notification(m, parse_mode=ParseMode.MARKDOWN_V2)

            case 483:  # The character does not have enough HP to unequip this item
                logger.warning(f'The character does not have enough HP to unequip this item from {slot}. Will rest and try again.')
                reloaded_character = self.service.get_character_details(character.name)
                action_result.update_character(reloaded_character)
                action_result.append(Task.rest())
                action_result.repeat()

            case 485:  # This item is already equipped.
                logger.info(f'{item_code} in {slot} is already equipped.')
                reloaded_character = self.service.get_character_details(character.name)
                action_result.update_character(reloaded_character)

            case 499:  # The character is in cooldown.
                msg = error.get('message', '')
                character_cooldown = msg if msg else 'The character is in cooldown.'
                logger.info(f'{character_cooldown} Fetching current character again.')
                reloaded_character = self.service.get_character_details(character.name)
                action_result.update_character(reloaded_character)
                action_result.repeat()

            case _:
                logger.error(f'Unexpected response: {error}')
                action_result.abort(f'{task.action}: {error} ({quantity}x {item_code} to {slot})')

        if result and result.character:
            action_result.update_character(result.character)
        return action_result
