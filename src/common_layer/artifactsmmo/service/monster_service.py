from collections import defaultdict
from itertools import chain
from typing import Dict, List, Optional, Iterator

from artifactsmmo.client.client import Client
from artifactsmmo.extensions import MonsterSchemaExtension
from artifactsmmo.models import MonsterSchema, EventSchema
from artifactsmmo.singleton import SingletonMeta


class MonsterService(metaclass=SingletonMeta):
    def __init__(self, client: Client):
        self.client = client

        self.__monsters_list: List[MonsterSchemaExtension] = []
        self.__monsters_map: Dict[str, MonsterSchemaExtension] = {}
        self.__monster_levels_map: Dict[int, List[MonsterSchemaExtension]] = defaultdict(list)
        self.__monster_drops_map: Dict[str, List[MonsterSchemaExtension]] = defaultdict(list)

    def init_monsters(self):
        monsters_list: List[MonsterSchema] = self.client.get_all_monsters()
        all_events: List[EventSchema] = self.client.get_all_events()
        event_monsters: List[str] = [event.content.code for event in all_events if event.content.type == 'monster']

        for monster in monsters_list:
            monster_ext = MonsterSchemaExtension(monster)
            monster_ext.is_event_monster = monster.code in event_monsters
            self.__monsters_list.append(monster_ext)
            self.__monsters_map[monster.code] = monster_ext
            self.__monster_levels_map[monster.level].append(monster_ext)
            for drop in monster.drops:
                self.__monster_drops_map[drop.code].append(monster_ext)

    def get_all_monsters(self) -> Iterator[MonsterSchemaExtension]:
        if not self.__monsters_list:
            self.init_monsters()
        yield from self.__monsters_list

    def get_monster(self, code: str) -> Optional[MonsterSchemaExtension]:
        if not self.__monsters_map:
            self.init_monsters()
        return self.__monsters_map.get(code)

    def get_monsters_by_drop(self, drop_code: str) -> List[MonsterSchemaExtension]:
        if not self.__monster_drops_map:
            self.init_monsters()
        return self.__monster_drops_map.get(drop_code, [])

    def get_monsters_by_level(self, min_level: int, max_level: int) -> List[MonsterSchemaExtension]:
        if not self.__monster_levels_map:
            self.init_monsters()
        return list(
            chain.from_iterable(
                self.__monster_levels_map[level] for level in range(min_level, max_level + 1) if level in self.__monster_levels_map
            )
        )
