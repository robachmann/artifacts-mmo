from collections import defaultdict
from enum import Enum
import itertools
from typing import Dict, Generator, List, Optional, Set, Tuple

from artifactsmmo import game_constants
from artifactsmmo.extensions import CharacterSchemaExtension, ItemSchemaExtension, MonsterSchemaExtension
from artifactsmmo.fights.character_fight_stats import CharacterFightStats
from artifactsmmo.fights.combat_calculator_approximation import CombatCalculatorApproximation
from artifactsmmo.game_constants import ELEMENTS
from artifactsmmo.log.logger import logger
from artifactsmmo.service.helpers import is_item_available
from artifactsmmo.service.service import Service
from artifactsmmo.singleton import SingletonMeta


class EquipmentScope(Enum):
    ALL = 'ALL'
    NONE = 'NONE'
    CRAFTABLE = 'CRAFTABLE'
    CRAFTABLE_AND_MONSTER_DROPS = 'CRAFTABLE_AND_MONSTER_DROPS'
    AVAILABLE = 'AVAILABLE'


class EquipmentAssembler(metaclass=SingletonMeta):
    def __init__(self, service: Service):
        self.service = service
        self.simulation_turns: List[Tuple[int, bool]] = []
        self.combat_calculator_approximation = CombatCalculatorApproximation()
        self.item_effects_map = {}

    def find_best_equipment_against_monster(
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
        include_runes: bool = True,
    ) -> Tuple[Dict[str, Dict[str, List[str]]], Dict[str, List[str]]]:
        if not bank_items_map:
            bank_items_map = self.service.get_bank_items_map(character_name=character.name)

        min_level = max((character.level - 16) // 5 * 5, 1)
        # For levels 1 to 20, the minimum level is 1.
        # From levels 21 to 25, the minimum level is 5.
        # From levels 26 to 30, the minimum level is 10.
        # From levels 31 to 35, the minimum level is 15.
        # From levels 36 to 40, the minimum level is 20.
        max_level = character.level

        exclude_monsters: List[MonsterSchemaExtension] = []
        if exclude_drops_from_monsters is not None:
            for monster_code in exclude_drops_from_monsters:
                exclude_monsters.append(self.service.get_monster(monster_code))

        exclude_items = exclude_items or []
        include_items = include_items or []
        global_quantity_map: Dict[str, int] = self.service.get_global_quantity_map(bank_items_map, all_characters_inventory_map)

        logger.info('Finding best equipment for character=%s against monster=%s', character.name, monster.code)
        all_weapons_candidates = self.get_items(
            exclude_monsters=exclude_monsters,
            item_type='weapon',
            exclude_subtype='tool',
            min_level=min_level,
            bank_items_map=bank_items_map,
            max_level=max_level,
            scope=equipment_scope,
            exclude_items_if_unavailable=exclude_items_if_unavailable,
            exclude_items=exclude_items,
            include_items=include_items,
            character=character,
            skill_map=skill_map,
        )

        all_weapon_codes = [weapon.code for weapon in all_weapons_candidates]

        weakest_weapons: Dict[str, Set[str]] = self.find_clearly_weakest_items(all_weapon_codes, global_quantity_map=global_quantity_map)
        if weakest_weapons:
            all_weapons = []
            for weapon in all_weapons_candidates:
                if weapon.code not in weakest_weapons:
                    all_weapons.append(weapon)
        else:
            all_weapons = all_weapons_candidates

        top_n = 9 if monster.type == 'boss' else 3
        top_weapon_keys = [w.code for w in sorted(all_weapons, key=lambda w: w.get_avg_attack(monster), reverse=True)[:top_n]]
        logger.info('top_weapon_keys=%s, all_weapon_codes=%s', top_weapon_keys, all_weapon_codes)

        permutation_map: Dict[str, Dict[str, List[str]]] = {}
        artifact_map: Dict[str, List[str]] = {}
        for weapon_code in top_weapon_keys:
            permutation_map[weapon_code] = defaultdict(list)

        gear_types = ['shield', 'helmet', 'body_armor', 'leg_armor', 'boots', 'amulet', 'ring1', 'artifact1']
        if include_runes:
            gear_types.append('rune')

        for gear_type in gear_types:
            gear_type_str = gear_type.rstrip('123')
            logger.debug('Fetching all suitable %s...', gear_type)
            all_items_of_type_res = self.get_items(
                min_level=1 if gear_type_str in ('rune', 'artifact') else min_level,
                exclude_monsters=exclude_monsters,
                max_level=max_level,
                bank_items_map=bank_items_map,
                item_type=gear_type_str,
                scope=equipment_scope,
                character=character,
                exclude_items_if_unavailable=exclude_items_if_unavailable,
                exclude_items=exclude_items,
                include_items=include_items,
                skill_map=skill_map,
            )

            artifact_list: Dict[str, List[str]] = defaultdict(list)
            for item in all_items_of_type_res:
                if item.improves_only_generic_stats() or item.improves_defense(monster):
                    for weapon_code in top_weapon_keys:
                        if gear_type_str == 'artifact':
                            artifact_list[weapon_code].append(item.code)
                        else:
                            permutation_map[weapon_code][gear_type_str].append(item.code)
                else:
                    for weapon_code in top_weapon_keys:
                        weapon = self.service.get_item(weapon_code)
                        if item.supports_weapon_focus(weapon):
                            if gear_type_str == 'artifact':
                                artifact_list[weapon_code].append(item.code)
                            else:
                                permutation_map[weapon_code][gear_type_str].append(item.code)

            for weapon_code, artifacts in artifact_list.items():
                artifact_map[weapon_code] = artifacts

        for weapon_code, gears in permutation_map.items():
            weapon = self.service.get_item(weapon_code)
            for gear_slot in gears:
                weakest_items = self.find_clearly_weakest_items(gears[gear_slot], weapon, monster, global_quantity_map=global_quantity_map)
                for weak_item_code in weakest_items:
                    gears[gear_slot].remove(weak_item_code)

        for weapon_code in permutation_map:
            permutation_map[weapon_code] = dict(permutation_map[weapon_code])  # Reduce number?

        return permutation_map, artifact_map

    def get_items(
        self,
        item_type: str,
        min_level: int,
        max_level: int,
        exclude_items_if_unavailable: List[str],
        exclude_items: List[str],
        include_items: List[str],
        character: CharacterSchemaExtension,
        bank_items_map: Dict[str, int],
        scope: EquipmentScope = EquipmentScope.ALL,
        exclude_subtype: str = None,
        exclude_monsters: List[MonsterSchemaExtension] = None,
        skill_map: Dict[str, int] = None,
    ) -> List[ItemSchemaExtension]:
        result: List[ItemSchemaExtension] = []

        exclude_items_if_unavailable = exclude_items_if_unavailable or []
        exclude_items = exclude_items or []
        include_items = include_items or []
        skill_map = skill_map or {}

        only_available = False
        only_craftable = False
        include_monster_drops = False

        match scope:
            case EquipmentScope.ALL:
                pass

            case EquipmentScope.CRAFTABLE:
                only_craftable = True
                if not skill_map:
                    for skill in game_constants.SKILLS:
                        skill_map[skill] = character.skills[skill].level

            case EquipmentScope.CRAFTABLE_AND_MONSTER_DROPS:
                only_craftable = True
                include_monster_drops = True
                if not skill_map:
                    for skill in game_constants.SKILLS:
                        skill_map[skill] = character.skills[skill].level

            case EquipmentScope.AVAILABLE:
                only_available = True

            case EquipmentScope.NONE:
                return result

        for item in self.service.get_items_by_type(item_type):
            if not (min_level <= item.level <= max_level):
                continue

            if exclude_subtype is not None and item.subtype == exclude_subtype:
                continue

            if self.item_contains_crafts(item, exclude_items):
                continue

            bank_count = bank_items_map.get(item.code, 0)
            currently_equipped = character.equipped_items.get(item.code, 0) > 0
            item_available = is_item_available(currently_equipped=currently_equipped, bank_count=bank_count, item_index=item.item_index())

            if not item_available and item.code not in include_items:
                if only_available:
                    continue

                if exclude_items_if_unavailable and self.item_contains_crafts(item, exclude_items_if_unavailable):
                    continue

                if only_craftable:
                    if not self.can_craft(skill_map, item):
                        continue
                    if not item.craft and not item.is_npc_item and not include_monster_drops:
                        continue

                if exclude_monsters and self.monster_drops_required_parts(exclude_monsters, item):
                    continue

            result.append(ItemSchemaExtension(item))

        # sort by Prospecting DESC, ATTACK DESC, HP DESC

        if item_type != 'weapon':
            result.sort(key=lambda r: (r.prospecting_value(), r.level), reverse=True)

        return result

    def find_clearly_weakest_items(
        self, item_codes: List[str], weapon=None, monster=None, global_quantity_map: Dict[str, int] = None
    ) -> Dict[str, Set[str]]:
        global_quantity_map = global_quantity_map or {}
        result: Dict[str, Set[str]] = defaultdict(set)
        items: Generator[ItemSchemaExtension] = (self.service.get_item(item_code) for item_code in item_codes if item_code)
        for item1, item2 in itertools.combinations(items, 2):
            item1_available = item1.code in global_quantity_map
            item2_available = item2.code in global_quantity_map
            if self.is_this_item_better(item1, item2, weapon, monster, item1_available, item2_available):
                result[item2.code].add(item1.code)
            elif self.is_this_item_better(item2, item1, weapon, monster, item2_available, item1_available):
                result[item1.code].add(item2.code)
        return result

    def find_clearly_weakest_item_effects(
        self,
        combinations: List[Tuple[str, ...]],
        weapon: ItemSchemaExtension = None,
        monster: MonsterSchemaExtension = None,
        global_quantity_map: Dict[str, int] = None,
    ) -> Dict[Tuple[str, ...], Set[Tuple[str, ...]]]:
        global_quantity_map = global_quantity_map or {}
        result: Dict[Tuple[str, ...], Set[Tuple[str, ...]]] = defaultdict(set)

        for combination1, combination2 in itertools.combinations(combinations, 2):
            combination1_effects = defaultdict(int)
            for item_code in combination1:
                for effect_name, effect_value in self.service.get_item(item_code).item_effects.items():
                    combination1_effects[effect_name] += effect_value

            combination2_effects = defaultdict(int)
            for item_code in combination2:
                for effect_name, effect_value in self.service.get_item(item_code).item_effects.items():
                    combination2_effects[effect_name] += effect_value

            combination1_available = all(item_code in global_quantity_map for item_code in combination1)
            combination2_available = all(item_code in global_quantity_map for item_code in combination2)
            if self.are_these_effects_better(
                combination1_effects,
                combination2_effects,
                weapon,
                monster,
                combination1_available,
                combination2_available,
            ):
                result[combination2].add(combination1)
            elif self.are_these_effects_better(
                combination2_effects,
                combination1_effects,
                weapon,
                monster,
                combination2_available,
                combination1_available,
            ):
                result[combination1].add(combination2)
        return result

    def is_this_item_better(
        self,
        this_item: ItemSchemaExtension,
        other_item: ItemSchemaExtension,
        weapon: ItemSchemaExtension = None,
        monster: MonsterSchemaExtension = None,
        this_item_available: bool = True,
        other_item_available: bool = True,
    ) -> bool:
        this_item_effects = this_item.get_relevant_effects(weapon, monster)
        other_item_effects = other_item.get_relevant_effects(weapon, monster)
        return self.are_these_effects_better(this_item_effects, other_item_effects, weapon, monster, this_item_available, other_item_available)

    def are_these_effects_better(
        self,
        this_item_effects: Dict[str, float],
        other_item_effects: Dict[str, float],
        weapon: ItemSchemaExtension = None,
        monster: MonsterSchemaExtension = None,
        this_item_available: bool = True,
        other_item_available: bool = True,
    ) -> bool:
        bonus_resistance_this = self.calculate_bonus_resistance(this_item_effects, monster)
        if bonus_resistance_this is not None:
            this_item_effects['bonus_resistance'] = bonus_resistance_this
            for element in ELEMENTS:
                this_item_effects.pop(f'res_{element}', None)

        bonus_resistance_other = self.calculate_bonus_resistance(other_item_effects, monster)
        if bonus_resistance_other is not None:
            other_item_effects['bonus_resistance'] = bonus_resistance_other
            for element in ELEMENTS:
                other_item_effects.pop(f'res_{element}', None)

        bonus_attack_this = self.calculate_bonus_attack(this_item_effects, weapon)
        if bonus_attack_this is not None:
            this_item_effects['bonus_attack'] = bonus_attack_this
            for element in ELEMENTS:
                this_item_effects.pop(f'dmg_{element}', None)

        bonus_attack_other = self.calculate_bonus_attack(other_item_effects, weapon)
        if bonus_attack_other is not None:
            other_item_effects['bonus_attack'] = bonus_attack_other
            for element in ELEMENTS:
                other_item_effects.pop(f'dmg_{element}', None)

        if this_item_effects == other_item_effects:
            return this_item_available or not other_item_available

        # check weapon stats incl. critical_strike
        if 'critical_strike' in this_item_effects and any(e.startswith('attack_') for e in this_item_effects.keys()):
            critical_strike_bonus_factor = 1 + this_item_effects['critical_strike'] * 0.005
            for key in this_item_effects.keys():
                if key.startswith('attack_'):
                    this_item_effects[key] = this_item_effects[key] * critical_strike_bonus_factor
            del this_item_effects['critical_strike']

        # check weapon stats incl. critical_strike
        if 'critical_strike' in other_item_effects and any(e.startswith('attack_') for e in other_item_effects.keys()):
            critical_strike_bonus_factor = 1 + other_item_effects['critical_strike'] * 0.005
            for key in other_item_effects.keys():
                if key.startswith('attack_'):
                    other_item_effects[key] = other_item_effects[key] * critical_strike_bonus_factor
            del other_item_effects['critical_strike']

        # remove same stats with same values
        all_effect_keys = set(this_item_effects.keys()) | set(other_item_effects.keys())
        for key in all_effect_keys:
            if key in this_item_effects and key in other_item_effects:
                if this_item_effects[key] == other_item_effects[key]:
                    this_item_effects.pop(key)
                    other_item_effects.pop(key)

        for effect, value in other_item_effects.items():
            if effect not in this_item_effects and value < 0:
                return True
            if effect not in this_item_effects or this_item_effects[effect] < value:
                return False

        for effect in other_item_effects:
            this_item_effects.pop(effect, None)

        if any(value < 0 for effect, value in this_item_effects.items()):
            return False

        return True

    @staticmethod
    def item_contains_crafts(item: ItemSchemaExtension, exclude_items: List[str]):
        if item:
            if item.code in exclude_items:
                return True
            craft_items = [craft.code for craft in item.craft.items] if item.craft else []
            for exclude_item in exclude_items:
                if exclude_item in craft_items:
                    return True
        return False

    def monster_drops_required_parts(self, monsters: List[MonsterSchemaExtension], item: ItemSchemaExtension):
        if monsters:
            craft_items = [craft.code for craft in item.craft.items] if item.craft else []
            craft_items.append(item.code)

            if not item.craft:
                origin = self.service.get_item_origin(item.code)
                if origin and origin.npcs:
                    for npc_offer in origin.npcs.values():
                        if npc_offer.currency != 'gold':
                            craft_items.append(npc_offer.currency)

            for monster in monsters:
                if any(drop.code in craft_items for drop in monster.drops):
                    return True
        return False

    @staticmethod
    def can_craft(skill_map: Dict[str, int], item: ItemSchemaExtension) -> bool:
        if item.craft:
            return skill_map.get(str(item.craft.skill), 1) >= item.craft.level
        else:
            return True

    def create_character_stats_from_equipment(self, level: int, item_codes: List[str]) -> CharacterFightStats:
        item_codes = set(item_codes)

        get_item = self.service.get_item

        effects_total = defaultdict(int)
        effects_total['initiative'] = 100
        for item_code in item_codes:
            if item_code:
                item: ItemSchemaExtension = get_item(item_code)
                item_type = item.type
                for effect_name, effect_value in item.item_effects.items():
                    match item_type:
                        case 'utility':
                            if effect_name.startswith('boost_'):
                                stat_effect = effect_name[6:]  # Equivalent to removeprefix('boost_')
                                effects_total[stat_effect] += effect_value
                        case 'ring':
                            effects_total[effect_name] += 2 * effect_value
                        case _:
                            effects_total[effect_name] += effect_value

        effects_total['max_hp'] = effects_total.pop('hp', 0) + 115 + 5 * level
        character_fight_stats = CharacterFightStats.from_stats_dict(effects_total)
        return character_fight_stats

    def create_item_effects_map(self, item_codes: Set[str]) -> Dict[str, Dict[str, int]]:  # rings will be counted twice!
        if not self.item_effects_map:
            self.item_effects_map = self.__init_item_effects_map()

        return {code: self.item_effects_map[code] for code in item_codes if code}

    def get_item_effects_map(self) -> Dict[str, Dict[str, int]]:  # rings will be counted twice!
        if not self.item_effects_map:
            self.item_effects_map = self.__init_item_effects_map()
        return self.item_effects_map

    def __init_item_effects_map(self) -> Dict[str, Dict[str, int]]:  # rings will be counted twice!
        items_effect_map: Dict[str, Dict[str, int]] = {}
        for item in self.service.get_all_items():
            item_effect_map: Dict[str, int] = {}
            for effect_name, effect_value in item.item_effects.items():
                if item.type == 'utility':
                    if effect_name.startswith('boost_'):
                        stat_effect = effect_name[6:]
                        item_effect_map[stat_effect] = effect_value
                elif item.type == 'ring':
                    item_effect_map[effect_name] = 2 * effect_value
                else:
                    item_effect_map[effect_name] = effect_value
            items_effect_map[item.code] = item_effect_map
        return items_effect_map

    @staticmethod
    def get_character_hp_at_level(character_level: int) -> int:
        return 115 + 5 * character_level

    @staticmethod
    def create_character_stats_from_items(  # submit rings only once!
        item_codes: Set[str],
        item_effects_map: Dict[str, Dict[str, int]],
        character_hp: int,
        character_level: int = None,
    ) -> CharacterFightStats:
        effects_total: Dict[str, int] = {'initiative': 100}
        for item_code in item_codes:
            for effect_name, effect_value in item_effects_map[item_code].items():
                if effect_name in effects_total:
                    effects_total[effect_name] += effect_value
                else:
                    effects_total[effect_name] = effect_value
        effects_total['max_hp'] = effects_total.pop('hp', 0) + character_hp
        character_fight_stats = CharacterFightStats.from_stats_dict(effects_total, character_level=character_level)
        return character_fight_stats

    @staticmethod
    def calculate_bonus_resistance(item_effects: Dict[str, float], monster: MonsterSchemaExtension) -> Optional[float]:
        if monster and any(e.startswith('res_') for e in item_effects):
            bonus_resistance = 0
            for res_effect, res_value in item_effects.items():
                if res_effect.startswith('res_'):
                    res_elem = res_effect.removeprefix('res_')
                    bonus_resistance += monster.attack_elem[res_elem] * res_value * 0.01
            return bonus_resistance

    @staticmethod
    def calculate_bonus_attack(item_effects: Dict[str, float], weapon: ItemSchemaExtension) -> Optional[float]:
        if weapon and any(e.startswith('dmg_') for e in item_effects):
            bonus_attack = 0
            for dmg_effect, dmg_value in item_effects.items():
                if dmg_effect.startswith('dmg_'):
                    dmg_elem = dmg_effect.replace('dmg_', 'attack_')
                    if dmg_elem in weapon.item_effects:
                        bonus_attack += weapon.item_effects[dmg_elem] * dmg_value * 0.01
            return bonus_attack
