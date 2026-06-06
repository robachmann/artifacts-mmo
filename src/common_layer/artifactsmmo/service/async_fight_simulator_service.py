from typing import List, Optional

from artifactsmmo.dynamodb.fight_simulator_table import FightSimulatorTable
from artifactsmmo.queue.fight_simulator_queue import FightSimulatorQueue


class AsyncFightSimulatorService:
    def __init__(self, fight_simulator_table: FightSimulatorTable, fight_simulator_queue: FightSimulatorQueue):
        self._fight_simulator_table = fight_simulator_table
        self._fight_simulator_queue = fight_simulator_queue

    def trigger_fight_simulator(
        self,
        participants: List[str],
        character_name: str,
        monster_code: str,
        exclude_items: Optional[List[str]] = None,
        force_utilities: bool = False,
        sort_function: Optional[str] = None,
        quest_id: Optional[int] = None,
    ) -> str:
        fight_simulator_id = self._fight_simulator_table.insert(
            participants, character_name, monster_code, exclude_items, force_utilities, sort_function, quest_id
        )
        self._fight_simulator_queue.invoke_fight_simulator(fight_simulator_id)
        return fight_simulator_id
