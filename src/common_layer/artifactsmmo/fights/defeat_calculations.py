from collections import Counter
from dataclasses import dataclass


@dataclass
class DefeatCalculations:
    turns_to_lose: float
    required_hp: float
    used_utilities: Counter
