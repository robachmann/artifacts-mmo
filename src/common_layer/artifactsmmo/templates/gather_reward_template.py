from artifactsmmo.extensions import CharacterSchemaExtension
from artifactsmmo.log.logger import logger
from artifactsmmo.service.execution_context import ExecutionContext
from artifactsmmo.service.tasks import Task
from artifactsmmo.templates.template_result import TemplateResult
from artifactsmmo.templates.template_strategy import TemplateStrategy


class GatherRewardTemplate(TemplateStrategy):
    def template(self) -> str:
        return 'gather-reward'

    @staticmethod
    def describe_task(task: Task) -> str:
        return f'{task.extra.get("quantity")}x {task.extra.get("item")}'

    def render(self, character: CharacterSchemaExtension, task: Task, quest_id: str = None, context: ExecutionContext = None) -> TemplateResult:
        template_result: TemplateResult = TemplateResult()
        extra = task.extra
        item_code = extra.get('item')
        required_quantity = int(extra.get('quantity') or 1)
        leader = extra.get('leader')
        task_type = extra.get('task_type') or 'items'

        if (leader is None or leader == character.name) and required_quantity > 0 and item_code:
            bank_items_map = self.service.get_bank_items_map(task_id=task.task_id, character_name=character.name)
            available_quantity = bank_items_map.get(item_code, 0)
            carry_quantity = character.inventory_map.get(item_code, 0)

            logger.info(
                f'reward_item={item_code}, required_quantity={required_quantity}, available_quantity={available_quantity}, carry_quantity={carry_quantity}, task_id={task.task_id}.'
            )

            if available_quantity + carry_quantity < required_quantity:
                logger.info('Plan to solve tasks and exchange task coins.')
                if available_quantity > 0:
                    self.service.add_bank_reservation(task.task_id, item_code, available_quantity, character.name)

                template_result.append(Task.solve_task(False, True, task_type, task_id=task.task_id))
                template_result.append(Task.exchange_task_coins())
                template_result.repeat()
            else:
                logger.info(
                    f'reward_item={item_code}, required_quantity={required_quantity} matches available_quantity={available_quantity}, task_id={task.task_id}.'
                    f'No further tasks required.'
                )

        return template_result
