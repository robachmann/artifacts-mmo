from typing import Dict

from artifactsmmo.actions.action_result import ActionResult
from artifactsmmo.actions.action_strategy import ActionStrategy
from artifactsmmo.extensions import CharacterSchemaExtension
from artifactsmmo.log.logger import logger
from artifactsmmo.service.execution_context import ExecutionContext
from artifactsmmo.service.tasks import Task


class SleepAction(ActionStrategy):
    def action(self) -> str:
        return 'sleep'

    @staticmethod
    def describe_task(task: Task) -> str:
        return ''

    def process(self, character: CharacterSchemaExtension, task: Task, quest_id: str = None, context: ExecutionContext = None) -> ActionResult:
        action_result: ActionResult = ActionResult()
        leader = task.extra.get('leader')
        seconds = task.extra.get('seconds', 30)
        reload_character = bool(task.extra.get('reload_character', True))
        items_map: Dict[str, int] = task.extra.get('items_map')

        if seconds <= 0:
            return action_result

        if task.task_id and (leader is None or leader == character.name):
            bank_items_map = self.service.get_bank_items_map(task_id=task.task_id, character_name=character.name)
            global_quantity_map = self.service.get_global_quantity_map(
                bank_items_map=bank_items_map, all_characters_inventory_map=self.service.get_all_characters_inventory_map()
            )

            if items_map:
                will_sleep = False
                all_items_available = True
                for item_code, quantity_requested in items_map.items():
                    quantity_available = bank_items_map.get(item_code, 0)
                    if quantity_available < quantity_requested:
                        global_availability = global_quantity_map.get(item_code, 0)
                        if quantity_requested <= global_availability:
                            log_msg = (
                                f'Bank does not hold requested quantity {quantity_requested} of item={item_code} '
                                f'(available={quantity_available}). 💤 Sleep for seconds={seconds}, ttl={task.ttl}'
                            )
                            if task.ttl > 1:
                                logger.debug(log_msg)
                            else:
                                logger.warning(log_msg)
                            action_result.update_expiration(seconds=seconds)
                            will_sleep = True
                        else:
                            logger.warning(
                                f'Bank does not hold requested quantity {quantity_requested} of item={item_code} '
                                f'(global_availability={global_availability}). Will not sleep anymore.'
                            )
                            task.ttl = 0
                            all_items_available = False
                        break
                if not will_sleep and all_items_available:
                    logger.info('All requested items are available, setting ttl to 0')
                    task.ttl = 0
        else:
            logger.info(f'💤 Sleep for seconds={seconds}.')
            action_result.update_expiration(seconds=seconds)
            if reload_character:
                action_result.append(Task.reload_character())

        return action_result
