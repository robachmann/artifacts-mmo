from collections import defaultdict
from typing import List, Dict, Optional, Iterator

from artifactsmmo.client.client import Client
from artifactsmmo.extensions import NPCSchemaExtension
from artifactsmmo.models import EventSchema, NPCItem
from artifactsmmo.singleton import SingletonMeta


class NPCService(metaclass=SingletonMeta):
    def __init__(self, client: Client):
        self.__client = client
        self.__all_npcs: List[NPCSchemaExtension] = []
        self.__all_npcs_code_map: Dict[str, NPCSchemaExtension] = {}
        self.__all_npcs_item_code_list_map: Dict[str, List[str]] = {}

    def __init_objects(self):
        all_events: List[EventSchema] = self.__client.get_all_events()
        event_npcs: List[str] = [event.content.code for event in all_events if event.content.type == 'npc']
        all_npc_items: Dict[str, List[NPCItem]] = defaultdict(list)
        for item in self.__client.get_all_npc_items():
            all_npc_items.setdefault(item.npc, []).append(item)

        for npc in self.__client.get_all_npcs():
            npc_ext = NPCSchemaExtension(npc)
            npc_ext.items = {item.code: item for item in all_npc_items.get(npc.code, [])}
            npc_ext.is_event_npc = npc.code in event_npcs
            self.__all_npcs.append(npc_ext)
            self.__all_npcs_code_map[npc.code] = npc_ext

            for item_code in npc_ext.items:
                if item_code not in self.__all_npcs_item_code_list_map:
                    self.__all_npcs_item_code_list_map[item_code] = []
                self.__all_npcs_item_code_list_map[item_code].append(npc.code)

    def get_all_npcs(self) -> Iterator[NPCSchemaExtension]:
        if not self.__all_npcs:
            self.__init_objects()
        yield from self.__all_npcs

    def get_npc(self, npc_code: str) -> Optional[NPCSchemaExtension]:
        if not self.__all_npcs_code_map:
            self.__init_objects()
        return self.__all_npcs_code_map[npc_code]

    def get_npcs_by_item_code(self, item_code: str) -> List[NPCSchemaExtension]:
        if not self.__all_npcs_item_code_list_map:
            self.__init_objects()
        return [self.get_npc(npc_code) for npc_code in self.__all_npcs_item_code_list_map.get(item_code, [])]

    def get_all_npc_items(self) -> Dict[str, List[str]]:
        if not self.__all_npcs_item_code_list_map:
            self.__init_objects()
        return self.__all_npcs_item_code_list_map
