from typing import List

from artifactsmmo.extensions import CharacterSchemaExtension
from artifactsmmo.game_constants import RECYCLING_SKILLS
from artifactsmmo.log.logger import logger
from artifactsmmo.models import AccountAchievementSchema, AchievementType
from artifactsmmo.service.execution_context import ExecutionContext
from artifactsmmo.service.tasks import Task
from artifactsmmo.templates.common_templates import gather_and_craft_recipe
from artifactsmmo.templates.template_result import TemplateResult
from artifactsmmo.templates.template_strategy import TemplateStrategy


class SolveRecyclingAchievementsTemplate(TemplateStrategy):
    def template(self) -> str:
        return 'solve-recycling-achievements'

    @staticmethod
    def describe_task(task: Task) -> str:
        return f'of type {task.extra.get("type")}' if task.extra.get('type') else ''

    def render(self, character: CharacterSchemaExtension, task: Task, quest_id: str = None, context: ExecutionContext = None) -> TemplateResult:
        template_result: TemplateResult = TemplateResult()
        skill_filter = task.extra.get('skill')
        buy_from_ge = bool(task.extra.get('buy_from_ge', False))
        gather_parts = bool(task.extra.get('gather_parts', True))

        achievements: List[AccountAchievementSchema] = self.service.get_account_achievements(character.account)
        remaining_recycling_count = 0
        for achievement in achievements:
            if achievement.type == AchievementType.RECYCLING:
                remaining_recycling_count = max(remaining_recycling_count, achievement.total - achievement.current)

        if remaining_recycling_count > 0:
            if buy_from_ge:
                orders = self.service.get_recyclable_ge_orders()
                for order in orders:
                    logger.info(f'Plan to buy {order.quantity}x {order.code}')
                    template_result.append(Task.buy_order(order.id))

            craftable_items = self.service.get_currently_craftable_items(character, skill_filter=RECYCLING_SKILLS)

            if craftable_items:
                logger.info(f'Plan to craft and recycle {sum(i.quantity for i in craftable_items)}/{remaining_recycling_count} items.')

            # all_character_details: List[CharacterSchemaExtension] = self.service.get_all_character_details()
            # min_character_level: int = min(c.level for c in all_character_details)
            # min_character_level_threshold: int = max(1, min_character_level - 20)
            # available_items_map: Dict[str, int] = self.service.get_global_quantity_map()
            # available_tools: Dict[str, Dict[int, int]] = self.service.get_available_tools(available_items_map)
            # skill_map = self.service.get_skill_map([character])

            for item in craftable_items:
                quantity = min(remaining_recycling_count, item.quantity)
                if quantity > 0:
                    # available_items_map[item.code] += quantity
                    # disposal_quantity: int = self.service.get_disposal_quantity(
                    #     item.code,
                    #     available_tools,
                    #     available_items_map,
                    #     min_character_level_threshold,
                    #     quantity,
                    #     skill_filter,
                    #     skill_map,
                    # )
                    # deposit_quantity = quantity #- disposal_quantity

                    # if deposit_quantity > 0:
                    template_result.append(Task.craft_recipe(item=item.code, quantity=quantity, target='recycle', leader=character.name))
                    logger.info(f'Plan to craft and recycle {quantity}x {item.code}.')

                    # if disposal_quantity > 0:
                    #    template_result.append(
                    #        Task.craft_recipe(item=item.code, quantity=disposal_quantity, target='recycle', leader=character.name)
                    #    )
                    #    logger.info(f'Plan to craft and recycle {disposal_quantity}x {item.code}.')

                    remaining_recycling_count -= quantity

            if not template_result.new_tasks and gather_parts:
                items = self.service.get_quickest_recyclable_items(
                    item_count=min(remaining_recycling_count, 100),
                    min_level=1,
                    max_level=25,
                    skill_filter=RECYCLING_SKILLS,
                    ignore_bank_reservations=False,
                    include_task_drops=False,
                    include_event_drops=False,
                )
                if items:
                    craft_item = items[0]
                    template_result.extend(
                        gather_and_craft_recipe(quantity=craft_item.quantity, item=craft_item.item_code, leader=character.name, target='recycle')
                    )
                    logger.info(f'Plan to craft and recycle {craft_item.quantity}x {craft_item.item_code}.')

        if template_result.new_tasks:
            # template_result.append(Task.recycle_excess_items())
            template_result.repeat()

        return template_result
