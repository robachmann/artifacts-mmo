from artifactsmmo.extensions import CharacterSchemaExtension
from artifactsmmo.log.logger import logger
from artifactsmmo.service.execution_context import ExecutionContext
from artifactsmmo.service.tasks import Task
from artifactsmmo.templates.template_result import TemplateResult
from artifactsmmo.templates.template_strategy import TemplateStrategy


class EnsureItemTemplate(TemplateStrategy):
    def template(self) -> str:
        return 'ensure-item'

    @staticmethod
    def describe_task(task: Task) -> str:
        target = ' (♻️)' if task.extra.get('target') == 'recycle' else ''
        global_max = task.extra.get('global_max') if task.extra.get('global_max') else 1
        return f'up to {global_max}x {task.extra.get("item")}{target}'

    def render(self, character: CharacterSchemaExtension, task: Task, quest_id: str = None, context: ExecutionContext = None) -> TemplateResult:
        template_result: TemplateResult = TemplateResult()

        item_code: str = task.extra['item']
        #    quantity: int = task.extra.get('quantity')
        force_gather: bool = task.extra.get('force_gather', False)
        allow_fewer: bool = task.extra.get('allow_fewer', False)
        leader: str = task.extra.get('leader', character.name)
        target: str = task.extra.get('target', 'bank')
        global_max: int = task.extra.get('global_max', 1)
        request_support: bool = task.extra.get('request_support', False)
        reserve_target_product: bool = task.extra.get('reserve_target_product', True)

        item = self.service.get_item(item_code)
        global_quantity = self.service.get_global_quantity(item_code)
        if global_max <= global_quantity:
            logger.info(
                f'Requested global_max={global_max} of item={item_code} already fulfilled with global_quantity={global_quantity}, nothing to craft.'
            )
        else:
            recipe_id = Task.generate_task_id()
            template_result.append(
                Task.gather_recipe(
                    task_id=recipe_id,
                    item=item_code,
                    quantity=global_max,
                    force_gather=force_gather,
                    global_max=global_max,
                    leader=leader,
                    request_support=request_support,
                    reserve_target_product=reserve_target_product,
                )
            )
            if item.craft:
                template_result.append(
                    Task.craft_recipe(
                        task_id=recipe_id,
                        item=item_code,
                        quantity=global_max,
                        allow_fewer=allow_fewer,
                        global_max=global_max,
                        target=target,
                        leader=leader,
                    )
                )

        return template_result
