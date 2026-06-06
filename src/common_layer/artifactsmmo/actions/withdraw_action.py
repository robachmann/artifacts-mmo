from typing import Counter, Dict

from artifactsmmo.actions.action_result import ActionResult
from artifactsmmo.actions.action_strategy import ActionStrategy
from artifactsmmo.client.actions import ActionsClient
from artifactsmmo.dynamodb.character_table import CharacterTable
from artifactsmmo.dynamodb.counters_table import CountersTable
from artifactsmmo.dynamodb.skill_stats_table import SkillStatsTable
from artifactsmmo.dynamodb.task_progress_table import TaskProgressTable
from artifactsmmo.dynamodb.withdraw_table import WithdrawTable
from artifactsmmo.extensions import CharacterSchemaExtension
from artifactsmmo.log.logger import logger
from artifactsmmo.service.execution_context import ExecutionContext
from artifactsmmo.service.food_service import FoodService
from artifactsmmo.service.helpers import format_dict
from artifactsmmo.service.service import Service
from artifactsmmo.service.tasks import Task
from artifactsmmo.telegram.client import TelegramClient


class WithdrawAction(ActionStrategy):
    def __init__(
        self,
        actions_client: ActionsClient,
        service: Service,
        counters_table: CountersTable,
        telegram_client: TelegramClient,
        task_progress_table: TaskProgressTable,
        skill_stats_table: SkillStatsTable,
        food_service: FoodService,
        character_table: CharacterTable,
    ):
        super().__init__(
            actions_client, service, counters_table, telegram_client, task_progress_table, skill_stats_table, food_service, character_table
        )
        self.withdraw_table = WithdrawTable()

    def action(self) -> str:
        return 'withdraw'

    @staticmethod
    def describe_task(task: Task) -> str:
        return format_dict(task.extra.get('items'))

    def process(self, character: CharacterSchemaExtension, task: Task, quest_id: str = None, context: ExecutionContext = None) -> ActionResult:
        action_result: ActionResult = ActionResult()

        item_map: Dict[str, int] = task.extra.get('items', {}) or {}

        if not item_map:
            logger.error(f'Missing "items" key in {task.extra}')
        else:
            bank_items_map = self.service.get_bank_items_map(task_id=task.task_id, character_name=character.name)
            item_list = []
            for item_code, quantity in item_map.items():
                if quantity > 0:
                    available_quantity = bank_items_map.get(item_code, 0)
                    if available_quantity == 0:
                        logger.warning(
                            f'Requested item not available in bank: {item_code}, requested_quantity={quantity}, available_quantity={available_quantity}. '
                            f'Skip withdrawal.'
                        )
                    elif available_quantity < quantity:
                        logger.warning(
                            f'Requested item not available in bank: {item_code}, requested_quantity={quantity}, available_quantity={available_quantity}. '
                            f'Will withdraw available quantity.'
                        )
                        item_list.append({'code': item_code, 'quantity': available_quantity})
                    else:
                        item_list.append({'code': item_code, 'quantity': quantity})
                else:
                    logger.warning(f'Skipping withdrawal of {quantity} {item_code}')

            if item_list:
                status_code, result, error = self.actions_client.withdraw(character, item_list)

                match status_code:
                    case 200:
                        logger.debug(f'Withdrawn items={item_list} from bank.')
                        if task.task_id:
                            for item in result.items:
                                self.service.subtract_from_bank_reservation(task.task_id, item.code, item.quantity, character.name)
                                try:
                                    self.withdraw_table.update(item.code)
                                except Exception as e:
                                    logger.error(e)

                    case 404:
                        logger.warning(f'Requested item not found in bank: {item_map}')

                    case 461:  # A transaction is already in progress with this item/your golds in your bank.
                        action_result.repeat()

                    case 497:  # The character's inventory is full.
                        reloaded_character = self.service.get_character_details(character.name)
                        action_result.update_character(reloaded_character)

                        inventory_total = reloaded_character.inventory_map.total()
                        withdraw_total = Counter(item_map).total()
                        max_inventory = reloaded_character.inventory_max_items

                        excess = inventory_total + withdraw_total - max_inventory
                        deposit_teleport_items = Counter()
                        for item_code, item_quantity in reloaded_character.inventory_map.items():
                            if deposit_teleport_items.total() < excess:
                                if self.service.get_item(item_code).is_teleport_item:
                                    deposit_teleport_items[item_code] += item_quantity

                        if deposit_teleport_items.total() >= excess:
                            action_result.append(Task.deposit(items=deposit_teleport_items, task_id=task.task_id))
                            action_result.repeat()
                            logger.warning(
                                f'Plan to deposit teleport items: {dict(deposit_teleport_items)} to make room for '
                                f'expected items to withdraw: {item_map}; excess={excess}'
                            )
                        else:
                            message = (
                                f"The character's inventory is full. Expected inventory before transaction={dict(character.inventory_map)}, "
                                f'actual inventory={dict(reloaded_character.inventory_map)}, items to withdraw={item_map}'
                            )
                            logger.error(message)
                            action_result.abort(message)

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

                    case _:
                        logger.error(f'Unexpected response: {error}')
                        action_result.abort(f'{task.action}: {error}')

                if result and result.character:
                    action_result.update_character(result.character)
        return action_result
