from __future__ import annotations

from collections import Counter, defaultdict
from concurrent.futures import (
    as_completed,
    CancelledError,
    FIRST_COMPLETED,
    Future,
    ThreadPoolExecutor,
    wait,
)
from copy import copy, deepcopy
from datetime import timedelta
from functools import cache
import heapq
import itertools
from itertools import combinations, product
import math
from math import prod
import os
import time
from typing import Any, Dict, Iterator, List, Optional, Set, Tuple

import numpy as np

from artifactsmmo import game_constants
from artifactsmmo.extensions import (
    CharacterSchemaExtension,
    ItemSchemaExtension,
    MonsterSchemaExtension,
)
from artifactsmmo.fights.character_fight_stats import CharacterFightStats
from artifactsmmo.fights.combat_result import (
    CharacterResult,
    CombatResults,
    minimize_est_turns,
    minimize_forced_used_utilities,
    minimize_gather_time,
    minimize_gather_time_boss,
    minimize_gather_time_island,
    minimize_used_utilities,
)
from artifactsmmo.fights.equipment_assembler import EquipmentAssembler, EquipmentScope
from artifactsmmo.fights.fight_bundle import GenericFightBundle
from artifactsmmo.fights.generic_combat_calculator import GenericCombatCalculator
from artifactsmmo.game_constants import GEAR_POSITIONS, WIN_RATE_THRESHOLD
from artifactsmmo.log.logger import logger
from artifactsmmo.models import ItemType
from artifactsmmo.service.service import Service
from artifactsmmo.singleton import SingletonMeta


class FightSimulator(metaclass=SingletonMeta):
    def __init__(self, service: Service):
        self.service = service
        self.equipment_assembler = EquipmentAssembler(service)
        self.timeout_seconds = 60 if os.environ.get('AWS_LAMBDA_FUNCTION_NAME') else 600
        self.min_permutations = 1e5
        self.keep_percentile = 40
        self.generic_combat_calculator = GenericCombatCalculator()
        self.item_types = self.service.get_item_types()

    def find_best_fight_config(  # this is the main function to find the best gear
        self,
        character: CharacterSchemaExtension,
        monster: MonsterSchemaExtension,
        equipment_scope: EquipmentScope = EquipmentScope.AVAILABLE,
        utility_scope: EquipmentScope = None,
        exclude_items_if_unavailable: List[str] = None,
        exclude_items: List[str] = None,
        include_items: List[str] = None,
        exclude_drops_from_monsters: List[str] = None,
        winrate_threshold: int = 80,
        skill_map: Dict[str, int] = None,
        bank_items_map: Dict[str, int] = None,
        all_characters_inventory_map: Dict[str, int] = None,
        return_first_config: bool = False,
        raw_results: List[CombatResults] = None,
        force_utilities: bool = False,
        include_runes: bool = True,
        force_simulation: bool = False,
        sort_function=None,
        add_character_inventory: bool = False,
    ) -> CombatResults:
        utility_scope = utility_scope or equipment_scope

        if not bank_items_map:
            bank_items_map = Counter(self.service.get_bank_items_map(character_name=character.name))
        else:
            if not isinstance(bank_items_map, Counter):
                bank_items_map = Counter(bank_items_map)

        if add_character_inventory and character.inventory_map:
            bank_items_map.update(character.inventory_map)
            logger.info(f'Added {dict(character.inventory_map)} to available items.')

        combat_results = self.__find_best_equipment_against_monster(
            character=character,
            monster=monster,
            equipment_scope=equipment_scope,
            exclude_drops_from_monsters=exclude_drops_from_monsters,
            exclude_items_if_unavailable=exclude_items_if_unavailable,
            exclude_items=exclude_items,
            include_items=include_items,
            skill_map=skill_map,
            bank_items_map=bank_items_map,
            all_characters_inventory_map=all_characters_inventory_map,
            return_first_config=return_first_config,
            raw_results=raw_results,
            include_runes=include_runes,
            force_simulation=force_simulation,
            sort_function=sort_function,
        )

        if combat_results and ((WIN_RATE_THRESHOLD > combat_results.raw_result.win_rate > 1) or force_utilities):
            sim_result_utilities: CombatResults = self.__find_best_utilities_against_monster(
                character=character,
                monster=monster,
                utility_scope=utility_scope,
                equipment_map=list(combat_results.characters.values())[0].equipment,
                exclude_items_if_unavailable=exclude_items_if_unavailable,
                exclude_items=exclude_items,
                include_items=include_items,
                bank_items_map=bank_items_map,
                skill_map=skill_map,
                raw_results=raw_results,
                force_utilities=force_utilities,
                # fight_bundle=combat_results.fight_bundle,
                force_simulation=force_simulation,
            )
            if sim_result_utilities:
                sim_result_utilities.fight_bundle = combat_results.fight_bundle
                combat_results = sim_result_utilities
                if combat_results.raw_result.win_rate < winrate_threshold:
                    combat_results.character_wins = False

        return combat_results

    def find_best_multi_character_fight_config(
        self,
        monster: MonsterSchemaExtension,
        characters: List[CharacterSchemaExtension],
        bank_items_map: Dict[str, int] = None,
        equipment_scope: EquipmentScope = EquipmentScope.AVAILABLE,
        utility_scope: EquipmentScope = None,
        exclude_items_if_unavailable: List[str] = None,
        exclude_items: List[str] = None,
        include_items: List[str] = None,
        exclude_drops_from_monsters: List[str] = None,
        skill_map: Dict[str, int] = None,
        force_utilities: bool = False,
        raw_results: List[CombatResults] = None,
    ) -> CombatResults:
        skill_map = skill_map or self.service.get_skill_map(characters=characters)

        top_n_configs: Iterator[CombatResults] = self.find_top_n_fight_configs(
            monster=monster,
            characters=deepcopy(characters),
            bank_items_map=bank_items_map,
            equipment_scope=equipment_scope,
            utility_scope=utility_scope,
            exclude_items_if_unavailable=exclude_items_if_unavailable,
            exclude_items=exclude_items,
            include_items=include_items,
            exclude_drops_from_monsters=exclude_drops_from_monsters,
            skill_map=skill_map,
            include_runes=False,
            force_utilities=force_utilities,
            sort_function=minimize_est_turns,
        )
        fight_configs = list(top_n_configs)

        return self.find_best_boss_fight_config(
            configs=fight_configs,
            characters=characters,
            monster=monster,
            exclude_items=exclude_items,
            include_items=include_items,
            equipment_scope=equipment_scope,
            exclude_items_if_unavailable=exclude_items_if_unavailable,
            utility_scope=utility_scope,
            force_utilities=force_utilities,
            raw_results=raw_results,
            bank_items_map=bank_items_map,
        )

    def find_best_boss_fight_config(  # this is the main function to find the best gear
        self,
        configs: List[CombatResults],
        characters: List[CharacterSchemaExtension],
        monster: MonsterSchemaExtension,
        equipment_scope: EquipmentScope = EquipmentScope.AVAILABLE,
        utility_scope: EquipmentScope = None,
        exclude_items_if_unavailable: List[str] = None,
        exclude_items: List[str] = None,
        include_items: List[str] = None,
        # exclude_drops_from_monsters: List[str] = None,
        # winrate_threshold: int = 80,
        # skill_map: Dict[str, int] = None,
        bank_items_map: Dict[str, int] = None,
        all_characters_inventory_map: Dict[str, int] = None,
        # return_first_config: bool = False,
        raw_results: List[CombatResults] = None,
        force_utilities: bool = False,
        # include_runes: bool = True,
    ) -> CombatResults:
        utility_scope = utility_scope or equipment_scope

        if not bank_items_map:
            bank_items_map = self.service.get_bank_items_map()

        combat_results = self.__find_best_equipment_against_boss(
            configs=configs,
            characters=characters,
            monster=monster,
            equipment_scope=equipment_scope,
            exclude_items_if_unavailable=exclude_items_if_unavailable,
            exclude_items=exclude_items,
            include_items=include_items,
            bank_items_map=bank_items_map,
            raw_results=raw_results,
        )
        return combat_results

    def test_exact_config(
        self,
        monster: MonsterSchemaExtension,
        character: CharacterSchemaExtension = None,
        character_stats: CharacterFightStats = None,
        equipment_map: Dict[str, str] = None,
        hp: int = None,
        utilities_list: List[str] = None,
        print_log: bool = False,
        rounds: int = 0,
    ) -> Optional[CombatResults]:
        equipment_changes = 0
        utilities_list = utilities_list or []
        if not character_stats:
            if equipment_map:
                equipment_changes = self.__calculate_equipment_changes(character=character, equipment_map=equipment_map)
                utilities_list_from_equipment = [equipment_map[key] for key in ('utility1', 'utility2') if equipment_map.get(key)]
                character_stats: CharacterFightStats = self.equipment_assembler.create_character_stats_from_equipment(
                    character.level, [*list(equipment_map.values()), *utilities_list]
                )
                utilities_list.extend(utilities_list_from_equipment)
            else:
                utilities_list = list(character.utilities.keys())
                character_stats = self.equipment_assembler.create_character_stats_from_equipment(
                    character.level, list(character.equipment.values())
                )

        if hp is not None:
            character_stats.hp = hp

        utilities: Set[ItemSchemaExtension] = {self.service.get_item(item_code) for item_code in utilities_list if item_code}

        combat_results: CombatResults = self.generic_combat_calculator.calculate_win_rate(
            character_stats,
            monster,
            utilities,
            print_log=print_log,
            min_rounds=rounds,
        )
        if combat_results:
            combat_results.equipment_changes = equipment_changes

            if equipment_map:
                combat_results.characters['Character'].equipment = equipment_map
            elif character:
                if character.name in combat_results.characters:
                    combat_results.characters[character.name].equipment = character.equipment
                elif 'Character' in combat_results.characters:
                    combat_results.characters['Character'].equipment = character.equipment
                # else:
                #     logger.warning(
                #         f'Character name {character.name} is not present in combat_results. '
                #         f'Available keys: {list(combat_results.characters.keys())}'
                #     )
                #     if combat_results.characters:
                #         for character_name, character_result in combat_results.characters.items():
                #             character_result.equipment = character.equipment
                #             logger.info(f"Assigned equipment to {character_name}'s result")
                #             break
            combat_results.character_stats = character_stats

        if print_log:
            if equipment_map:
                self.print_fight_config(combat_results, Counter(equipment_map.values()), character_name=character.name)
            else:
                self.print_fight_config(combat_results, character_name=character.name)

        return combat_results

    def test_exact_boss_config(
        self,
        monster: MonsterSchemaExtension,
        characters: List[CharacterSchemaExtension] = None,
        character_stats: List[CharacterFightStats] = None,
        character_equipment_map: List[Dict[str, str]] = None,
        hp: int = None,
        utilities_map: Dict[str, Set[ItemSchemaExtension]] = None,
        print_log: bool = False,
        rounds: int = 0,
    ) -> Optional[CombatResults]:

        multi_fight_bundle_map: Dict[str, GenericFightBundle] = {}

        characters_map = {character.name: character for character in characters}
        boost_utilities_map: Dict[str, Set[str]] = defaultdict(set)

        unique_item_codes = set()
        permutation_map = {}
        for character, equipment in zip(characters, character_equipment_map):
            utility1_code = equipment.get('utility1_slot', '')
            utility2_code = equipment.get('utility2_slot', '')
            if utility1_code:
                utility = self.service.get_item(utility1_code)
                if utility and utility.is_boost_utility:
                    boost_utilities_map[character.name].add(utility1_code)
            if utility2_code:
                utility = self.service.get_item(utility2_code)
                if utility and utility.is_boost_utility:
                    boost_utilities_map[character.name].add(utility2_code)
            for remove_key in ['level', 'utility1_slot_quantity', 'utility2_slot_quantity']:
                if remove_key in equipment:
                    del equipment[remove_key]

            permutation_map[character.name] = equipment
            unique_item_codes.update(set(item_code for item_code in equipment.values() if item_code))

        item_effects_map: Dict[str, Dict[str, int]] = self.equipment_assembler.create_item_effects_map(unique_item_codes)

        for character_name, equipment_map in permutation_map.items():
            character = characters_map[character_name]
            character_hp = self.equipment_assembler.get_character_hp_at_level(character.level)
            character_fight_stats = self.equipment_assembler.create_character_stats_from_items(
                set(item_code for item_code in equipment_map.values() if item_code) | boost_utilities_map.get(character_name, set()),
                item_effects_map,
                character_hp,
                character.level,
            )
            multi_fight_bundle_map[character_name] = GenericFightBundle.from_fight_stats(
                character_fight_stats,
                monster,
                character_name=character.name,
            )

        combat_results = self.generic_combat_calculator.calculate_multi_character_win_rate(
            multi_fight_bundle_map=multi_fight_bundle_map,
            monster=monster,
            utilities_map=utilities_map,
            print_log=print_log,
            force_simulation=True,
            min_rounds=rounds,
        )

        if combat_results:
            for character_name, character_result in combat_results.characters.items():
                if not character_result.equipment:
                    for position in GEAR_POSITIONS:
                        if f'{position}_slot' in permutation_map[character_name]:
                            character_result.equipment[position] = permutation_map[character_name][f'{position}_slot']

        if print_log:
            self.print_fight_config(combat_results)

        return combat_results

    def __find_best_equipment_against_monster(
        self,
        character: CharacterSchemaExtension,
        monster: MonsterSchemaExtension,
        equipment_scope: EquipmentScope = EquipmentScope.AVAILABLE,
        exclude_drops_from_monsters: List[str] = None,
        exclude_items_if_unavailable: List[str] = None,
        exclude_items: List[str] = None,
        include_items: List[str] = None,
        skill_map: Dict[str, int] = None,
        bank_items_map: Dict[str, int] = None,
        all_characters_inventory_map: Dict[str, int] = None,
        return_first_config: bool = False,
        raw_results: List[CombatResults] = None,
        include_runes: bool = True,
        force_simulation: bool = False,
        sort_function=None,
    ) -> Optional[CombatResults]:
        # exclude_monsters: List[MonsterSchemaExtension] = []  # TODO: Investigate if ths is even used
        # if exclude_drops_from_monsters is not None:
        #    for monster_code in exclude_drops_from_monsters:
        #        exclude_monsters.append(self.service.get_monster(monster_code))

        if not bank_items_map:
            bank_items_map = self.service.get_bank_items_map(character_name=character.name)

        exclude_items = exclude_items or []
        include_items = include_items or []

        permutation_map, artifact_map = self.equipment_assembler.find_best_equipment_against_monster(
            character=character,
            monster=monster,
            equipment_scope=equipment_scope,
            exclude_drops_from_monsters=exclude_drops_from_monsters,
            exclude_items_if_unavailable=exclude_items_if_unavailable,
            exclude_items=exclude_items,
            include_items=include_items,
            skill_map=skill_map,
            bank_items_map=bank_items_map,
            all_characters_inventory_map=all_characters_inventory_map,
            include_runes=include_runes,
        )

        logger.info(f'permutation_map={dict(permutation_map)}, artifact_map={dict(artifact_map)}')

        def generate_permutations():
            if artifact_map:
                for weapon_code, gears in permutation_map.items():
                    artifacts = artifact_map.get(weapon_code, [])
                    for artifact_comb in self.create_artifact_combinations(artifacts, monster, weapon_code):
                        yield [[weapon_code], *gears.values(), *[[item] for item in artifact_comb]]
            else:
                for weapon_code, gears in permutation_map.items():
                    yield [[weapon_code], *gears.values()]

        # Collect unique item codes in single pass
        unique_item_codes = set()
        permutation_list = []
        for perm in generate_permutations():
            permutation_list.append(perm)
            for item_codes in perm:
                unique_item_codes.update(item_codes)

        total_permutation_number = sum(prod(len(p) for p in lst) for lst in permutation_list)

        logger.info(
            f'Finding best equipment for character={character.name} against monster={monster.code} in '
            f'permutations={total_permutation_number} across {os.cpu_count()} threads.'
        )

        if total_permutation_number > 1_000_000:
            modulo = 20
        elif total_permutation_number > 100_000:
            modulo = 10
        elif total_permutation_number > 5000:
            modulo = 4
        else:
            modulo = 0

        if not sort_function:
            if monster.code in ['sand_snake', 'sea_marauder', 'dusk_beetle', 'duskworm', 'sandwarden', 'desert_scorpion', 'sandwhisper_empress']:
                logger.info('Selecting sort_function=minimize_gather_time_island')
                sort_function = minimize_gather_time_island
            else:
                logger.info('Selecting sort_function=minimize_gather_time')
                sort_function = minimize_gather_time

        start = time.perf_counter()
        timeout_at: float = time.perf_counter() + self.timeout_seconds

        if return_first_config:
            result: Optional[CombatResults] = self.__stream_process_permutations(
                start=start,
                permutation_list=permutation_list,
                character=character,
                monster=monster,
                total_permutation_number=total_permutation_number,
                modulo=modulo,
                timeout_at=timeout_at,
                return_first_config=return_first_config,
                raw_results=raw_results,
                sort_function=sort_function,
                unique_item_codes=unique_item_codes,
            )
        else:
            result: Optional[CombatResults] = self.__process_permutations(
                permutation_list=permutation_list,
                character=character,
                monster=monster,
                total_permutation_number=total_permutation_number,
                modulo=modulo,
                timeout_at=timeout_at,
                return_first_config=return_first_config,
                raw_results=raw_results,
                sort_function=sort_function,
                unique_item_codes=unique_item_codes,
            )

        duration_seconds: float = time.perf_counter() - start  # seconds
        time_per_1_microseconds = duration_seconds / max(total_permutation_number, 1) * 1_000_000  # microseconds

        fields = dict(
            number_permutations=total_permutation_number,
            time_per_1=time_per_1_microseconds,
            monster=monster.code,
        )
        logger.info(
            f'⏱️ permutations={total_permutation_number}, time={timedelta(seconds=duration_seconds)}, cpu_count={os.cpu_count()}, '
            f'time_per_1={time_per_1_microseconds:.2f} μs, 👾 monster={monster.code} ({monster.level}), '
            f'character={character.name} ({character.level})',
            extra=fields,
        )

        if not result:
            logger.info(
                f'CombatResult (Gear) for character={character.name} ({character.level}), 👾 monster={monster.code} '
                f'({monster.level}): No combination found.'
            )
            return None
        else:
            logger.info(
                f'CombatResult (Gear) for character={character.name} ({character.level}), 👾 monster={monster.code} '
                f'({monster.level}), {result.to_string()}'
            )
            return result

    def __find_best_equipment_against_boss(
        self,
        configs: List[CombatResults],
        characters: List[CharacterSchemaExtension],
        monster: MonsterSchemaExtension,
        equipment_scope: EquipmentScope = EquipmentScope.AVAILABLE,
        exclude_items_if_unavailable: List[str] = None,
        exclude_items: List[str] = None,
        include_items: List[str] = None,
        exclude_drops_from_monsters: List[str] = None,
        bank_items_map: Dict[str, int] = None,
        raw_results: List[CombatResults] = None,
    ) -> Optional[CombatResults]:
        exclude_monsters: List[MonsterSchemaExtension] = []
        if exclude_drops_from_monsters is not None:
            for monster_code in exclude_drops_from_monsters:
                exclude_monsters.append(self.service.get_monster(monster_code))

        if not bank_items_map:
            bank_items_map = self.service.get_bank_items_map()

        exclude_items = exclude_items or []
        include_items = include_items or []

        best_config: Dict[str, CombatResults] = {}
        for idx, config in enumerate(configs):
            character_name = characters[idx].name
            best_config[character_name] = config

        characters_str = ', '.join(f'{c.name} ({c.level})' for c in characters)
        rune_map: Dict = {}
        equipped_runes = Counter()
        # bank_items_map_copy = Counter(bank_items_map.copy())
        for character in characters:
            runes = self.equipment_assembler.get_items(
                exclude_monsters=exclude_monsters,
                item_type='rune',
                min_level=1,
                bank_items_map=bank_items_map,
                max_level=character.level,
                scope=equipment_scope,
                exclude_items_if_unavailable=exclude_items_if_unavailable,
                exclude_items=exclude_items,
                include_items=include_items,
                character=character,
            )
            rune_map[character.name] = [rune.code for rune in runes]
            # if equipment_scope == EquipmentScope.AVAILABLE:
            #    candidates = Counter(rune_map[character.name])
            #    bank_items_map_copy -= candidates
            if character.rune_slot:
                equipped_runes[character.rune_slot] += 1

        utilities_map = defaultdict(set)
        config_combinations: List[Dict[str, Dict[str, str]]] = []
        for combo in itertools.product(*rune_map.values()):
            boss_config = {}
            skip_config = False
            if equipment_scope == EquipmentScope.AVAILABLE:
                used_runes = Counter(combo)
                for rune_code, rune_qty in used_runes.items():
                    if bank_items_map.get(rune_code, 0) + equipped_runes.get(rune_code, 0) < rune_qty:
                        skip_config = True
                        break
            if not skip_config:
                for character_name, rune_code in zip(rune_map.keys(), combo):
                    equipment = copy(best_config[character_name].characters['Character'].equipment)
                    equipment['rune'] = rune_code
                    boss_config[character_name] = equipment
                    for utility_code in best_config[character_name].characters['Character'].used_utilities.keys():
                        utilities_map[character_name].add(self.service.get_item(utility_code))
                config_combinations.append(boss_config)

        total_permutation_number = len(config_combinations)

        start = time.perf_counter()
        time.perf_counter() + self.timeout_seconds
        permutation_number = 0

        result: Optional[CombatResults] = self.__process_boss_permutations(
            permutation_map_list=config_combinations,
            characters=characters,
            monster=monster,
            permutation_number=permutation_number,
            raw_results=raw_results,
            utilities_map=utilities_map,
            #    print_log=permutation_number == 0,
        )

        duration_seconds: float = time.perf_counter() - start  # seconds
        time_per_1_microseconds = duration_seconds / max(total_permutation_number, 1) * 1_000_000  # microseconds

        fields = dict(
            number_permutations=total_permutation_number,
            time_per_1=time_per_1_microseconds,
            monster=monster.code,
        )
        logger.info(
            f'⏱️ permutations={total_permutation_number}, time={timedelta(seconds=duration_seconds)}, cpu_count={os.cpu_count()}, '
            f'time_per_1={time_per_1_microseconds:.2f} μs, 👾 monster={monster.code} ({monster.level}), '
            f'characters={characters_str})',
            extra=fields,
        )

        if not result:
            logger.info(
                f'CombatResult (Gear) for characters={characters_str}), 👾 monster={monster.code} ({monster.level}): No combination found.'
            )
            return None
        else:
            logger.info(
                f'CombatResult (Gear) for characters={characters_str}, 👾 monster={monster.code} ({monster.level}), {result.to_string()}'
            )
            return result

    def __find_best_utilities_against_monster(
        self,
        character: CharacterSchemaExtension,
        monster: MonsterSchemaExtension,
        equipment_map: Dict[str, str],
        utility_scope: EquipmentScope = EquipmentScope.AVAILABLE,
        exclude_items_if_unavailable: List[str] = None,
        exclude_items: List[str] = None,
        include_items: List[str] = None,
        bank_items_map: Dict[str, int] = None,
        skill_map: Dict[str, int] = None,
        raw_results: List[CombatResults] = None,
        print_log: bool = False,
        force_utilities: bool = False,
        # fight_bundle=None,
        force_simulation: bool = False,
    ) -> Optional[CombatResults]:
        if not bank_items_map:
            bank_items_map = self.service.get_bank_items_map(character_name=character.name)

        exclude_items = exclude_items or []

        all_utility_candidates: List[ItemSchemaExtension] = self.equipment_assembler.get_items(
            item_type='utility',
            min_level=1,
            bank_items_map=bank_items_map,
            max_level=character.level,
            scope=utility_scope,
            exclude_items_if_unavailable=exclude_items_if_unavailable,
            exclude_items=exclude_items,
            skill_map=skill_map,
            include_items=include_items,
            character=character,
        )

        weapon_code = equipment_map.get('weapon')
        weapon = self.service.get_item(weapon_code) if weapon_code else None
        all_utilities = self.__filter_utilities(weapon, monster, all_utility_candidates)
        logger.info(f'Checking with utilities={[u.code for u in all_utilities]}')
        equipment_changes = self.__calculate_equipment_changes(character=character, equipment_map=equipment_map)

        sort_function = minimize_forced_used_utilities if force_utilities else minimize_used_utilities

        result: Optional[CombatResults] = None
        for utility1, utility2 in combinations(all_utilities, 2):
            gear_keys: List[str] = list(equipment_map.values())
            utilities = {utility1, utility2}
            gear_keys.extend(i.code for i in utilities)

            character_stats = self.equipment_assembler.create_character_stats_from_equipment(character.level, gear_keys)

            combat_results: CombatResults = self.generic_combat_calculator.calculate_win_rate(
                character_stats,
                monster,
                utilities,
                print_log=print_log,
                force_simulation=force_simulation,
            )

            combat_results.equipment = equipment_map
            combat_results.equipment_changes = equipment_changes
            if 'Character' in combat_results.characters:
                combat_results.characters['Character'].equipment = equipment_map
                combat_results.characters['Character'].equipment_changes = equipment_changes

            if not combat_results.fight_bundle:
                character_fight_stats = self.equipment_assembler.create_character_stats_from_equipment(character.level, gear_keys)
                combat_results.fight_bundle = GenericFightBundle.from_fight_stats(character_fight_stats, monster)

            if raw_results:
                raw_results.append(combat_results)

            if not result or sort_function(combat_results, result.character_wins) < sort_function(result, combat_results.character_wins):
                result = combat_results

                used_utilities = Counter()
                for r in combat_results.characters.values():
                    used_utilities.update(r.used_utilities)
                logger.info(
                    f'Found better combination: {sort_function(combat_results, result.character_wins)}, '
                    f'new win_rate={combat_results.raw_result.win_rate:.2f}%, used_utilities={used_utilities}'
                )

        if not result:
            logger.info(
                f'CombatResult (Con.) for character={character.name} ({character.level}), 👾 monster={monster.code} '
                f'({monster.level}): No combination found.'
            )
            return None
        else:
            logger.info(
                f'CombatResult (Con.) for character={character.name} ({character.level}), 👾 monster={monster.code} '
                f'({monster.level}), {result.to_string()}'
            )
            return result

    def find_top_n_fight_configs(
        self,
        monster: MonsterSchemaExtension,
        character: CharacterSchemaExtension = None,
        characters: List[CharacterSchemaExtension] = None,
        bank_items_map: Dict[str, int] = None,
        equipment_scope: EquipmentScope = EquipmentScope.AVAILABLE,
        utility_scope: EquipmentScope = None,
        exclude_items_if_unavailable: List[str] = None,
        exclude_items: List[str] = None,
        include_items: List[str] = None,
        exclude_drops_from_monsters: List[str] = None,
        top_n: int = 5,
        winrate_threshold: int = 80,
        skill_map: Dict[str, int] = None,
        return_first_config: bool = False,
        include_runes: bool = True,
        force_utilities: bool = False,
        sort_function=None,
    ) -> Iterator[CombatResults]:
        if not character and not characters:
            characters = self.service.get_all_character_details()[:top_n]

        if not characters:
            characters = []
        elif characters:
            top_n = len(characters)

        if character:
            for n in range(top_n):
                characters.append(character)

        skill_map = skill_map or self.service.get_skill_map(characters)
        if bank_items_map:
            bank_items_map = bank_items_map.copy()
        else:
            bank_items_map = self.service.get_global_quantity_map()
            for c in characters:
                c.inventory_map = Counter()
                c.equipped_items = Counter()
        all_characters_inventory_map = {'tasks_coin': 1}

        config: Optional[CombatResults] = None
        for n in range(top_n):
            should_find_new_config = True
            if config and n > 0 and characters[n].level <= characters[n - 1].level:
                character_level = characters[n].level

                equipment_map = Counter()
                for c in config.characters.values():
                    for equipment_code in c.equipment.values():
                        equipment_map[equipment_code] += 1
                    for consumable_code, consumable_qty in c.used_utilities.items():
                        equipment_map[consumable_code] += consumable_qty

                can_wear_all = not any(character_level < self.service.get_item(item_code).level for item_code in equipment_map.keys())

                if can_wear_all and (
                    equipment_scope == EquipmentScope.ALL
                    or all(bank_items_map.get(item_code, 0) >= item_quantity for item_code, item_quantity in equipment_map.items())
                ):
                    should_find_new_config = False
                    logger.info(
                        f'{characters[n].name} can equip the same equipment as {characters[n - 1].name} '
                        f'and all pieces are available for another character.'
                    )

            if should_find_new_config:
                config: CombatResults = self.find_best_fight_config(
                    character=characters[n],
                    monster=monster,
                    equipment_scope=equipment_scope,
                    utility_scope=utility_scope,
                    skill_map=skill_map,
                    exclude_items_if_unavailable=exclude_items_if_unavailable,
                    exclude_items=exclude_items,
                    include_items=include_items,
                    exclude_drops_from_monsters=exclude_drops_from_monsters,
                    winrate_threshold=winrate_threshold,
                    bank_items_map=bank_items_map,
                    all_characters_inventory_map=all_characters_inventory_map,
                    return_first_config=return_first_config,
                    include_runes=include_runes,
                    force_utilities=force_utilities,
                    force_simulation=True,
                    sort_function=sort_function,
                )

            if config:
                for c in config.characters.values():
                    for equipment_code in c.equipment.values():
                        if equipment_code in bank_items_map:
                            bank_items_map[equipment_code] -= 1
                            if bank_items_map[equipment_code] == 0:
                                del bank_items_map[equipment_code]
                    for consumable_code, consumable_qty in c.used_utilities.items():
                        if consumable_code in bank_items_map:
                            bank_items_map[consumable_code] -= consumable_qty
                            if bank_items_map[consumable_code] == 0:
                                del bank_items_map[consumable_code]
            yield config

    def print_best_fight_config(
        self,
        character: CharacterSchemaExtension,
        monster: MonsterSchemaExtension,
        equipment_scope: EquipmentScope = EquipmentScope.AVAILABLE,
        utility_scope: EquipmentScope = None,
        exclude_items_if_unavailable: List[str] = None,
        exclude_items: List[str] = None,
        include_items: List[str] = None,
        exclude_drops_from_monsters: List[str] = None,
        skill_map=None,
        winrate_threshold: int = 80,
        # equipment: Dict[str, str] = None,
        raw_results: List[CombatResults] = None,
        force_utilities: bool = False,
        sort_function=None,
    ) -> Optional[CombatResults]:
        bank_items_map = self.service.get_bank_items_map()

        result: Optional[CombatResults] = self.find_best_fight_config(
            character=character,
            monster=monster,
            exclude_drops_from_monsters=exclude_drops_from_monsters,
            exclude_items_if_unavailable=exclude_items_if_unavailable,
            exclude_items=exclude_items,
            include_items=include_items,
            equipment_scope=equipment_scope,
            utility_scope=utility_scope,
            winrate_threshold=winrate_threshold,
            bank_items_map=bank_items_map,
            skill_map=skill_map,
            raw_results=raw_results,
            force_utilities=force_utilities,
            sort_function=sort_function,
        )

        character_equipment = defaultdict(int)
        for gear_position in game_constants.GEAR_POSITIONS:
            slot_item = character.equipment.get(gear_position)
            if slot_item:
                character_equipment[slot_item] += 1

        if result and result.character_wins:
            logger.info(f'Best fight-config against monster={monster.code}, A: {monster.offensive_elements_emojis()}')
            self.print_fight_config(result, character_equipment, character_name=character.name)
        else:
            logger.error(f'Cannot find equipment for character={character.name} ({character.level}) to beat {monster.code} ({monster.level})')
        return result

    @staticmethod
    def __equipment_list_to_map(equipment_list: Tuple[Any, ...], item_types: Dict[str, str]) -> Dict[str, str]:
        equipment_map: Dict[str, str] = {}
        if equipment_list:
            for item_code in equipment_list:
                item_type = item_types[item_code]
                if item_type == 'artifact':
                    for artifact_slot in ('artifact1', 'artifact2', 'artifact3'):
                        if artifact_slot not in equipment_map:
                            equipment_map[artifact_slot] = item_code
                            break
                elif item_type == 'ring':
                    equipment_map['ring1'] = equipment_map['ring2'] = item_code
                else:
                    equipment_map[item_type] = item_code
        return equipment_map

    @staticmethod
    def __calculate_equipment_changes(character: CharacterSchemaExtension, equipment_map: Dict[str, str]):
        result = 0
        character_equipment = character.equipment
        artifact_slots = ('artifact1', 'artifact2', 'artifact3')
        equipped_artifacts = {character_equipment[slot] for slot in artifact_slots if character_equipment[slot]}
        num_equipped_artifacts = len(equipped_artifacts)
        for gear, item_code in equipment_map.items():
            if gear.startswith('artifact'):
                if item_code in equipped_artifacts:
                    continue
                elif num_equipped_artifacts < 3:
                    result += 1
                else:
                    result += 2
            else:
                currently_equipped = character_equipment.get(gear)
                if currently_equipped == item_code:
                    continue
                elif currently_equipped == '':
                    result += 1
                else:
                    result += 2
        return result

    def print_fight_config(self, res: CombatResults, character_equipment: Dict[str, int] = None, character_name: str = None):
        # character_equipment = character_equipment if character_equipment else defaultdict(int)
        all_character_details: List[CharacterSchemaExtension] = self.__get_cached_character_details()
        bank_items_map = self.__get_cached_bank_items_map()
        all_characters_inventory_map = self.__get_cached_characters_inventory_map()
        character_equipment_map = self.__get_cached_characters_equipment_map()

        total_equipment = defaultdict(int)
        unavailable_gear: Counter = Counter()
        increment_global_max: Counter = Counter()
        global_count: Counter = Counter()
        for c_name, c in res.characters.items():
            if len(res.characters) == 1:
                c_name = character_name
            logger.info(f'Combat Configuration for {c_name}')
            equipment_map = c.equipment

            for idx, utility in enumerate(c.used_utilities, 1):
                equipment_map[f'utility{idx}'] = utility

            for slot, item_code in equipment_map.items():
                if item_code:
                    item = self.service.get_item(item_code)
                    current_character = character_equipment_map.get(c_name, {}).get(item.code, 0)
                    other_characters = all_characters_inventory_map.get(item.code, 0) - current_character
                    bank_count = bank_items_map.get(item.code, 0)

                    log_icon = ''
                    log_parts = [f'{slot}:', item.code, '|']

                    locations: Counter = Counter()
                    for character in all_character_details:
                        equip_count = sum(1 for i in character.equipment.values() if i == item.code)
                        key = character.name if character.name != character_name else f'{character.name} (✅)'
                        on_character_count = equip_count + character.inventory_map.get(item.code, 0)
                        locations[key] += on_character_count
                        if item.type == ItemType.RING:
                            global_count[item.code] += math.ceil(on_character_count / 2)
                        else:
                            global_count[item.code] += on_character_count
                    locations['🏦'] = bank_items_map.get(item.code, 0)
                    global_count[item.code] += bank_items_map.get(item.code, 0)

                    log_parts.append(', '.join(f'{k}: {v}' for k, v in locations.items() if v > 0))
                    if sum(1 for k, v in locations.items() if v > 0) > 1:
                        log_parts.append(f'| total: {locations.total()}')

                    if current_character:
                        log_icon = '✅'
                    elif other_characters and not bank_count:
                        log_icon = '*️⃣'
                        increment_global_max[item_code] += 1
                    elif bank_count:
                        log_icon = '✳️'

                    from_previous_equipments = total_equipment.get(item.code, 0)
                    account_qty = current_character + other_characters + bank_count - from_previous_equipments

                    log_type = 'info'
                    if account_qty < 1:
                        increment_global_max[item_code] += 2 if item.type == ItemType.RING else 1
                        unavailable_gear[item_code] += 2 if item.type == ItemType.RING else 1
                        craft = item.craft
                        if craft:
                            can_craft = [char.name for char in all_character_details if getattr(char, f'{craft.skill}_level', 1) >= craft.level]
                            if can_craft:
                                log_type = 'warning'
                                log_icon = '⚠️'
                                log_parts.append(f'needs to be crafted by {", ".join(can_craft)}')
                            else:
                                log_type = 'error'
                                log_icon = '⭕️'
                                log_parts.append(f'cannot be crafted (yet), requires {craft.skill} at {craft.level}.')
                        else:
                            origin = self.service.get_item_origin(item.code)
                            if origin:
                                if origin.npcs:
                                    log_type = 'warning'
                                    log_icon = '⚠️'

                                    for npc_code, offer in origin.npcs.items():
                                        if offer.currency != 'gold':
                                            log_parts.append(
                                                f'needs to be traded from {npc_code} for {offer.price}x {offer.currency} '
                                                f'(available: {bank_items_map.get(offer.currency, 0)})'
                                            )
                                        else:
                                            log_parts.append(f'needs to be traded from {npc_code} for {offer.price}x {offer.currency}')
                                        break

                                elif origin.monsters:
                                    log_type = 'warning'
                                    log_icon = '⚠️'
                                    log_parts.append(f'needs to be dropped from {", ".join(origin.monsters.keys())}')
                            else:
                                log_type = 'error'
                                log_parts.append('cannot be crafted.')

                    log_str = ' '.join([log_icon, *log_parts])
                    match log_type:
                        case 'info':
                            logger.info('   ' + log_str)
                        case 'warning':
                            logger.warning(log_str)
                        case 'error':
                            logger.error('  ' + log_str)
                    total_equipment[item.code] += 1

        if unavailable_gear:
            logger.info(f'Resolve recipes of unavailable gear: /resolve {" ".join(unavailable_gear.elements())}')

        exact_map = Counter()
        for c in res.characters.values():
            exact_map.update(c.equipment.values())
            exact_map.update(c.used_utilities)

        logger.info(f'Create craft task: Task.ensure_equipment(exact_map={dict(exact_map)})')

        if increment_global_max:
            logger.info(f'Resolve recipes of additional gear: /resolve {" ".join(increment_global_max.elements())}')
            for c in increment_global_max:
                increment_global_max[c] += global_count.get(c, 0)
            logger.info(f'Create craft task: Task.ensure_equipment(exact_map={dict(increment_global_max)})')

    @staticmethod
    def __log_permutation(total_permutation_number: int, permutation_number: int, modulo: int, start: float):
        if modulo > 0:
            logging_number = total_permutation_number // modulo
            if permutation_number % logging_number == 0:
                elapsed_seconds: float = time.perf_counter() - start  # seconds
                total_seconds_required = elapsed_seconds / permutation_number * total_permutation_number
                total_seconds_remaining = int(total_seconds_required - elapsed_seconds)
                duration_remaining: timedelta = timedelta(seconds=total_seconds_remaining)
                tpn_str = str(total_permutation_number)
                pn_str = str(permutation_number).zfill(len(tpn_str))
                logger.info(
                    f'Processing permutation {pn_str}/{tpn_str}: '
                    f'{permutation_number / total_permutation_number * 100:.2f}% -{duration_remaining}'
                )

    @cache
    def __get_cached_character_details(self) -> List[CharacterSchemaExtension]:
        return self.service.get_all_character_details()

    @cache
    def __get_cached_bank_items_map(self):
        return self.service.get_bank_items_map(ignore_reservations=True)

    @cache
    def __get_cached_characters_inventory_map(self):
        characters = self.__get_cached_character_details()
        return self.service.get_all_characters_inventory_map(characters)

    @cache
    def __get_cached_characters_equipment_map(self) -> Dict[str, Dict[str, int]]:
        characters: List[CharacterSchemaExtension] = self.__get_cached_character_details()
        return {character.name: character.equipped_items for character in characters}

    def create_artifact_combinations(self, artifacts: List[str], monster: MonsterSchemaExtension, weapon_code: str):
        strong_combinations = []
        if artifacts:
            weapon = self.service.get_item(weapon_code)
            weakest_items: Dict[str, Set[str]] = self.equipment_assembler.find_clearly_weakest_items(artifacts, weapon, monster)
            result_combinations = []
            for combination in combinations(artifacts, min(3, len(artifacts))):
                should_append = True
                for weaker_code, stronger_codes in weakest_items.items():
                    if weaker_code in combination and not any(stronger_code in combination for stronger_code in stronger_codes):
                        should_append = False
                        break
                if should_append:
                    result_combinations.append(combination)

            weakest_combinations = self.equipment_assembler.find_clearly_weakest_item_effects(result_combinations, weapon, monster)
            if weakest_combinations:
                for combination in result_combinations:
                    if combination not in weakest_combinations:
                        strong_combinations.append(combination)
            else:
                strong_combinations = result_combinations

        return strong_combinations

    def __precompute_inputs(
        self,
        permutation_list: List[List[List[str]]],
        character: CharacterSchemaExtension,
        unique_item_codes: Set[str] = None,
    ):
        unique_item_codes: Set[str] = unique_item_codes or {
            item_code for list_of_lists in permutation_list for item_codes in list_of_lists for item_code in item_codes
        }
        item_effects_map: Dict[str, Dict[str, int]] = self.equipment_assembler.create_item_effects_map(unique_item_codes)
        character_hp: int = self.equipment_assembler.get_character_hp_at_level(character.level)
        return item_effects_map, character_hp

    def __compute_ratio(
        self,
        permutation_values_set: Set[str],
        permutation_values: Tuple[str, ...],
        item_effects_map: Dict[str, Any],
        character_hp: int,
        monster: MonsterSchemaExtension,
    ) -> Tuple[float, Tuple[str, ...], GenericFightBundle, CharacterFightStats]:
        """Compute the ratio and fight bundle for a single permutation."""
        character_fight_stats = self.equipment_assembler.create_character_stats_from_items(
            permutation_values_set, item_effects_map, character_hp
        )
        partial_fight_bundle = GenericFightBundle.partial_from_fight_stats(character_fight_stats, monster)
        return partial_fight_bundle.est_turns_ratio, permutation_values, partial_fight_bundle, character_fight_stats

    def __find_top_candidates(
        self,
        permutation_list: List[List[List[Any]]],
        item_effects_map: Dict[str, Any],
        character_hp: int,
        monster: MonsterSchemaExtension,
        max_keep: int,
        max_workers: int,
    ) -> Tuple[List[Tuple[float, int, Dict[str, Any]]], float, float]:
        """Step 1: Find top candidates by streaming permutations in parallel."""
        top_heap: List[Tuple[float, int, Dict[str, Any]]] = []
        min_ratio, max_ratio = float('inf'), 0.0
        counter = itertools.count()
        max_in_flight: int = max_workers * 8
        active_futures: Dict[Future, None] = {}

        def process_result(completed_future: Future):
            """Process a completed future and update the heap."""
            nonlocal min_ratio, max_ratio

            try:
                ratio, permutation_values_ret, partial_fight_bundle, character_fight_stats = completed_future.result()
            except Exception as e:
                logger.error(f'Error in ratio computation: {e}')
                return

            cnt: int = next(counter)
            min_ratio = min(min_ratio, ratio)
            max_ratio = max(max_ratio, ratio)

            entry: Tuple[float, int, Dict[str, Any]] = (
                -ratio,
                cnt,
                {
                    'permutation_values': permutation_values_ret,
                    'fight_bundle': partial_fight_bundle,
                    'character_fight_stats': character_fight_stats,
                },
            )

            # Keep a bounded heap of best ratios
            if len(top_heap) < max_keep:
                heapq.heappush(top_heap, entry)
            elif -entry[0] < -top_heap[0][0]:
                heapq.heappushpop(top_heap, entry)

        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            for list_of_lists in permutation_list:
                for permutation_values in product(*list_of_lists):
                    permutation_values_set: Set[str] = set(permutation_values)

                    future: Future = executor.submit(
                        self.__compute_ratio,
                        permutation_values_set,
                        permutation_values,
                        item_effects_map,
                        character_hp,
                        monster,
                    )
                    active_futures[future] = None

                    # Limit the number of active futures
                    if len(active_futures) >= max_in_flight:
                        done, _ = wait(active_futures.keys(), return_when=FIRST_COMPLETED)
                        for f in done:
                            active_futures.pop(f, None)
                            process_result(f)

            # Drain remaining futures
            for f in as_completed(active_futures):
                process_result(f)

        return top_heap, min_ratio, max_ratio

    def __process_top_candidates(
        self,
        top_candidates,
        character,
        monster,
        item_types,
        timeout_at,
        return_first_config,
        raw_results,
        half_permutation_number,
        modulo,
        sort_function,
        max_workers=4,
        print_log=False,
    ):
        """Step 3: Run full calculations on top candidates."""
        result: Optional[CombatResults] = None
        active_futures = {}
        batch_results: List[CombatResults] = []
        max_in_flight = max_workers * 2
        start = time.perf_counter()
        permutation_number = 0

        def flush_batch_if_needed():
            if raw_results is not None and len(batch_results) >= 500:
                raw_results.extend(batch_results)
                batch_results.clear()

        def handle_finished_future(future):
            nonlocal permutation_number, result
            permutation_number, result = self.__handle_future_result(
                future,
                active_futures,
                result,
                permutation_number,
                half_permutation_number,
                modulo,
                start,
                sort_function,
                batch_results,
            )

        def should_return_early():
            if not result:
                return False
            if result.character_wins and return_first_config:
                return True
            if result.character_wins and time.perf_counter() > timeout_at:
                return True
            return False

        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            # Main loop: submit work
            for est_ratio, _, permutation in top_candidates:
                pv = permutation['permutation_values']
                fight_bundle = permutation['fight_bundle']
                cstats = permutation['character_fight_stats']

                fight_bundle.complete_initialization(cstats, monster)

                equipment_map = self.__equipment_list_to_map(pv, item_types)
                equipment_changes = self.__calculate_equipment_changes(
                    character=character,
                    equipment_map=equipment_map,
                )

                future = executor.submit(
                    self.__process_permutation,
                    character_level=character.level,
                    fight_bundle=fight_bundle,
                    permutation_values=pv,
                    equipment_map=equipment_map,
                    equipment_changes=equipment_changes,
                    monster=monster,
                    print_log=print_log,
                    provided_character_fight_stats=cstats,
                )
                active_futures[future] = (pv, equipment_map, equipment_changes)

                # Limit in-flight work
                if len(active_futures) >= max_in_flight:
                    done, _ = wait(active_futures.keys(), return_when=FIRST_COMPLETED)
                    for f in done:
                        handle_finished_future(f)
                        flush_batch_if_needed()

                        if should_return_early():
                            logger.info('Returning early due to win or timeout.')
                            executor.shutdown(wait=False, cancel_futures=True)
                            return result

            # Drain remaining
            for f in as_completed(active_futures):
                handle_finished_future(f)

            # Final batch push
            if raw_results is not None and batch_results:
                raw_results.extend(batch_results)

        return result

    @staticmethod
    def __filter_top_candidates_smart(top_heap, keep_percentile: int):
        """Step 2: Filter top candidates using percentile instead of average ratio."""
        if not top_heap:
            return []

        if len(top_heap) < 1000:
            top_candidates = [(-r, fight_id, data) for r, fight_id, data in top_heap]
            top_candidates.sort()  # Tuples sort by first element by default
            logger.info(f'Smart-filtered {len(top_candidates)} candidates (all kept, dataset < 1000), lowest_ratio={top_candidates[0][0]}')
            return top_candidates

        ratios = np.fromiter((-r for r, _, _ in top_heap), dtype=np.float64, count=len(top_heap))
        threshold = np.percentile(ratios, keep_percentile)

        top_candidates = [(-r, fight_id, data) for r, fight_id, data in top_heap if -r <= threshold]
        top_candidates.sort()

        logger.info(
            f'Smart-filtered {len(top_candidates)} candidates (percentile={keep_percentile}%, threshold={threshold:.3f}), '
            f'lowest_ratio={top_candidates[0][0]}'
        )
        return top_candidates

    def __process_permutations(
        self,
        permutation_list: List[List[List[str]]],
        character,
        monster,
        total_permutation_number,
        modulo,
        timeout_at,
        print_log=False,
        return_first_config=False,
        raw_results=None,
        sort_function=None,
        unique_item_codes=None,
    ):
        """Main orchestration method."""
        logger.info(f'Processing {total_permutation_number} permutations')
        max_workers = min(os.cpu_count() or 1, 4)
        max_keep = 75_000

        # Step 1: Precompute inputs
        item_effects_map, character_hp = self.__precompute_inputs(permutation_list, character, unique_item_codes)
        logger.info('Finished pre-computing item_effects_map.')

        # Step 2: First executor - find top candidates quickly
        top_heap, min_ratio, max_ratio = self.__find_top_candidates(
            permutation_list,
            item_effects_map,
            character_hp,
            monster,
            max_keep=max_keep,
            max_workers=max_workers,
        )
        logger.info('Finished finding top candidates.')

        # Step 3: Smarter filtering of top candidates
        top_candidates = self.__filter_top_candidates_smart(top_heap, self.keep_percentile)
        half_permutation_number = len(top_candidates)
        logger.info('Finished filtering top candidates.')

        # Step 4: Second executor - expensive full simulations
        result = self.__process_top_candidates(
            top_candidates=top_candidates,
            character=character,
            monster=monster,
            item_types=self.item_types,
            timeout_at=timeout_at,
            return_first_config=return_first_config,
            raw_results=raw_results,
            half_permutation_number=half_permutation_number,
            modulo=modulo,
            max_workers=max_workers,
            sort_function=sort_function,
        )

        return result

    def __stream_process_permutations(
        self,
        permutation_list,
        character,
        monster,
        total_permutation_number,
        modulo,
        start,
        timeout_at: float,
        print_log: bool = False,
        return_first_config: bool = False,
        raw_results: List[CombatResults] = None,
        sort_function=None,
        unique_item_codes=None,
    ) -> Optional[CombatResults]:
        result: Optional[CombatResults] = None

        max_workers = min(os.cpu_count() or 1, 4)
        max_in_flight = max_workers * 2
        active_futures = {}
        total_permutation_number_tenth = total_permutation_number // 10 if total_permutation_number > 100_000 else total_permutation_number

        item_effects_map, character_hp = self.__precompute_inputs(permutation_list, character, unique_item_codes)
        permutation_number = 0
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            for list_of_lists in permutation_list:
                for permutation_values in product(*list_of_lists):
                    equipment_map = self.__equipment_list_to_map(permutation_values, self.item_types)
                    equipment_changes = self.__calculate_equipment_changes(character=character, equipment_map=equipment_map)
                    character_fight_stats = self.equipment_assembler.create_character_stats_from_items(
                        set(permutation_values), item_effects_map, character_hp, character.level
                    )
                    fight_bundle = GenericFightBundle.from_fight_stats(character_fight_stats, monster)

                    while len(active_futures) >= max_in_flight:
                        done, _ = wait(active_futures.keys(), return_when=FIRST_COMPLETED)

                        if result:
                            if return_first_config and result.character_wins:
                                logger.info('Found a first config to win fight, returning early.')
                                executor.shutdown(wait=False, cancel_futures=True)
                                return result

                            if result.raw_result.win_rate == 100 and permutation_number > total_permutation_number_tenth:
                                logger.info('100% win-rate achieved after 10% of all permutations, cancelling early.')
                                executor.shutdown(wait=False, cancel_futures=True)
                                return result

                            if time.perf_counter() > timeout_at and result.character_wins:
                                logger.info('Timeout reached and intermediary result available, cancelling early.')
                                executor.shutdown(wait=False, cancel_futures=True)
                                return result

                        for future in done:
                            permutation_number, result = self.__handle_future_result(
                                future=future,
                                active_futures=active_futures,
                                best_result=result,
                                permutation_number=permutation_number,
                                total_permutation_number=total_permutation_number,
                                modulo=modulo,
                                start=start,
                                sort_function=sort_function,
                                raw_results_sink=raw_results,
                            )

                    future = executor.submit(
                        self.__process_permutation,
                        character_level=character.level,
                        fight_bundle=fight_bundle,
                        permutation_values=list(permutation_values),
                        equipment_map=equipment_map,
                        equipment_changes=equipment_changes,
                        monster=monster,
                        print_log=print_log,
                        provided_character_fight_stats=character_fight_stats,
                    )
                    active_futures[future] = (permutation_values, equipment_map, equipment_changes)

            for future in as_completed(active_futures):
                permutation_number, result = self.__handle_future_result(
                    future=future,
                    active_futures=active_futures,
                    best_result=result,
                    permutation_number=permutation_number,
                    total_permutation_number=total_permutation_number,
                    modulo=modulo,
                    start=start,
                    sort_function=sort_function,
                    raw_results_sink=raw_results,
                )

        return result

    def __process_boss_permutations(
        self,
        permutation_map_list: List[Dict[str, Dict[str, str]]],
        characters: List[CharacterSchemaExtension],
        monster,
        permutation_number,
        print_log=False,
        raw_results: List[CombatResults] = None,
        utilities_map: Dict[str, Set[ItemSchemaExtension]] = None,
    ):

        permutation_list = []
        for permutation_map in permutation_map_list:
            for _, equipment_map in permutation_map.items():
                permutation_list.append(equipment_map.values())

        boost_utilities_map: Dict[str, Set[str]] = defaultdict(set)
        for character_name, utility_set in utilities_map.items():
            for utility in utility_set:
                if utility.is_boost_utility:
                    boost_utilities_map[character_name].add(utility.code)

        item_effects_map = self.equipment_assembler.get_item_effects_map()

        logger.info('Finished pre-computing item_effects_map.')

        characters_map: Dict[str, CharacterSchemaExtension] = {c.name: c for c in characters}

        best_result: Optional[CombatResults] = None
        for permutation_map in permutation_map_list:
            permutation_number += 1
            multi_fight_bundle_map: Dict[str, GenericFightBundle] = {}

            for character_name, equipment_map in permutation_map.items():
                character = characters_map[character_name]
                character_hp = self.equipment_assembler.get_character_hp_at_level(character.level)
                character_fight_stats = self.equipment_assembler.create_character_stats_from_items(
                    set(equipment_map.values()) | boost_utilities_map.get(character_name, set()),
                    item_effects_map,
                    character_hp,
                    character.level,
                )
                multi_fight_bundle_map[character_name] = GenericFightBundle.from_fight_stats(
                    character_fight_stats,
                    monster,
                    character_name=character.name,
                )

            new_result = self.generic_combat_calculator.calculate_multi_character_win_rate(
                multi_fight_bundle_map=multi_fight_bundle_map,
                monster=monster,
                utilities_map=utilities_map,  # map with character_name as key? yes
                print_log=print_log,
                force_simulation=True,
            )

            if raw_results is not None and new_result:
                raw_results.append(new_result)

            if not best_result or new_result and minimize_gather_time_boss(new_result) < minimize_gather_time_boss(best_result):
                if best_result:
                    logger.info(
                        f'Found better boss result: {minimize_gather_time_boss(new_result)}, win_rate: {new_result.raw_result.win_rate:.2f}%'
                    )
                best_result = new_result
                if new_result.characters.keys():
                    for c_name, p_equip in permutation_map.items():
                        new_result.characters[c_name].equipment = p_equip
                        new_result.characters[c_name].level = multi_fight_bundle_map[c_name].character.level
                new_result.equipment_changes = 0

        return best_result

    def __handle_future_result(
        self,
        future,
        active_futures: Dict[Future, Any],
        best_result: Optional[CombatResults],
        permutation_number: int,
        total_permutation_number: int,
        modulo: int,
        start: float,
        sort_function,
        raw_results_sink: Optional[List[CombatResults]] = None,
    ) -> Tuple[int, Optional[CombatResults]]:
        meta: Optional[Tuple[Any, Any, Any]] = active_futures.pop(future, None)
        if not meta:
            return permutation_number, best_result

        try:
            new_result: CombatResults = future.result()
            permutation_values, equipment_map, equipment_changes = meta
            new_result.equipment = equipment_map
            new_result.equipment_changes = equipment_changes
            if not new_result.characters:
                new_result.characters['Character'] = CharacterResult(
                    max_hp=0,
                    required_hp_map={},
                    remaining_hp_map={},
                    used_utilities={},
                    required_hp_median=0,
                    equipment=equipment_map,
                    equipment_changes=equipment_changes,
                    level=None,
                )
            elif new_result.characters['Character']:
                new_result.characters['Character'].equipment = equipment_map
                new_result.characters['Character'].equipment_changes = equipment_changes

        except CancelledError:
            return permutation_number, best_result
        except Exception as exc:
            logger.exception('Permutation task failed: %s', exc)
            return permutation_number, best_result

        # Optional batching: caller can pass a temporary list to be flushed later
        if raw_results_sink is not None:
            raw_results_sink.append(new_result)

        # Progress
        permutation_number += 1
        self.__log_permutation(total_permutation_number, permutation_number, modulo, start)

        if not best_result:
            return permutation_number, new_result

        if not new_result:
            return permutation_number, best_result

        if sort_function(new_result) < sort_function(best_result):
            # if new_result.character_wins:
            #     rechecked_result = self.generic_combat_calculator.calculate_win_rate(
            #         character_fight_stats=character_fight_stats,
            #         monster=monster,
            #         fight_bundle=fight_bundle,
            #         print_log=False,
            #         min_rounds=1000,
            #     )

            differences = [
                f"'{k}': {best_result.characters['Character'].equipment[k]} -> {equipment_map.get(k, '')}"
                for k in best_result.characters['Character'].equipment
                if best_result.characters['Character'].equipment[k] != equipment_map.get(k, '')
            ]
            tpn_str = str(total_permutation_number)
            pn_str = str(permutation_number).zfill(len(tpn_str))
            logger.info(
                f'[{pn_str}/{tpn_str}] Found better combination: {sort_function(new_result)}, '
                f'new win_rate={new_result.raw_result.win_rate:.2f}% (n={new_result.sample_size}), differences: {", ".join(differences)}'
            )
            return permutation_number, new_result

        return permutation_number, best_result

    def __process_permutation(
        self,
        character_level: int,
        fight_bundle: GenericFightBundle,
        permutation_values: List[str],
        equipment_map: Dict[str, str],
        equipment_changes: int,
        monster: MonsterSchemaExtension,
        print_log: bool,
        provided_character_fight_stats: CharacterFightStats = None,
    ) -> Optional[CombatResults]:
        character_fight_stats: CharacterFightStats = (
            provided_character_fight_stats
            or self.equipment_assembler.create_character_stats_from_equipment(
                character_level,
                permutation_values,
            )
        )

        result = self.generic_combat_calculator.calculate_win_rate(
            character_fight_stats=character_fight_stats,
            monster=monster,
            fight_bundle=fight_bundle,
            print_log=print_log,
        )
        if result:
            result.equipment = equipment_map
            result.equipment_changes = equipment_changes
            result.character_stats = character_fight_stats
        return result

    @staticmethod
    def __filter_utilities(weapon: ItemSchemaExtension, monster: MonsterSchemaExtension, all_utility_candidates: List[ItemSchemaExtension]):
        all_utilities = []
        for utility in all_utility_candidates:
            add_utility = True
            if utility.is_boost_utility:
                def_elements = set()
                dmg_elements = set()
                for effect_name in utility.item_effects:
                    if effect_name.startswith('boost_res_'):
                        def_elements.add(effect_name.removeprefix('boost_res_'))
                    elif effect_name.startswith('boost_dmg_'):
                        dmg_elements.add(effect_name.removeprefix('boost_dmg_'))
                if def_elements or dmg_elements:
                    add_utility = False
                    if monster.offensive_elements & def_elements:
                        add_utility = True
                    elif weapon and (weapon.offensive_elements & dmg_elements):
                        add_utility = True

            elif 'antipoison' in utility.item_effects and 'poison' not in monster.effect:
                add_utility = False

            if add_utility:
                all_utilities.append(utility)

        return all_utilities
