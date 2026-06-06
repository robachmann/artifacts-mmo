from datetime import datetime, UTC
from typing import Dict


class ExecutionContext:
    def __init__(self, character_name: str = None):
        self.started_at_ts = datetime.now(UTC).timestamp()
        self.bank_items_maps: Dict[str, Dict[str, Dict[str, int]]] = {}
        self.character_name = character_name

    def set_bank_items_map(
        self,
        bank_items_map: Dict[str, int],
        task_id: str = None,
        ignore_reservations: bool = False,
    ):
        if str(task_id) not in self.bank_items_maps:
            self.bank_items_maps[str(task_id)] = {}
        self.bank_items_maps[str(task_id)][str(ignore_reservations)] = bank_items_map

    @classmethod
    def local(cls):
        context = cls()
        context.set_bank_items_map({'tasks_coin': 1})
        return context
