from collections import Counter
from typing import Dict

from telegram.constants import ParseMode

from artifactsmmo.actions.action_result import ActionResult
from artifactsmmo.actions.action_strategy import ActionStrategy
from artifactsmmo.extensions import CharacterSchemaExtension
from artifactsmmo.log.logger import logger
from artifactsmmo.service.execution_context import ExecutionContext
from artifactsmmo.service.helpers import escape_string, format_dict, format_number
from artifactsmmo.service.tasks import Task


class DepositAction(ActionStrategy):
    def action(self) -> str:
        return 'deposit'

    @staticmethod
    def describe_task(task: Task) -> str:
        return format_dict(task.extra.get('items'))

    def process(self, character: CharacterSchemaExtension, task: Task, quest_id: str = None, context: ExecutionContext = None) -> ActionResult:
        action_result: ActionResult = ActionResult()
        item_map: Dict[str, int] = task.extra.get('items', {}) or {}

        if not item_map:
            logger.error(f'Missing "items" key in {task.extra}')
        else:
            item_list = []
            for item_code, item_qty in item_map.items():
                inventory_qty = character.inventory_map.get(item_code, 0)

                if item_qty > inventory_qty:
                    logger.warning(f'Cannot deposit {item_qty} of {item_code}, only {inventory_qty} available in inventory.')

                deposit_qty = min(item_qty, inventory_qty)

                if deposit_qty > 0:
                    item_list.append({'code': item_code, 'quantity': deposit_qty})

            if not item_list:
                logger.warning('Nothing to deposit.')
                return action_result

            status_code, result, error = self.actions_client.deposit(character, item_list)

            match status_code:
                case 200:
                    logger.info(f'Deposited {item_map}.')

                    if quest_id and task.task_id:
                        for item in result.items:
                            drop_id = f'{task.task_id}.{item.code}'
                            progress = self.task_progress_table.get_progress(quest_id, drop_id)
                            if progress and progress.leader:
                                self.service.increment_bank_reservation(task.task_id, item.code, item.quantity, progress.leader)

                case 461:  # A transaction is already in progress with this item/your golds in your bank.
                    reloaded_character = self.service.get_character_details(character.name)
                    action_result.update_character(reloaded_character)
                    action_result.repeat()

                case 462:  # Your bank is full.
                    bank_details = self.service.get_bank_details()
                    available_gold = character.gold + bank_details.gold
                    if available_gold >= bank_details.next_expansion_cost:
                        logger.info('Bank is full, adding tasks to buy expansion.')
                        gold_to_withdraw = max(bank_details.next_expansion_cost - character.gold, 0)
                        if gold_to_withdraw > 0:
                            action_result.append(Task.withdraw_gold(quantity=gold_to_withdraw))
                        action_result.append(Task.buy_bank_expansion())
                        action_result.repeat()
                    else:
                        bank_items_map = self.service.get_bank_items_map(ignore_reservations=True)
                        deposit_anyway_map = {}
                        for item_code, item_qty in item_map.items():
                            if item_code in bank_items_map:
                                action_result.append(Task.deposit(item=item_code, quantity=item_qty, task_id=task.task_id))
                                deposit_anyway_map[item_code] = item_qty

                        if not deposit_anyway_map:
                            remaining_space = bank_details.slots - len(bank_items_map)
                            for item_code, item_qty in item_map.items():
                                if remaining_space > 0:
                                    item = self.service.get_item(item_code)
                                    if item.is_gear():
                                        action_result.append(Task.deposit(item=item_code, quantity=item_qty, task_id=task.task_id))
                                        deposit_anyway_map[item_code] = item_qty
                                        remaining_space -= 1

                        if not deposit_anyway_map:
                            item_counter = Counter(item_map)
                            remaining_space = bank_details.slots - len(bank_items_map)
                            for slots, (item_code, item_qty) in enumerate(item_counter.most_common()):
                                if slots < remaining_space:
                                    action_result.append(Task.deposit(item=item_code, quantity=item_qty, task_id=task.task_id))
                                    deposit_anyway_map[item_code] = item_qty

                        logger.warning(f'Bank is full but cannot afford to buy expansion, deposit_anyway_map={deposit_anyway_map}')
                        if not deposit_anyway_map:
                            overflow_item_codes = [item_code for item_code in item_map if item_code not in deposit_anyway_map]
                            message = (
                                f'⛔️ {character.name} tried to deposit {len(overflow_item_codes)} items ({", ".join(overflow_item_codes)}) '
                                f'but the bank is already full ({len(bank_items_map)}/{bank_details.slots}) and we cannot afford the next expansion yet (missing {format_number(bank_details.next_expansion_cost - available_gold)} gold).'
                            )
                            self.telegram_client.send_notification(escape_string(message), ParseMode.MARKDOWN_V2)

                case 499:  # The character is in cooldown.
                    msg = error.get('message', '')
                    character_cooldown = msg if msg else 'The character is in cooldown.'
                    logger.info(f'{character_cooldown} Fetching current character again.')
                    reloaded_character = self.service.get_character_details(character.name)
                    action_result.update_character(reloaded_character)
                    action_result.repeat()

                case 598:
                    logger.info('Bank not found on this map.')
                    reloaded_character = self.service.get_character_details(character.name)
                    action_result.update_character(reloaded_character)
                    action_result.append(Task.move(content_type='bank'))
                    action_result.repeat()

                case 478:  # Missing required item(s)
                    reloaded_character = self.service.get_character_details(character.name)
                    action_result.update_character(reloaded_character)
                    deposit_map = {item['code']: item['quantity'] for item in item_list}
                    log_message = (
                        f'{reloaded_character.name} tried to deposit items: {deposit_map}, current inventory: {reloaded_character.inventory_map}'
                    )
                    logger.warning(log_message)
                    self.telegram_client.send_notification(log_message)
                    action_result.repeat()
                case _:
                    logger.error(f'Unexpected response: {error}')

                    deposit_map = {}
                    for i in item_list:
                        deposit_map[i['code']] = {
                            'deposit': i['quantity'],
                            'inventory': character.inventory_map.get(i['code'], 0),
                        }

                    action_result.abort(f'{task.action}: {error} ({deposit_map})')

            if result and result.character:
                action_result.update_character(result.character)
        return action_result
