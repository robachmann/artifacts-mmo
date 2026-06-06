from collections import Counter
from typing import Dict, List, Set

from artifactsmmo import game_constants
from artifactsmmo.extensions import MonsterSchemaExtension
from artifactsmmo.game_constants import ELEMENTS, SKILLS
from artifactsmmo.models import ItemSchema, ItemType
from artifactsmmo.service import helpers


class ItemSchemaExtension(ItemSchema):
    def __init__(self, base_obj: ItemSchema, is_task_reward: bool = False, is_npc_item: bool = False):
        super().__init__()
        self.__dict__.update(base_obj.__dict__)

        self.item_effects: Dict[str, int] = Counter()
        self.defensive_elements: Set[str] = set()
        self.offensive_elements: Set[str] = set()
        self.strongest_offensive_elements: Set[str] = set()

        if self.effects:
            for effect in self.effects:
                if effect.code != 'dmg':
                    self.item_effects[effect.code] += effect.value
                else:
                    for dmg_elem in ('dmg_air', 'dmg_fire', 'dmg_earth', 'dmg_water'):
                        self.item_effects[dmg_elem] += effect.value

            if any(f'dmg_{element}' in self.item_effects for element in ELEMENTS):
                max_dmg = max(self.item_effects[f'dmg_{element}'] for element in ELEMENTS)
                if max_dmg > 0:
                    for element in ELEMENTS:
                        dmg_elem = self.item_effects[f'dmg_{element}']
                        if dmg_elem > 0:
                            self.offensive_elements.add(element)
                            if dmg_elem == max_dmg:
                                self.strongest_offensive_elements.add(element)
            elif any(f'attack_{element}' in self.item_effects for element in ELEMENTS):
                max_attack = max(self.item_effects[f'attack_{element}'] for element in ELEMENTS)
                if max_attack > 0:
                    for element in ELEMENTS:
                        attack_elem = self.item_effects[f'attack_{element}']
                        if attack_elem > 0:
                            self.offensive_elements.add(element)
                            if attack_elem == max_attack:
                                self.strongest_offensive_elements.add(element)

            if any(f'res_{element}' in self.item_effects for element in ELEMENTS):
                max_res = max(self.item_effects[f'res_{element}'] for element in ELEMENTS)
                if max_res > 0:
                    for element in ELEMENTS:
                        res_elem = self.item_effects[f'res_{element}']
                        if res_elem > 0:
                            self.defensive_elements.add(element)
                            if res_elem == max_res:
                                self.defensive_elements.add(element)

            self.is_boost_utility = self.item_effects and all(effect_name.startswith('boost_') for effect_name in self.item_effects)
            self.item_effects = dict(self.item_effects)

        self.is_recyclable = self.craft and self.craft.skill in game_constants.RECYCLING_SKILLS
        self.is_task_reward = is_task_reward
        self.is_teleport_item = bool(self.item_effects and 'teleport' in self.item_effects)
        self.is_npc_item = is_npc_item
        self.is_processed_food = False
        self.buy_price = None
        self.sell_price = None
        self.sell_to = None

    def __hash__(self):
        return hash(self.code)

    def is_gear(self) -> bool:
        return bool(self.type and self.type != ItemType.RESOURCE)

    def offensive_elements_emojis(self, filter_elements: Set[str]):
        return helpers.format_elements_emojis(self.offensive_elements.intersection(filter_elements))

    def defensive_elements_emojis(self, filter_elements: Set[str]):
        return helpers.format_elements_emojis(self.defensive_elements.intersection(filter_elements))

    def element_emojis(self, filter_offensive_elements: Set[str], filter_defensive_elements: Set[str]) -> str:
        list_str: List[str] = []

        if offensive_elements := self.offensive_elements_emojis(filter_offensive_elements):
            list_str.append(f'A: {offensive_elements}')

        defensive_elements = self.defensive_elements_emojis(filter_defensive_elements)
        if self.item_effects.get('hp', 0) > 0:
            defensive_elements += '💕'
        if defensive_elements:
            list_str.append(f'D: {defensive_elements}')

        return ' | '.join(list_str)

    def supports_weapon(self, weapon: 'ItemSchemaExtension' = None) -> bool:
        if weapon:
            return not weapon.strongest_offensive_elements.isdisjoint(self.offensive_elements)
        else:
            return False

    def supports_weapon_focus(self, weapon: 'ItemSchemaExtension' = None) -> bool:
        if weapon:
            return not weapon.strongest_offensive_elements.isdisjoint(self.strongest_offensive_elements)
        else:
            return False

    def improves_only_generic_stats(self) -> bool:
        if any(effect.code.endswith(ELEMENTS) for effect in self.effects) or all(effect.code in SKILLS for effect in self.effects):
            return False
        return True

    def improves_defense(self, monster: MonsterSchemaExtension) -> bool:
        return not monster.offensive_elements.isdisjoint(self.defensive_elements)

    def get_relevant_effects(self, weapon: 'ItemSchemaExtension' = None, monster: MonsterSchemaExtension = None) -> Dict[str, float]:
        effects: Dict[str, int] = {}
        for effect, value in self.item_effects.items():
            if not monster or effect.removeprefix('res_') in monster.offensive_elements:
                effects[effect] = value
            elif not weapon or effect.removeprefix('dmg_') in weapon.offensive_elements:
                effects[effect] = value
            elif effect in ['hp', 'haste', 'critical_strike', 'prospecting', 'lifesteal', 'burn', 'healing']:
                effects[effect] = value
        return effects

    def get_strength(self, weapon: 'ItemSchemaExtension', monster: MonsterSchemaExtension, character_max_hp: int = 100) -> Dict[str, float]:
        monster_attack_modifier = 0
        character_attack_modifier = 0

        weapon_avg_dmg = weapon.get_avg_attack(monster)

        additional_hp = 0
        prospecting = 0
        # turn_factor = 1
        # hp_factor = 1
        for effect_name, effect_value in self.get_relevant_effects(weapon, monster).items():
            if effect_name.startswith('dmg_'):
                element = effect_name[len('dmg_') :]
                character_attack_modifier += weapon.item_effects.get(f'attack_{element}', 0) * (effect_value * 0.01)

            elif effect_name.startswith('res_'):
                element = effect_name[len('res_') :]
                monster_attack_modifier -= monster.attack_elem.get(element, 0) * (effect_value * 0.01)

            elif effect_name == 'critical_strike':
                additional_dmg = effect_value * 0.005 * weapon_avg_dmg
                character_attack_modifier += additional_dmg

            elif effect_name == 'hp':
                additional_hp += effect_value * 0.0009

            elif effect_name == 'prospecting':
                prospecting += effect_value * 0.009

        character_turns_no_buff = monster.hp / weapon_avg_dmg
        character_turns_buff = monster.hp / (weapon_avg_dmg + character_attack_modifier)
        character_turn_modifier = character_turns_buff - character_turns_no_buff

        monster_turns_no_buff = character_max_hp / monster.base_attack_sum
        monster_turns_buff = character_max_hp / (monster.base_attack_sum + monster_attack_modifier)
        monster_turn_modifier = monster_turns_buff - monster_turns_no_buff

        total_turns_modifier = character_turn_modifier - monster_turn_modifier - additional_hp - prospecting

        return dict(
            #    character_attack_modifier=character_attack_modifier,
            #    character_turn_modifier=character_turn_modifier,
            #    monster_attack_modifier=monster_attack_modifier,
            #    monster_turn_modifier=monster_turn_modifier,
            total_turns_modifier=total_turns_modifier,
        )

    def inventory_space_value(self):
        return self.item_effects.get('inventory_space', 0)

    def is_confining_gear(self):
        return self.inventory_space_value() < 0

    def prospecting_value(self):
        return self.item_effects.get('prospecting', 0)

    def wisdom_value(self):
        return self.item_effects.get('wisdom', 0)

    def heal_value(self):
        return self.item_effects.get('heal', 0)

    def item_index(self) -> int:
        if self.type == ItemType.RING:
            return 2
        elif self.type == ItemType.UTILITY:
            if self.item_effects.get('restore', 0) > 0:
                return 25
            else:
                return 5
        else:
            return 1

    def to_flat_dict(self) -> dict:
        item_dict = self.to_dict()
        for key, value in self.item_effects.items():
            item_dict[f'effect.{key}'] = value
        item_dict['defensive_elements'] = self.defensive_elements
        item_dict['offensive_elements'] = self.offensive_elements
        item_dict['strongest_offensive_elements'] = self.strongest_offensive_elements
        return item_dict

    def get_avg_attack(self, monster: MonsterSchemaExtension = None):
        total_attack = 0
        crit_chance = self.item_effects.get('critical_strike', 0) * 0.01
        for element in ELEMENTS:
            attack_elem = self.item_effects.get(f'attack_{element}', 0)
            monster_resistance = 1 - monster.res_elem.get(element, 0) * 0.01 if monster else 1
            total_attack += (attack_elem * crit_chance * 1.5 + attack_elem * (1 - crit_chance)) * monster_resistance
        return total_attack
