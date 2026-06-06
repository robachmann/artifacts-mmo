from collections import Counter
from dataclasses import dataclass
from itertools import chain, repeat
from typing import Dict, List, Set

from artifactsmmo.extensions import ItemSchemaExtension


class LiveStats:
    def __init__(self, name: str, max_hp: int, half_hp: int = None, current_hp: int = None):
        self.name = name
        self.max_hp = max_hp
        self.half_hp = half_hp
        if current_hp:
            self.current_hp = current_hp
        else:
            self.current_hp = max_hp
        self.lowest_hp: int = self.current_hp
        self.start_hp: int = self.current_hp
        self.poisoned: int = 0
        self.restore_utilities: Set[ItemSchemaExtension] = set()
        self.used_utilities: Counter[str] = Counter()
        self.burned: List[int] = []
        self.barrier: int = 0
        self.required_hp: int = 0
        self.shelled: bool = False
        self.berserked: bool = False
        self.shell_turns_left: int = 0
        self.dmg_modifiers: Dict[str, repeat[int | float] | chain[int | float]] = {}
        self.res_modifiers: Dict[str, int] = {}
        self.last_vampiric_strike_turn: int = -2
        self.guard_charges: int = 3
        self.redirect_guard_name: str = ''
        self.redirect_factor: float = 0.0
        self.standard_hits = 0
        self.critical_hits = 0


@dataclass
class SimulationResult:
    characters_win: bool
    turns: int
    cooldown: int
    character_stats: Dict[str, LiveStats]
    monster_critical_hits: int
    monster_standard_hits: int
