from collections import defaultdict
from datetime import timedelta
from typing import List

from artifactsmmo.extensions import CharacterSchemaExtension
from artifactsmmo.game_constants import MAX_LEVEL
from artifactsmmo.log.logger import logger
from artifactsmmo.models import CraftSkill
from artifactsmmo.service.execution_context import ExecutionContext
from artifactsmmo.service.tasks import NextMove, Task
from artifactsmmo.templates.template_result import TemplateResult
from artifactsmmo.templates.template_strategy import TemplateStrategy


class CraftRecipeTemplate(TemplateStrategy):
    def template(self) -> str:
        return 'craft-recipe'

    def describe_task(self, task: Task) -> str:
        target = ' (♻️)' if task.extra.get('target') == 'recycle' else ''
        item_code = str(task.extra.get('item'))
        item_qty = int(task.extra.get('quantity', 1))
        if task.extra.get('global_max'):
            return f'up to {task.extra.get("global_max")}x {item_code}{target}'
        else:
            total_qty = item_qty * task.ttl if task.ttl else item_qty
            if total_qty >= 5:
                # self.service.calculate_craft_recipe_time({item_code: total_qty})
                etc_str = f' ⏱️ ~{timedelta(seconds=30 + total_qty * 5)}'
            else:
                etc_str = ''
            return f'{total_qty}x {item_code}{target}{etc_str}'

    def render(self, character: CharacterSchemaExtension, task: Task, quest_id: str = None, context: ExecutionContext = None) -> TemplateResult:
        template_result: TemplateResult = TemplateResult()
        extra = task.extra
        item_code = extra.get('item')
        quantity = int(extra.get('quantity', 1))
        allow_fewer = bool(extra.get('allow_fewer', False))
        global_max = extra.get('global_max')
        target = extra.get('target', 'bank')
        leader = extra.get('leader')

        if leader is None or leader == character.name:
            if global_max is not None:
                global_quantity = self.service.get_global_quantity(item_code)
                additional_quantity = max(min((global_max - global_quantity), quantity), 0)
                if additional_quantity != quantity:
                    logger.info(
                        f'Crafting item={item_code}, global_quantity={global_quantity}, '
                        f'quantity={quantity}, global_max={global_max}, additional_quantity={additional_quantity}'
                    )
                    quantity = additional_quantity
            else:
                logger.info(
                    f'Crafting item={item_code}, global_quantity=None, '
                    f'quantity={quantity}, global_max={global_max}, additional_quantity={quantity}'
                )

            if quantity > 0:
                if item_code:
                    task_list = self.generate_craft_recipe_tasks(
                        character=character,
                        item_code=item_code,
                        quantity=quantity,
                        allow_fewer=allow_fewer,
                        target=target,
                        task_id=task.task_id,
                        leader=leader,
                    )
                    template_result.extend(task_list)
                    template_result.quest_status(f'{quantity}x {item_code}')
                else:
                    logger.warning('item is None, cannot create craft recipe')

        return template_result

    def generate_craft_recipe_tasks(
        self,
        character: CharacterSchemaExtension,
        item_code,
        quantity,
        allow_fewer: bool = False,
        target: str = 'bank',
        task_id: str = None,
        leader: str = None,
    ) -> List[Task]:
        new_tasks = []

        item = self.service.get_item(item_code)
        craft = item.craft
        if craft:
            required_skill = str(craft.skill)
            required_skill_level = craft.level
            character_skill_level = character.skills[required_skill].level
            if character_skill_level < required_skill_level:
                if required_skill in (CraftSkill.MINING, CraftSkill.WOODCUTTING, CraftSkill.ALCHEMY):
                    for level in range(character_skill_level + 1, required_skill_level + 1):
                        new_tasks.append(Task.level_skill(skill=required_skill, target_level=level, stock_only=True))
                        new_tasks.append(Task.level_skill(skill=required_skill, target_level=level))
                else:
                    new_tasks.append(Task.level_skill(skill=required_skill, target_level=required_skill_level))
                logger.warning(
                    f'Character skill level for {required_skill} ({character_skill_level}) '
                    f'is insufficient (required: {required_skill_level}). Adding task to level skill and retry.'
                )

            bank_items_map = self.service.get_bank_items_map(task_id=task_id, character_name=character.name)
            resolved_item_recipe = self.service.resolve_item_recipe(item_code=item_code, bank_items_map=bank_items_map, quantity=quantity)
            if resolved_item_recipe.missing_items:
                craftable_quantities: List[int] = []
                for missing_code, missing_quantity in resolved_item_recipe.missing_items.items():
                    all_quantity = resolved_item_recipe.all_items[missing_code]
                    available_quantity = all_quantity - missing_quantity
                    craftable_quantities.append(int(available_quantity / all_quantity * quantity))
                craftable_quantity = min(craftable_quantities)
                logger.warning(
                    f'Crafting {quantity}x item={item_code} requires missing_items={dict(resolved_item_recipe.missing_items)}, '
                    f'craftable_quantity={craftable_quantity}, allow_fewer={allow_fewer}'
                )
                if allow_fewer:
                    quantity = craftable_quantity
                else:
                    quantity = 0

            if quantity > 0:
                teleport_item_codes = self.service.get_teleport_item_codes()
                inventory_max_items = character.inventory_capacity(teleport_item_codes)
                total_quantity_per_craft = sum(item.quantity for item in craft.items)
                total_quantity_recipe = quantity * total_quantity_per_craft

                if total_quantity_recipe <= inventory_max_items:  # means it can be done in just one go.
                    craft_dependencies_tasks = []
                    withdraw_map = defaultdict(int)
                    for i in craft.items:
                        required_quantity = i.quantity * quantity

                        bank_available = bank_items_map.get(i.code, 0)
                        withdraw_quantity = min(required_quantity, bank_available)
                        craft_quantity = required_quantity - withdraw_quantity

                        if craft_quantity > 0:
                            dependency = self.service.get_item(i.code)
                            if dependency.craft or dependency.is_npc_item:
                                logger.info(f'Plan to craft dependency {craft_quantity}x {dependency.code} for item {item_code}')
                            else:
                                logger.warning(
                                    f'No need to craft dependency {craft_quantity}x {dependency.code} for item {item_code}, '
                                    f'available={bank_available}, required_quantity={required_quantity}'
                                )

                            craft_dependencies_tasks.append(
                                Task.craft_recipe(
                                    item=i.code,
                                    quantity=craft_quantity,
                                    allow_fewer=allow_fewer,
                                    target='bank',
                                    leader=leader,
                                    task_id=task_id,
                                )
                            )
                        withdraw_map[i.code] += required_quantity

                    new_tasks.extend(craft_dependencies_tasks)

                    craft_yields_xp = self.__craft_yields_xp(character_skill_level, required_skill_level)
                    if craft_yields_xp:
                        logger.info(
                            f'Plan to equip wisdom gear, character_skill_level={character_skill_level}, '
                            f'required_skill_level={required_skill_level}'
                        )
                        new_tasks.append(Task.equip_wisdom_gear(task_id=task_id))

                    if withdraw_map:
                        new_tasks.append(
                            Task.ensure_inventory(
                                item_map=withdraw_map, task_id=task_id, next_move=NextMove(content_type='workshop', content_code=required_skill)
                            )
                        )

                        new_tasks.append(
                            Task.craft(
                                task_id=task_id,
                                item=item_code,
                                quantity=quantity,
                                allow_fewer=allow_fewer,
                                skill=required_skill,
                                target=target,
                                recraft=target == 'recycle',
                            )
                        )

                else:  # multiple runs required
                    quantity_per_iteration = inventory_max_items // total_quantity_per_craft
                    quantity_bucket = quantity_per_iteration * total_quantity_per_craft
                    iterations = total_quantity_recipe // quantity_bucket

                    new_tasks.append(
                        Task.craft_recipe(
                            item=item_code,
                            quantity=quantity_per_iteration,
                            allow_fewer=allow_fewer,
                            ttl=iterations,
                            target=target,
                            task_id=task_id,
                            leader=leader,
                        )
                    )
                    remainder_str = ''
                    if (quantity_remainder := total_quantity_recipe % quantity_bucket) > 0:
                        quantity_last_iteration = quantity_remainder // total_quantity_per_craft
                        new_tasks.append(
                            Task.craft_recipe(
                                item=item_code,
                                quantity=quantity_last_iteration,
                                target=target,
                                allow_fewer=allow_fewer,
                                task_id=task_id,
                                leader=leader,
                            )
                        )
                        remainder_str = f'quantity_remainder={quantity_remainder}, quantity_last_iteration={quantity_last_iteration}'

                    logger.info(
                        f'Craft {item_code} {quantity} times, quantity_per_iteration={quantity_per_iteration}, '
                        f'quantity_bucket={quantity_bucket}, iterations={iterations}, remainder_str={remainder_str}'
                    )
            else:
                logger.warning(f'Cannot craft any of {item_code} with the available items.')
        else:
            origin = self.service.get_item_origin(item_code)
            if origin and origin.npcs and not origin.tasks and not origin.resources and not origin.monsters:
                logger.info(f'item={item_code} needs to be obtained from npc={list(origin.npcs.keys())[0]}')
                for npc_code, npc_offer in origin.npcs.items():
                    if npc_offer.price and npc_offer.currency:
                        new_tasks.append(Task.buy_from_npc(item_code, npc_code, quantity=quantity, task_id=task_id))
                        break
            else:
                logger.info(f'item_code {item_code} cannot be crafted.')
        return new_tasks

    @staticmethod
    def __craft_yields_xp(character_skill_level: int, required_skill_level: int) -> bool:
        return character_skill_level <= required_skill_level + 10 and character_skill_level < MAX_LEVEL
