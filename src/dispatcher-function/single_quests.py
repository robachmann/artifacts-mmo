from datetime import datetime, UTC, timedelta
from typing import Dict, List

from artifactsmmo.models import CraftSkill
from artifactsmmo.service.helpers import character_1_name, character_5_name, character_4_name, character_3_name, \
    character_2_name
from artifactsmmo.service.tasks import Task
from artifactsmmo.service.until import Until


def single_quests() -> Dict[str, List[List[Task] | Task]]:
    return {
        # Frequently used tasks:
        # Task.exchange_task_coins()
        # Task.exchange_gifts()
        # Task.recycle_excess_items(),
        # Task.recycle_excess_items(skill=CraftSkill.GEARCRAFTING),
        # Task.solve_achievements(achievement_type=AchievementType.GATHERING)
        # Task.solve_task()
        # Task.solve_task(allow_cancellation=False)
        # Task.solve_task(task_type='items', task_id=task_id())
        # Task.upgrade_basic_parts()
        # Task.upgrade_basic_parts(skill=CraftSkill.ALCHEMY)

        character_1_name(): [

        ],
        character_2_name(): [
            Task.recycle_excess_items(skill=CraftSkill.GEARCRAFTING),
        ],
        character_3_name(): [

        ],
        character_4_name(): [

        ],
        character_5_name(): [

        ],
    }
