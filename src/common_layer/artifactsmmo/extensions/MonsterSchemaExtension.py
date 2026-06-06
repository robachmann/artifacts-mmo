from typing import Dict, Set

from artifactsmmo.game_constants import ELEMENTS
from artifactsmmo.models import MonsterSchema
from artifactsmmo.service import helpers


class MonsterSchemaExtension(MonsterSchema):
    def __init__(self, base_obj: MonsterSchema):
        super().__init__()
        self.__dict__.update(base_obj.__dict__)

        self.offensive_elements: Set[str] = set()
        self.res_elem: Dict[str, int] = {}
        self.attack_elem: Dict[str, int] = {}
        self.effect: Dict[str, int] = {}
        for effect in self.effects:
            self.effect[effect.code] = effect.value

        self.base_attack_sum = 0
        for element in ELEMENTS:
            attack = getattr(base_obj, f'attack_{element}') > 0
            if attack:
                self.offensive_elements.add(element)

            attack_elem = getattr(base_obj, f'attack_{element}', 0)
            self.attack_elem[element] = attack_elem
            self.base_attack_sum += attack_elem
            self.res_elem[element] = getattr(base_obj, f'res_{element}', 0)

        self.is_event_monster = False
        self.is_boss_monster = self.type == 'boss'
        self.is_venomous = 'poison' in self.effect

    def __hash__(self):
        return hash(self.code)

    def offensive_elements_emojis(self):
        return helpers.format_elements_emojis(self.offensive_elements)

    # def get_block_chance(self, element: str) -> float:
    #    block_chance = self.res_elem[element] * 0.001  # 10% of 1%
    #    return block_chance if block_chance > 0 else 0

    # def get_block_chance_of_elements(self, elements: List[str]) -> float:
    #    return sum(block_chance for element in elements if (block_chance := self.get_block_chance(element)) > 0)

    def to_flat_dict(self) -> dict:
        flat_dict = self.to_dict()
        for key, value in self.effect.items():
            flat_dict[f'effect.{key}'] = value
        # flat_dict['defensive_elements'] = self.defensive_elements
        # flat_dict['offensive_elements'] = self.offensive_elements
        flat_dict['is_event_monster'] = self.is_event_monster
        # flat_dict['strongest_offensive_elements'] = self.strongest_offensive_elements
        return flat_dict
