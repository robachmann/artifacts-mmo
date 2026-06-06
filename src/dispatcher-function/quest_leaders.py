from typing import Dict, List

from artifactsmmo.game_constants import LEADER_CRAFTING_SKILLS, MAX_LEVEL
from artifactsmmo.models import CraftSkill
from artifactsmmo.service.helpers import character_1_name, character_2_name, character_3_name, character_4_name, character_5_name
from artifactsmmo.service.tasks import Task
from artifactsmmo.log.logger import logger
from artifactsmmo.service.until import Until


def get_quest_join_exclusions() -> List[str]:
    return []


def get_quest_join_exclusion_map() -> Dict[str, List[str]]:
    return {}
    # example to prevent characters 1-4 to join quests of character 5
    # return {character_5_name(): [character_1_name(), character_2_name(), character_3_name(), character_4_name()]}


def get_quest_leaders() -> List[str]:
    return [character_1_name()]


def quest_leaders(skill_map: Dict[str, int]) -> Dict[str, List[Task]]:
    character_name = character_1_name()
    tasks: List[Task] = []
    return {character_name: tasks}
