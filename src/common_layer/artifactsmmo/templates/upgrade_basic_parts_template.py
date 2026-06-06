from typing import Dict, List, Optional

from artifactsmmo.extensions import CharacterSchemaExtension, ItemSchemaExtension
from artifactsmmo.log.logger import logger
from artifactsmmo.models import ItemType, SimpleItemSchema
from artifactsmmo.service.execution_context import ExecutionContext
from artifactsmmo.service.tasks import Task
from artifactsmmo.templates.common_templates import gather_and_craft_recipe
from artifactsmmo.templates.template_result import TemplateResult
from artifactsmmo.templates.template_strategy import TemplateStrategy


class UpgradeBasicPartsTemplate(TemplateStrategy):
    def template(self) -> str:
        return 'upgrade-basic-parts'

    @staticmethod
    def describe_task(task: Task) -> str:
        return f'using {task.extra.get("skill")}' if task.extra.get('skill') else ''

    def render(self, character: CharacterSchemaExtension, task: Task, quest_id: str = None, context: ExecutionContext = None) -> TemplateResult:
        template_result: TemplateResult = TemplateResult()

        bank_item_map = self.service.get_bank_items_map(task_id=task.task_id, character_name=character.name)
        craft_into_map = self.service.get_items_craft_into()
        sorted_items: List[ItemSchemaExtension] = sorted(self.service.get_all_items(), key=lambda i: i.level, reverse=True)
        gather_missing_parts = bool(task.extra.get('gather_missing_parts', False))
        skill: Optional[str] = task.extra.get('skill')
        exclude_items: List[str] = task.extra.get('exclude_items') or []
        include_items: List[str] = task.extra.get('include_items') or []
        participants = task.extra['participants'] or []

        recipe_map: Dict[str, dict] = {}
        for item in sorted_items:
            if item.code in exclude_items:
                logger.info(f'Skipping item={item.code} as a possible craft candidate.')
                continue

            if item.craft and (
                item.code in include_items or len(item.craft.items) == 1 or (item.type == ItemType.CONSUMABLE and len(item.craft.items) < 3)
            ):
                contains_one_way_parts = False
                craftable_recipes = 0 if gather_missing_parts else 1e9

                for crafts in item.craft.items:
                    craft_item_code = crafts.code
                    craft_into_items = craft_into_map.get(craft_item_code)
                    contains_one_way_parts = (
                        contains_one_way_parts or item.code in include_items or (len(craft_into_items) == 1 or self.is_fish(crafts))
                    )

                    current_stock = bank_item_map.get(craft_item_code, 0)
                    quantity = crafts.quantity
                    recipe_quantity = current_stock // quantity
                    if gather_missing_parts:
                        craftable_recipes = max(craftable_recipes, recipe_quantity)
                    else:
                        craftable_recipes = min(craftable_recipes, recipe_quantity)

                if contains_one_way_parts and craftable_recipes > 0:
                    required_skill = str(item.craft.skill)
                    if not skill or skill == required_skill:
                        required_skill_level = item.craft.level
                        current_skill_level = character.skills[required_skill].level
                        if current_skill_level >= required_skill_level:
                            logger.info(f'Plan to craft {craftable_recipes}x {item.code} from available parts.')
                            if gather_missing_parts:
                                destination = str(item.craft.skill)
                                recipe_map.setdefault(destination, dict(count=0, recipes=[]))
                                recipe_map[destination]['count'] += craftable_recipes
                                recipe_map[destination]['recipes'].append(
                                    dict(
                                        quantity=craftable_recipes,
                                        item=item.code,
                                        leader=character.name,
                                        allow_fewer=True,
                                        level=item.level,
                                        bank_qty=bank_item_map.get(item.code, 0),
                                        gather_recipe=True,
                                        destination=destination,
                                    )
                                )

                            else:
                                resolved_recipe = self.service.resolve_item_recipe(item.code, bank_item_map, craftable_recipes, read_only=False)
                                reservation_id = Task.generate_task_id()
                                for reserve_code, reserve_quantity in resolved_recipe.available_items.items():
                                    self.service.add_bank_reservation(
                                        task_id=reservation_id,
                                        item_code=reserve_code,
                                        quantity=reserve_quantity,
                                        character_name=character.name,
                                    )

                                destination = str(item.craft.skill)
                                recipe_map.setdefault(destination, dict(count=0, recipes=[]))
                                recipe_map[destination]['count'] += craftable_recipes
                                recipe_map[destination]['recipes'].append(
                                    dict(
                                        task_id=reservation_id,
                                        item=item.code,
                                        quantity=craftable_recipes,
                                        leader=character.name,
                                        allow_fewer=True,
                                        level=item.level,
                                        bank_qty=bank_item_map.get(item.code, 0),
                                        destination=destination,
                                    )
                                )
            else:
                if not skill:
                    origin = self.service.get_item_origin(item.code)
                    if origin and origin.npcs and not origin.resources and not origin.monsters and not origin.tasks:
                        for npc_code, offer in origin.npcs.items():
                            if offer.currency != 'gold' and (
                                len(self.service.get_item_products(offer.currency)) == 1 or item.code in include_items
                            ):
                                current_stock = bank_item_map.get(offer.currency, 0)

                                recipe_quantity = current_stock // offer.price
                                if recipe_quantity > 0:
                                    reservation_id = Task.generate_task_id()

                                    self.service.add_bank_reservation(
                                        task_id=reservation_id,
                                        item_code=offer.currency,
                                        quantity=recipe_quantity * offer.price,
                                        character_name=character.name,
                                    )

                                    destination = npc_code
                                    recipe_map.setdefault(destination, dict(count=0, recipes=[]))
                                    recipe_map[destination]['count'] += recipe_quantity
                                    recipe_map[destination]['recipes'].append(
                                        dict(
                                            task_id=reservation_id,
                                            item=item.code,
                                            quantity=recipe_quantity,
                                            leader=character.name,
                                            level=item.level,
                                            bank_qty=bank_item_map.get(item.code, 0),
                                            destination=npc_code,
                                        )
                                    )
                                    logger.info(
                                        f'Plan to exchange {recipe_quantity * offer.price}x {offer.currency} for {recipe_quantity}x {item.code} at npc {npc_code}.'
                                    )
                                break

        sorted_recipe_map = dict(sorted(recipe_map.items(), key=lambda x: x[1]['count'], reverse=True))

        for destination, data in sorted_recipe_map.items():
            recipe_list = data['recipes']
            recipe_list.sort(key=lambda x: (-x['bank_qty'], x['quantity'], x['level']))

            for recipe in recipe_list:
                if 'gather_recipe' in recipe:
                    template_result.extend(
                        gather_and_craft_recipe(
                            quantity=recipe.get('quantity'),
                            item=recipe.get('item'),
                            leader=recipe.get('leader'),
                            allow_fewer=recipe.get('allow_fewer'),
                        )
                    )
                else:
                    template_result.append(
                        Task.craft_items_parallel(
                            task_id=recipe.get('task_id'),
                            item=recipe.get('item'),
                            quantity=recipe.get('quantity'),
                            participants=participants,
                        )
                        # Task.craft_recipe(
                        #     task_id=recipe.get('task_id'),
                        #     item=recipe.get('item'),
                        #     quantity=recipe.get('quantity'),
                        #     leader=recipe.get('leader'),
                        #     allow_fewer=recipe.get('allow_fewer'),
                        # )
                    )

        return template_result

    def is_fish(self, param: SimpleItemSchema):
        item = self.service.get_item(param.code)
        return item.type == ItemType.RESOURCE and item.subtype == 'fishing'
