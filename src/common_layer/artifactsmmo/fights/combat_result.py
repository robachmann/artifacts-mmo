from collections import Counter
from dataclasses import dataclass
from decimal import Decimal
import json
import math
from typing import Any, Dict, List, Optional

from artifactsmmo.extensions import MonsterSchemaExtension
from artifactsmmo.fights.fight_bundle import GenericFightBundle
from artifactsmmo.game_constants import WIN_RATE_THRESHOLD


@dataclass(slots=True)
class CombatResultDTO:
    win_rate: Decimal
    cooldown: Decimal
    turns_to_win: Decimal
    turns_to_lose: Decimal

    required_hp: Decimal
    required_hp_percent: Decimal
    min_required_hp: int
    max_required_hp: int

    gather_time: int
    prospecting_stat: int

    equipment_changes: int
    used_utilities_sum: int
    used_utilities_count: int

    characters: Dict
    characters_win: bool

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> 'CombatResultDTO':
        def d(key: str, default=None):
            return data.get(key, default)

        return cls(
            win_rate=Decimal(str(d('win_rate', 0))),
            cooldown=Decimal(str(d('cooldown', 0))),
            turns_to_win=Decimal(str(d('turns_to_win', 0))),
            turns_to_lose=Decimal(str(d('turns_to_lose', 0))),
            required_hp=Decimal(str(d('required_hp', 0))),
            required_hp_percent=Decimal(str(d('required_hp_percent', 0))),
            min_required_hp=int(d('min_required_hp', 0)),
            max_required_hp=int(d('max_required_hp', 0)),
            gather_time=int(d('gather_time', 0)),
            prospecting_stat=int(d('prospecting_stat', 0)),
            equipment_changes=int(d('equipment_changes', 0)),
            used_utilities_sum=int(d('used_utilities_sum', 0)),
            used_utilities_count=int(d('used_utilities_count', 0)),
            characters=d('characters', {}),
            characters_win=d('characters_win', False),
        )

    @classmethod
    def from_combat_results(cls, combat_result: 'CombatResults') -> 'CombatResultDTO':
        return CombatResultDTO(
            win_rate=Decimal(str(combat_result.raw_result.win_rate)),
            cooldown=Decimal(str(combat_result.raw_result.cooldown)),
            turns_to_win=Decimal(str(combat_result.raw_result.turns_to_win)),
            turns_to_lose=Decimal(str(combat_result.raw_result.turns_to_lose)),
            required_hp=Decimal(str(combat_result.raw_result.required_hp)),
            required_hp_percent=Decimal(str(combat_result.raw_result.required_hp_percent)),
            min_required_hp=combat_result.raw_result.min_required_hp,
            max_required_hp=combat_result.raw_result.max_required_hp,
            gather_time=int(combat_result.gather_time),
            prospecting_stat=int(combat_result.prospecting_stat),
            equipment_changes=int(combat_result.equipment_changes),
            used_utilities_sum=int(combat_result.used_utilities_sum),
            used_utilities_count=int(combat_result.used_utilities_count),
            characters={
                name: {
                    'used_utilities': dict(c.used_utilities),
                    'equipment_changes': c.equipment_changes,
                    'required_hp_median': c.required_hp_median,
                    'remaining_hp_list': list(c.remaining_hp_map.keys()),
                    'equipment': c.equipment,
                    'level': c.level,
                }
                for name, c in combat_result.characters.items()
            },
            characters_win=bool(combat_result.character_wins),
        )


@dataclass
class CombatResult:
    win_rate: Optional[float] = None
    cooldown: Optional[float] = None
    total_turns: Optional[float] = None
    turns_to_win: Optional[float] = None
    total_turns_if_win: Optional[float] = None
    turns_to_lose: Optional[float] = None
    total_turns_if_lose: Optional[float] = None
    required_hp: Optional[float] = None
    min_required_hp: Optional[int] = None
    max_required_hp: Optional[int] = None


@dataclass(slots=True)
class CharacterResult:
    max_hp: int
    required_hp_map: dict
    remaining_hp_map: dict
    used_utilities: Dict[str, int]
    required_hp_median: float
    equipment: Dict[str, str]
    equipment_changes: int
    level: Optional[int]


@dataclass(slots=True)
class RoundResult:
    max_hp: int
    start_hp: int
    half_start_hp: int
    required_hp_list: List[int]
    required_hp_map: Dict[int, int]
    remaining_hp_map: Dict[int, int]
    used_utilities: Dict[str, int]
    required_hp_median: float


class CombatResults:
    def __init__(
        self,
        win_rate: float,
        turns_to_win: float,
        turns_to_lose: float,
        cooldown: float,
        required_hp: float,
        required_hp_percent: float,
        min_required_hp: int,
        max_required_hp: int,
        prospecting: int,
        sample_size: int = None,
        monster: MonsterSchemaExtension = None,
        characters: Dict[str, CharacterResult] = None,
        fight_bundle: Optional[GenericFightBundle] = None,
    ):
        self.raw_result = CombatResult()
        self.rounded_result = CombatResult()
        self.equipment_changes = 0
        self.prospecting_stat = prospecting
        self.raw_result.win_rate = win_rate
        self.rounded_result.win_rate = round(win_rate)
        self.character_wins = win_rate > WIN_RATE_THRESHOLD
        self.raw_result.turns_to_win = turns_to_win
        self.rounded_result.turns_to_win = math.ceil(turns_to_win)
        self.raw_result.turns_to_lose = turns_to_lose
        self.rounded_result.turns_to_lose = math.floor(turns_to_lose)
        self.raw_result.cooldown = cooldown
        self.rounded_result.cooldown = cooldown
        self.rounded_result.required_hp = math.ceil(required_hp)
        self.rounded_result.required_hp_percent = math.ceil(required_hp_percent)
        self.raw_result.required_hp = required_hp
        self.raw_result.required_hp_percent = required_hp_percent
        self.rounded_result.min_required_hp = min_required_hp
        self.raw_result.min_required_hp = min_required_hp
        self.rounded_result.max_required_hp = max_required_hp
        self.raw_result.max_required_hp = max_required_hp
        rest_time = max(3, self.rounded_result.required_hp_percent) if self.rounded_result.required_hp_percent > 0 else 0
        self.recovery_time = cooldown + rest_time
        self.gather_time = math.ceil(self.recovery_time / (1 + prospecting * 0.001) / (win_rate * 0.01 if win_rate > 0 else 0.0001))
        self.sample_size = sample_size
        self.monster = monster
        self.characters: Dict[str, CharacterResult] = characters if characters is not None else {}

        used_utilities = Counter()
        for character in self.characters.values():
            used_utilities.update(character.used_utilities)
        self.used_utilities_sum = used_utilities.total() if used_utilities else 0
        self.used_utilities_count = len(used_utilities)
        self.fight_bundle = fight_bundle

    def to_string(self):
        used_utilities = Counter()
        for character in self.characters.values():
            used_utilities.update(character.used_utilities)

        turns_to_lose_string = f'{self.raw_result.turns_to_lose:.2f}' if self.raw_result.turns_to_lose < 1e6 else '∞'

        character_details = []
        for character_name, character in self.characters.items():
            character_details.append(
                str(
                    dict(
                        character=character_name,
                        used_utilities=dict(character.used_utilities),
                        equipment_changes=character.equipment_changes,
                        required_hp_median=character.required_hp_median,
                        equipment=character.equipment,
                    )
                )
            )

        return (
            f'result={self.__format_win_rate()} (n={self.sample_size}), cooldown={self.rounded_result.cooldown}, '
            f'prospecting={self.prospecting_stat}, '
            f'gather_time={self.gather_time}, p90_required_hp={self.rounded_result.required_hp}, '
            f'min_required_hp={self.rounded_result.min_required_hp}, max_required_hp={self.rounded_result.max_required_hp}, '
            f'turns_to_lose={turns_to_lose_string}, '
            f'turns_to_win={self.raw_result.turns_to_win:.2f}, '
            f'equipments={", ".join(character_details)}'
        )

    def __format_win_rate(self) -> str:
        if any(c.used_utilities for c in self.characters.values()):
            if self.raw_result.win_rate > WIN_RATE_THRESHOLD:
                icon = '🥩'
            elif self.raw_result.win_rate < 1:
                icon = '❌'
            else:
                icon = '⚠️'
        else:
            if self.raw_result.win_rate > WIN_RATE_THRESHOLD:
                icon = '✅'
            elif self.raw_result.win_rate < 1:
                icon = '❌'
            else:
                icon = '⚠️'
        return f'{self.raw_result.win_rate:.3f}% {icon}'

    def format_win_rate_icons(self) -> str:
        if any(c.used_utilities for c in self.characters.values()):
            if self.raw_result.win_rate > WIN_RATE_THRESHOLD:
                icon = '🥩'
            elif self.raw_result.win_rate < 1:
                icon = '❌'
            else:
                icon = '⚠️'
        else:
            if self.raw_result.win_rate > WIN_RATE_THRESHOLD:
                icon = '✅'
            elif self.raw_result.win_rate < 1:
                icon = '❌'
            else:
                icon = '⚠️'
        return f'{icon}'

    @classmethod
    def empty_win_rate(cls, required_hp: float, fight_bundle: Optional[GenericFightBundle]):
        return cls(
            win_rate=0,
            turns_to_win=100,
            turns_to_lose=1,
            cooldown=600,
            required_hp=required_hp,
            required_hp_percent=100,
            min_required_hp=int(required_hp),
            max_required_hp=int(required_hp),
            sample_size=0,
            prospecting=0,
            fight_bundle=fight_bundle,
        )

    def format_simulator_json(self) -> str:
        dicts: List[dict] = []
        for character in self.characters.values():
            character_dict = {}
            if character.level:
                character_dict['level'] = character.level
            for slot_name, equipment_code in character.equipment.items():
                character_dict[f'{slot_name}_slot'] = equipment_code
            for idx, (utility_name, utility_qty) in enumerate(character.used_utilities.items(), 1):
                character_dict[f'utility{idx}_slot'] = utility_name
                character_dict[f'utility{idx}_slot_quantity'] = utility_qty
            dicts.append(character_dict)
        return json.dumps(dicts, indent=2)


def minimize_gather_time_boss(result: CombatResults):
    return (
        -result.character_wins,
        result.gather_time,
        -result.prospecting_stat,
        result.rounded_result.required_hp,
        result.used_utilities_sum,
        result.used_utilities_count,
        result.equipment_changes,
        -result.raw_result.turns_to_lose,
    )


def minimize_gather_time(result: CombatResults):
    return (
        -result.character_wins,
        result.gather_time,
        -result.prospecting_stat,
        result.rounded_result.required_hp,
        result.used_utilities_sum,
        result.used_utilities_count,
        result.equipment_changes,
    )


def minimize_gather_time_island(result: CombatResults):
    return (
        -(result.raw_result.win_rate == 100),
        -result.character_wins,
        result.gather_time,
        -result.prospecting_stat,
        result.rounded_result.required_hp,
        result.used_utilities_sum,
        result.used_utilities_count,
        result.equipment_changes,
    )


def minimize_cooldown(result: CombatResults):
    return (
        -(result.raw_result.win_rate == 100),
        -result.character_wins,
        result.raw_result.cooldown,
        -result.raw_result.win_rate,
        -result.prospecting_stat,
        result.rounded_result.required_hp,
        result.used_utilities_sum,
        result.used_utilities_count,
        result.equipment_changes,
    )


def minimize_required_hp(result: CombatResults):
    return (
        -(result.raw_result.win_rate == 100),
        -result.character_wins,
        result.rounded_result.required_hp,
        -result.prospecting_stat,
        result.gather_time,
        result.used_utilities_sum,
        result.used_utilities_count,
        result.equipment_changes,
    )


def minimize_est_turns(result: CombatResults):
    return (
        result.fight_bundle.est_turns_ratio,
        -result.character_wins,
        result.gather_time,
        -result.prospecting_stat,
        result.rounded_result.required_hp,
        result.used_utilities_sum,
        result.used_utilities_count,
        result.equipment_changes,
        -result.raw_result.turns_to_lose,
    )


def minimize_used_utilities(result: CombatResults, other_config_wins: bool):
    if result.character_wins or other_config_wins:
        return (
            -result.character_wins,
            result.used_utilities_sum,
            result.used_utilities_count,
            -result.raw_result.win_rate,
            result.gather_time,
            result.rounded_result.required_hp,
            -result.raw_result.turns_to_lose,
        )
    else:
        return (
            -result.raw_result.win_rate,
            result.used_utilities_sum,
            result.used_utilities_count,
            result.gather_time,
            result.rounded_result.required_hp,
            -result.raw_result.turns_to_lose,
        )


def minimize_forced_used_utilities(result: CombatResults, other_config_wins: bool):
    if result.character_wins or other_config_wins:
        return (
            -result.character_wins,
            result.gather_time,
            result.rounded_result.required_hp,
            -result.raw_result.turns_to_lose,
        )
    else:
        return (
            -result.raw_result.win_rate,
            result.fight_bundle.est_turns_ratio,
        )
