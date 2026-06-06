from collections import Counter
from datetime import datetime, UTC
import math
from typing import Dict

from artifactsmmo.actions.action_result import ActionResult
from artifactsmmo.actions.action_strategy import ActionStrategy
from artifactsmmo.client.actions import ActionsClient
from artifactsmmo.dynamodb.character_table import CharacterTable
from artifactsmmo.dynamodb.counters_table import CountersTable
from artifactsmmo.dynamodb.skill_stats_table import SkillStatsTable
from artifactsmmo.dynamodb.task_progress_table import TaskProgressTable
from artifactsmmo.extensions import CharacterSchemaExtension, ItemSchemaExtension
from artifactsmmo.log.logger import logger
from artifactsmmo.service.execution_context import ExecutionContext
from artifactsmmo.service.food_service import FoodService
from artifactsmmo.service.service import Service
from artifactsmmo.service.tasks import Task
from artifactsmmo.telegram.client import TelegramClient


class DistributeFoodAction(ActionStrategy):
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
        self.processed_food_map: Dict[str, ItemSchemaExtension] = {f.code: f for f in self.service.get_processed_food()}

    def action(self) -> str:
        return 'distribute-food'

    def process(self, character: CharacterSchemaExtension, task: Task, quest_id: str = None, context: ExecutionContext = None) -> ActionResult:
        action_result: ActionResult = ActionResult()

        available_food = Counter()
        for item_code, item_qty in character.inventory_map.items():
            if item_code in self.processed_food_map:
                available_food[item_code] += item_qty

        if available_food:
            receiver = min(
                (
                    c
                    for c in self.service.get_all_character_details()
                    if c.map_id == character.map_id and c.name != character.name and c.inventory_map.total() < 0.9 * c.inventory_capacity()
                ),
                key=lambda c: c.cooldown_expiration,
                default=None,
            )
            if receiver:
                cooldown = (receiver.cooldown_expiration - datetime.now(UTC)).total_seconds()
                if cooldown > 1:
                    sleep_seconds = max(30, math.ceil(cooldown) + 5)
                    logger.info(f'Soonest expiration of receiver is in {cooldown} seconds. Sleeping for {sleep_seconds} seconds.')
                    action_result.append(Task.sleep(seconds=sleep_seconds))
                    action_result.repeat()
                else:
                    self.__give_to_receiver(character, receiver, available_food, action_result, task)
            else:
                logger.warning(f'No characters stand at map_id={character.map_id}')

        return action_result

    def __give_to_receiver(
        self,
        character: CharacterSchemaExtension,
        receiver: CharacterSchemaExtension,
        available_food: Dict[str, int],
        action_result: ActionResult,
        task: Task,
    ):
        remaining_space = int(receiver.inventory_capacity() * 0.9) - receiver.inventory_map.total()
        logger.info(f'Receiver has {remaining_space} remaining slots in his inventory.')

        food_map: Counter[str] = Counter()
        for item_code, item_qty in available_food.items():
            pack_qty = min(remaining_space, item_qty)
            food_map[item_code] = pack_qty
            remaining_space -= pack_qty
            if not remaining_space:
                break

        if food_map:
            item_map = dict(food_map)
            logger.info(f'Giver {character.name} plans to give food_map={item_map} to receiver={receiver.name}')

            status_code, result, error = self.actions_client.give(character, receiver, item_map)

            match status_code:
                case 200:
                    logger.info(f'{character.name} has successfully handed over {item_map} to receiver={receiver.name}. ')
                    item_count = sum(i.quantity for i in result.character.inventory if i.code and i.code in self.processed_food_map)
                    if item_count:
                        logger.info(f'Character has {item_count} food items left in its inventory. Will retry after cooldown expired.')
                        action_result.repeat()

                case 499:  # The character is in cooldown.
                    msg = error.get('message', '')
                    character_cooldown = msg if msg else 'The character is in cooldown.'
                    logger.info(f'{character_cooldown} Fetching current character again.')
                    reloaded_character = self.service.get_character_details(character.name)
                    action_result.update_character(reloaded_character)
                    action_result.repeat()

                case _:
                    logger.error(f'Unexpected response: {error}.')
                    action_result.abort(f'{task.action}: {error}')

            if result and result.character:
                action_result.update_character(result.character)
        else:
            logger.error(f'Could not determine food to hand over to {receiver.name}')
