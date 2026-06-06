from abc import ABC, abstractmethod
from enum import Enum
from typing import Optional, Set

from artifactsmmo.extensions import ItemSchemaExtension, MonsterSchemaExtension
from artifactsmmo.fights.character_fight_stats import CharacterFightStats
from artifactsmmo.fights.combat_result import CombatResults
from artifactsmmo.fights.fight_bundle import GenericFightBundle


class CombatCalculatorMode(Enum):
    APPROXIMATE = 'APPROXIMATE'
    GENERIC = 'GENERIC'


class CombatCalculator(ABC):
    @abstractmethod
    def calculate_win_rate(
        self,
        character: CharacterFightStats,
        monster: MonsterSchemaExtension,
        utilities: Set[ItemSchemaExtension] = None,
        fight_bundle: GenericFightBundle = None,
        print_log: bool = False,
        min_rounds: int = 0,
        force_simulation: bool = False,
    ) -> Optional[CombatResults]:
        pass
