from collections import Counter, defaultdict
from copy import copy
from dataclasses import dataclass
import itertools
from typing import Any, Dict, List, Optional, Set

from artifactsmmo.extensions import CharacterSchemaExtension, ItemSchemaExtension, MonsterSchemaExtension
from artifactsmmo.log.logger import logger
from artifactsmmo.service.execution_context import ExecutionContext
from artifactsmmo.service.helpers import escape_string
from artifactsmmo.service.tasks import NextMove, Task
from artifactsmmo.service.until import Until
from artifactsmmo.templates.template_result import TemplateResult
from artifactsmmo.templates.template_strategy import TemplateStrategy


@dataclass
class CraftCombination:
    craft_map: Dict[str, int]
    total_seconds: int
    finished_in: float
    contains_leader: bool


class CraftItemsParallelTemplate(TemplateStrategy):
    def template(self) -> str:
        return 'craft-items-parallel'

    @staticmethod
    def describe_task(task: Task) -> str:
        item_code = task.extra['item']
        item_quantity = task.extra['quantity']
        participants = task.extra['participants']
        participants_str = f'with {", ".join(participants)}' if participants else ''
        return f'{item_quantity}x {item_code} {participants_str}'

    def render(self, character: CharacterSchemaExtension, task: Task, quest_id: str = None, context: ExecutionContext = None) -> TemplateResult:
        template_result: TemplateResult = TemplateResult()

        item_code = task.extra['item']
        item_quantity = task.extra['quantity']
        participants = task.extra['participants']

        bank_items_map = self.service.get_bank_items_map(task_id=task.task_id, context=context)
        item = self.service.get_item(item_code)

        eligible_characters: List[CharacterSchemaExtension] = self.__filter_eligible_characters(character, participants, item)
        character_map = {c.name: c for c in eligible_characters}

        if eligible_characters:
            logger.info(f'Eligible characters to craft {item_code}: {", ".join(c.name for c in eligible_characters)}')
            resolved_item_recipe = self.service.resolve_item_recipe(item_code, bank_items_map, item_quantity)

            if resolved_item_recipe.missing_items:
                logger.info(f'Recipe has missing items: {resolved_item_recipe.missing_items}')
                logger.error('FIXME: Implement missing items.')
            else:
                fastest_combination: CraftCombination = self.__find_fastest_combination(
                    character.name, eligible_characters, item, item_quantity, bank_items_map
                )

                logger.info(f'Fastest combination to craft {item_quantity}x {item_code}: {fastest_combination.craft_map}')

                for current_character, i_qty in fastest_combination.craft_map.items():
                    tasks = [Task.craft_recipe(item_code, i_qty, task_id=task.task_id)]

                    if current_character == character.name:
                        template_result.extend(tasks)
                        logger.info(f'Plan to craft {i_qty}x {item_code}.')
                    else:
                        status = f'parallel-item-craft {item_code}'
                        active_quest = self.character_table.get_quest(character.name)
                        self.dispatch_service.dispatch(
                            task_list=tasks,
                            quest_id=quest_id,
                            is_new_quest_id=True,
                            character=character_map[current_character],
                            status=status,
                            # leader=character.name, # this could prevent crafting items
                            created_at=None,
                            skip_pre_tasks=True,
                            skip_post_tasks=False,
                            active_quest=active_quest,
                        )
                        logger.info(f'Dispatched {current_character} to craft {i_qty}x {item_code}.')

                if len(fastest_combination.craft_map.keys()) > 1:
                    pretty_map_str = ', '.join(f'{k}: {v}' for k, v in fastest_combination.craft_map.items())
                    message = f'{character.name} distributed work to craft {item_quantity}x {item_code}: {pretty_map_str}'
                    self.telegram_client.send_notification(message)

        else:
            logger.error(f'Item {item_code} has no eligible characters.')

        return template_result

    def _calculate_inventory_modifier(self, character: CharacterSchemaExtension, new_equipment: Dict[str, str]) -> int:
        current_modifier = sum(
            inv_space
            for item_c in character.equipped_items
            if (inv_space := self.service.get_item(item_c).item_effects.get('inventory_space', 0)) < 0
        )

        new_modifier = sum(self.service.get_item(item_c).item_effects.get('inventory_space', 0) for item_c in new_equipment.values())

        return character.inventory_max_items - current_modifier + new_modifier

    @staticmethod
    def _prepare_character_tasks(
        equipment: Dict[str, str],
        utilities: Dict[str, int],
        food_map: Optional[Dict[str, int]],
        next_move: NextMove,
        map_id: int,
        monster: MonsterSchemaExtension,
        leader_name: str,
        participants: List[str],
        task_extra_ttl: int,
        until: Until,
        reservation_id: str,
        expected_win_rate: float,
    ) -> List[Task]:
        tasks = [Task.equip_items(items_map=equipment, task_id=reservation_id)]
        if utilities:
            for idx, (item_code, quantity) in enumerate(utilities.items(), 1):
                task = Task.equip_utility(item_code, f'utility{idx}', quantity, False, reservation_id)
                tasks.append(task)

        if food_map:
            tasks.append(
                Task.ensure_inventory(
                    item_map=food_map,
                    next_move=next_move,
                    task_id=reservation_id,
                )
            )
        else:
            tasks.append(Task.move(map_id=map_id))

        tasks.append(
            Task.multi_character_fight(
                monster=monster.code,
                leader=leader_name,
                participants=participants,
                map_id=map_id,
                ttl=task_extra_ttl,
                until=copy(until) if until else None,
                expected_win_rate=expected_win_rate,
                utilities=utilities,
            )
        )

        return tasks

    def _get_food_for_character(
        self,
        character: CharacterSchemaExtension,
        expected_inventory_max_items: Optional[int],
        required_hp_median_max: int,
        required_hp_map_list: List[int],
        fight_times: int,
        monster: MonsterSchemaExtension,
        task: Task,
        context: ExecutionContext,
        is_leader: bool,
    ) -> Optional[Dict[str, int]]:
        """Get the best food map for a character and update context."""
        if is_leader:
            food_map = self.food_service.get_best_food_to_withdraw(
                character=character,
                required_hp=min(character.max_hp, required_hp_median_max),
                lost_hps_per_fight=required_hp_map_list,
                fight_times=fight_times,
                is_event_monster=monster.is_event_monster,
                is_boss_monster=monster.is_boss_monster,
                task_id=task.task_id,
                context=context,
            )
        else:
            food_map = self.food_service.get_best_food_to_withdraw(
                character=character,
                character_max_items=expected_inventory_max_items,
                required_hp=min(character.max_hp, required_hp_median_max),
                lost_hps_per_fight=required_hp_map_list,
                fight_times=fight_times,
                is_event_monster=monster.is_event_monster,
                is_boss_monster=monster.is_boss_monster,
                task_id=task.task_id,
                context=context,
            )

        if food_map:
            # Only log for participants (not leader) - matching original behavior
            if not is_leader:
                food_counter = Counter(food_map)
                logger.info(
                    f'Plan to let {character.name} withdraw {food_counter.total()}x food, '
                    f"character's total inventory size: {expected_inventory_max_items}"
                )
            # Update bank inventory
            for item_code, item_qty in food_map.items():
                context.bank_items_maps[str(task.task_id)]['False'][item_code] -= item_qty

        return food_map

    def __filter_eligible_characters(
        self, character: CharacterSchemaExtension, participants: List[str], item: ItemSchemaExtension
    ) -> List[CharacterSchemaExtension]:
        result: List[CharacterSchemaExtension] = []
        candidates: Set[str] = {character.name, *participants}
        for c in self.service.get_all_character_details():
            if c.name in candidates and (not item.craft or c.skills[item.craft.skill].level >= item.craft.level):
                active_quest = self.character_table.get_quest(c.name)
                if not active_quest or not active_quest.is_locked():
                    result.append(c)
        return result

    def __find_fastest_combination(
        self,
        leader_name: str,
        eligible_characters: List[CharacterSchemaExtension],
        item: ItemSchemaExtension,
        item_quantity: int,
        bank_items_map: Dict[str, int],
    ) -> Any:

        combinations: List[CraftCombination] = []

        if not item.is_npc_item:
            counter = Counter({i.code: i.quantity for i in item.craft.items})
        else:
            origin = self.service.get_item_origin(item.code)
            offer = next(iter(origin.npcs.values()))
            if offer.currency != 'gold':
                counter = Counter({offer.currency: offer.price})
            else:
                counter = Counter(item.code)

        parts_per_item = counter.total()
        teleport_item_codes = self.service.get_teleport_item_codes()

        craftable_items_per_iteration_map: Dict[str, int] = {}
        inventory_capacity_map: Dict[str, int] = {}
        character_map: Dict[str, CharacterSchemaExtension] = {}
        for character in eligible_characters:
            inventory_capacity = character.inventory_capacity(teleport_item_codes)
            inventory_capacity_map[character.name] = inventory_capacity
            craftable_items_per_iteration_map[character.name] = inventory_capacity // parts_per_item
            character_map[character.name] = character

        for n in range(1, len(eligible_characters) + 1):
            for character_combination in itertools.combinations(eligible_characters, n):
                logger.debug(f'n={n}, character combination: {", ".join(c.name for c in character_combination)}')

                remaining_item_quantity = item_quantity

                busy_until_map: Dict[str, int] = {}
                for character in character_combination:
                    busy_until_map[character.name] = character.get_remaining_cooldown()

                craft_map: Dict[str, int] = defaultdict(int)
                total_seconds = 0

                while remaining_item_quantity > 0:
                    character_name = min(busy_until_map, key=lambda name: busy_until_map[name])
                    logger.debug(f'Next character is {character_name} who is busy for {busy_until_map[character_name]}s')

                    craftable_items_per_iteration = craftable_items_per_iteration_map[character_name]
                    crafting_quantity = min(remaining_item_quantity, craftable_items_per_iteration)
                    inventory_capacity = inventory_capacity_map[character_name]
                    s = self.service.calculate_craft_recipe_time({item.code: crafting_quantity}, inventory_capacity, bank_items_map)
                    remaining_item_quantity -= crafting_quantity
                    logger.debug(f'Craft {crafting_quantity}x {item.code} with {character_name} in {s}s, {remaining_item_quantity}x remaining.')
                    busy_until_map[character_name] += s
                    total_seconds += s
                    craft_map[character_name] += crafting_quantity

                if all(c.name in craft_map for c in character_combination):
                    finished_in = max(busy_until_map.values())
                    logger.debug(f'Add craft combination: {craft_map}, total_seconds: {total_seconds}, finished_in: {finished_in}')
                    combinations.append(CraftCombination(craft_map, total_seconds, finished_in, leader_name in craft_map))
                else:
                    logger.debug(f'Not all characters are needed in character combination: {", ".join(c.name for c in character_combination)}')

        fastest = min(combinations, key=lambda c: (-c.contains_leader, c.finished_in))
        return fastest
