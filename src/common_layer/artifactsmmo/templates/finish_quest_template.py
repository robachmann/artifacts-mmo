from artifactsmmo.extensions import CharacterSchemaExtension
from artifactsmmo.log.logger import logger
from artifactsmmo.service.execution_context import ExecutionContext
from artifactsmmo.service.tasks import Task
from artifactsmmo.templates.template_result import TemplateResult
from artifactsmmo.templates.template_strategy import TemplateStrategy


class FinishQuestTemplate(TemplateStrategy):
    def template(self) -> str:
        return 'finish-quest'

    @staticmethod
    def describe_task(task: Task) -> str:
        return ''

    def render(self, character: CharacterSchemaExtension, task: Task, quest_id: str = None, context: ExecutionContext = None) -> TemplateResult:
        template_result: TemplateResult = TemplateResult()
        skip_post_tasks = bool(task.extra.get('skip_post_tasks', False))
        should_rest = bool(task.extra.get('rest', False))
        use_city_bank = bool(task.extra.get('use_city_bank', True))

        if not skip_post_tasks:
            logger.info(f'Adding post-tasks, use_city_bank={use_city_bank}')
            consumable_map = self.check_consumables(character)
            if consumable_map:
                for item_code, item_qty in consumable_map.items():
                    template_result.append(Task.use_item(item_code, item_qty))

            template_result.extend(
                [
                    Task.ensure_inventory(use_city_bank=use_city_bank, keep_consumables=True),
                    Task.finish_task(),
                    Task.unequip_all(),
                    Task.ensure_inventory(use_city_bank=use_city_bank),
                ]
            )

        template_result.append(Task.move_success())

        if should_rest:
            template_result.append(Task.rest())

        return template_result

    def check_consumables(self, character: CharacterSchemaExtension):
        total_additional_hp = 0
        for item_code, item_qty in character.equipped_items.items():
            item = self.service.get_item(item_code)
            total_additional_hp += item.item_effects.get('hp', 0) * item_qty

        if total_additional_hp >= character.hp:
            return self.food_service.get_best_food_to_consume(character, total_additional_hp)
        else:
            return {}
