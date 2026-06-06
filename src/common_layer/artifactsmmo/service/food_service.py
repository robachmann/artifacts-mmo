from collections import Counter
from dataclasses import dataclass
import itertools
from math import ceil
import random
from typing import Dict, List

from artifactsmmo.extensions import CharacterSchemaExtension, ItemSchemaExtension
from artifactsmmo.game_constants import INVENTORY_UTILIZATION_FACTOR_BOSS, INVENTORY_UTILIZATION_FACTOR_DEFAULT
from artifactsmmo.log.logger import logger
from artifactsmmo.service.execution_context import ExecutionContext
from artifactsmmo.service.service import Service


@dataclass
class SuitableConsumable:
    quantity: int
    item: ItemSchemaExtension


@dataclass
class SuitableConsumableDuration:
    consumables: Dict[str, int]
    rest_seconds: int
    consume_seconds: int
    total_seconds: int


class FoodService:
    def __init__(self, service: Service):
        self.service = service

    def get_best_food_to_gather(
        self,
        remaining_hp_counter: Counter[int],
        required_hp: int,
        max_hp: int,
        character_level: int,
        is_event_monster: bool = False,
    ) -> Dict[str, int]:
        result = Counter()

        inventory_map = Counter()
        for consumable in self.service.get_processed_food_by_level(character_level):
            inventory_map[consumable.code] = ceil(max_hp / consumable.heal_value())

        for remaining_hp, count in remaining_hp_counter.items():
            res = self.get_best_food(
                current_hp=remaining_hp,
                required_hp=required_hp,
                max_hp=max_hp,
                inventory_map=inventory_map,
                character_level=character_level,
                is_event_monster=is_event_monster,
            )
            for consumable_code, consumable_qty in res.items():
                result[consumable_code] += count * consumable_qty
        return dict(result)

    def get_best_food_to_withdraw(
        self,
        character: CharacterSchemaExtension,
        required_hp: int,
        lost_hps_per_fight: List[int] = None,
        fight_times: int = 1,
        is_event_monster: bool = False,
        is_boss_monster: bool = False,
        task_id: str = None,
        context: ExecutionContext = None,
        character_max_items: int = None,
    ) -> Dict[str, int]:
        lost_hps_per_fight = lost_hps_per_fight or [0]

        inventory_map = Counter()
        bank_items_map = self.service.get_bank_items_map(task_id=task_id, context=context, character_name=character.name)
        for consumable in self.service.get_processed_food_by_level(character.level):
            available_quantity = bank_items_map.get(consumable.code, 0)
            if available_quantity:
                inventory_map[consumable.code] = available_quantity

        if not inventory_map:
            return {}

        current_hp = character.hp
        result = Counter()
        for _ in range(fight_times):
            if current_hp < required_hp:
                res = self.get_best_food(
                    current_hp=current_hp,
                    required_hp=required_hp,
                    max_hp=character.max_hp,
                    inventory_map=inventory_map,
                    character_level=character.level,
                    is_event_monster=is_event_monster,
                )
                if res:
                    for consumable_code, consumable_qty in res.items():
                        result[consumable_code] += consumable_qty
                        inventory_map[consumable_code] -= consumable_qty
                        current_hp += min(character.max_hp, consumable_qty * self.service.get_item(consumable_code).heal_value())
                else:
                    current_hp = character.max_hp

            if len(lost_hps_per_fight) > 1:
                current_hp -= random.choice(lost_hps_per_fight)
            else:
                current_hp -= lost_hps_per_fight[0]

        if result:
            teleport_item_codes = self.service.get_teleport_item_codes()
            inventory_max_items = character.inventory_capacity(teleport_item_codes, character_max_items=character_max_items)

            if is_boss_monster:
                utilization_factor = INVENTORY_UTILIZATION_FACTOR_BOSS
            elif max(lost_hps_per_fight) < 10:
                utilization_factor = 0.5 * INVENTORY_UTILIZATION_FACTOR_DEFAULT
            else:
                utilization_factor = INVENTORY_UTILIZATION_FACTOR_DEFAULT

            inventory_space = int(utilization_factor * inventory_max_items)
            remaining_space = max(0, inventory_max_items - character.inventory_map.total() - 5)
            max_withdraw_quantity = min(inventory_space, remaining_space)
            total_consumable_quantity = sum(result.values())

            factor = max_withdraw_quantity / total_consumable_quantity

            if factor < 1:
                for code in result:
                    result[code] = int(factor * result[code])

        return {k: v for k, v in result.items() if v > 0}

    def get_best_food_to_consume(
        self,
        character: CharacterSchemaExtension,
        required_hp: int = None,
        is_event_monster: bool = False,
        inventory_map: Counter[str] = None,
    ) -> Dict[str, int]:
        return self.get_best_food(
            current_hp=character.hp,
            required_hp=required_hp if required_hp else character.max_hp,
            max_hp=character.max_hp,
            inventory_map=inventory_map if inventory_map else character.inventory_map,
            character_level=character.level,
            is_event_monster=is_event_monster,
        )

    def get_best_food(
        self,
        current_hp: int,
        required_hp: int,
        max_hp: int,
        inventory_map: Dict[str, int],
        character_level: int,
        is_event_monster: bool = False,
    ) -> Dict[str, int]:
        if current_hp > required_hp:
            return {}

        rest_time_threshold = 10 if is_event_monster else 20

        all_consumables: List[ItemSchemaExtension] = self.service.get_processed_food_by_level(character_level)
        available_consumables: List[ItemSchemaExtension] = []
        available_consumables_map = {}
        heal_map = {}
        for consumable in all_consumables:
            if consumable.code in inventory_map:
                available_consumables.append(consumable)
                available_consumables_map[consumable.code] = inventory_map[consumable.code]
                heal_map[consumable.code] = consumable.heal_value()

        res = self.possible_heal_combos_best(available_consumables_map, heal_map, max_hp)
        results = []

        if res:
            for total_heal in sorted(res.keys()):
                combination, diff_items, total_items = res[total_heal]
                rest_time = 0
                overheal_value = 0

                if current_hp + total_heal <= required_hp:
                    missing_hp = max_hp - total_heal - current_hp
                    missing_hp_percent = ceil(missing_hp / max_hp * 100)
                    rest_time = max(3, missing_hp_percent) if missing_hp_percent > 0 else 0
                    overheal_value = 0
                elif required_hp <= current_hp + total_heal < max_hp:
                    rest_time = 0
                    overheal_value = 0
                elif current_hp + total_heal >= required_hp and current_hp + total_heal >= max_hp:
                    rest_time = 0
                    overheal_value = current_hp + total_heal - max_hp
                else:
                    logger.error(
                        f'Unexpected status: current_hp={current_hp}, total_heal={total_heal}, '
                        f'current_hp + total_heal = {current_hp + total_heal}, '
                        f'required_hp={required_hp}, max_hp={max_hp}'
                    )

                results.append(
                    dict(
                        rest_time_sort=rest_time if rest_time > rest_time_threshold else 0,
                        overheal_value=overheal_value,
                        rest_time=rest_time,
                        use_time=diff_items * 3,
                        total_items=total_items,
                        total_heal=total_heal,
                        combination=combination,
                    )
                )

            results.sort(key=lambda x: (x['rest_time_sort'], x['overheal_value'], x['rest_time'], x['total_items'], x['use_time']))

            if results:
                return {k: v for k, v in results[0]['combination'].items() if v > 0}

        return {}

    @staticmethod
    def all_food_combinations_with_heal_sorted(foods: Dict[str, int], heal_values: Dict[str, int], max_hp: int):
        items = list(foods.items())
        max_heal = max(heal_values.values())
        results = []
        ranges = [range(0, qty + 1) for _, qty in items]
        for counts in itertools.product(*ranges):
            if any(c > 0 for c in counts):  # skip empty combo
                combo = {name: c for (name, _), c in zip(items, counts) if c > 0}
                total_heal = sum(c * heal_values[name] for name, c in combo.items())
                if total_heal <= max_hp + max_heal:
                    results.append((combo, total_heal))

        # Sort by total_heal, then by number of items
        results.sort(key=lambda x: (x[1], sum(x[0].values())))
        return results

    @staticmethod
    def possible_heal_combos_best(foods: Dict[str, int], heal_values: Dict[str, int], max_hp: int):
        if not foods:
            return {}

        item_names = list(foods.keys())
        max_heal = max(heal_values.values(), default=0) + max_hp
        # heal_sum -> (combo, diff_items_count, total_items_count)
        dp: Dict[int, tuple] = {0: ({name: 0 for name in item_names}, 0, 0)}

        for name in item_names:
            qty = foods[name]
            heal_amt = heal_values[name]

            new_dp = dict(dp)
            for heal_sum, (combo, diff_items, total_items) in dp.items():
                for count in range(1, qty + 1):
                    new_sum = heal_sum + heal_amt * count
                    if new_sum > max_heal:
                        break

                    new_combo = combo.copy()
                    prev_count = new_combo[name]
                    new_combo[name] += count

                    new_diff_items = diff_items
                    if prev_count == 0:
                        new_diff_items += 1
                    new_total_items = total_items + count

                    if new_sum not in new_dp:
                        new_dp[new_sum] = (new_combo, new_diff_items, new_total_items)
                    else:
                        _, existing_diff, existing_total = new_dp[new_sum]
                        if (new_diff_items < existing_diff) or (new_diff_items == existing_diff and new_total_items < existing_total):
                            new_dp[new_sum] = (new_combo, new_diff_items, new_total_items)

            dp = new_dp

        return dp
