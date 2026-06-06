from typing import Dict, Iterator, List, Optional, Set

from artifactsmmo.client.client import Client
from artifactsmmo.extensions import CharacterSchemaExtension, ItemSchemaExtension
from artifactsmmo.game_constants import ENABLE_APPLE_CONSUMPTION, ENABLE_COCONUT_CONSUMPTION, SKILLS
from artifactsmmo.singleton import SingletonMeta


class ItemService(metaclass=SingletonMeta):
    def __init__(self, client: Client):
        self.__client = client
        self.__all_items_ext_list: List[ItemSchemaExtension] = []
        self.__all_items_ext_code_map: Dict[str, ItemSchemaExtension] = {}
        self.__all_items_ext_type_map: Dict[str, List[ItemSchemaExtension]] = {}
        self.__all_tools: Dict[str, List[ItemSchemaExtension]] = {}
        self.__teleport_item_codes: List[str] = []
        self.__item_types_map: Dict[str, str] = {}
        self.__processed_food_list: Set[ItemSchemaExtension] = set()
        self.__unprocessed_food_list: Set[ItemSchemaExtension] = set()

    def init_items(self):
        task_reward_codes = [r.code for r in self.__client.get_all_task_rewards()]
        npc_item_codes = []
        npc_items = self.__client.get_all_npc_items()
        npc_item_map = {item.code: item for item in npc_items}
        for npc_item in npc_items:
            if npc_item.buy_price is not None and npc_item.buy_price > 0:
                npc_item_codes.append(npc_item.code)

        unprocessed_food_codes: Set[str] = set()
        for item in self.__client.get_all_items():
            is_npc_item = bool(not item.craft and item.code in npc_item_codes)
            item_ext = ItemSchemaExtension(
                item,
                is_task_reward=item.code in task_reward_codes,
                is_npc_item=is_npc_item,
            )
            if item.code in npc_item_map:
                npc_item = npc_item_map[item.code]
                if npc_item.currency == 'gold':
                    item_ext.buy_price = npc_item.buy_price
                    item_ext.sell_price = npc_item.sell_price
                    item_ext.sell_to = npc_item.npc

            self.__all_items_ext_list.append(item_ext)
            self.__all_items_ext_code_map[item.code] = item_ext
            if item_ext.is_teleport_item:
                self.__teleport_item_codes.append(item.code)
            if item.type:
                if item.type not in self.__all_items_ext_type_map:
                    self.__all_items_ext_type_map[item.type] = []
                self.__all_items_ext_type_map[item.type].append(item_ext)
                self.__item_types_map[item.code] = item.type

                for effect_name, effect_value in item_ext.item_effects.items():
                    if effect_value < 0 and effect_name in SKILLS:
                        if effect_name not in self.__all_tools:
                            self.__all_tools[effect_name] = []
                        self.__all_tools[effect_name].append(item_ext)

            if 'heal' in item_ext.item_effects:
                if item.craft:
                    item_ext.is_processed_food = True
                    self.__processed_food_list.add(item_ext)
                    for craft in item.craft.items:
                        unprocessed_food_codes.add(craft.code)
                elif (
                    item_ext.is_npc_item
                    or (item.code == 'apple' and ENABLE_APPLE_CONSUMPTION)
                    or (item.code == 'coconut' and ENABLE_COCONUT_CONSUMPTION)
                ):
                    item_ext.is_processed_food = True
                    self.__processed_food_list.add(item_ext)
                else:
                    unprocessed_food_codes.add(item.code)

        for item_code in unprocessed_food_codes:
            self.__unprocessed_food_list.add(self.__all_items_ext_code_map[item_code])

    def get_item_by_code(self, code: str) -> Optional[ItemSchemaExtension]:
        if not self.__all_items_ext_code_map:
            self.init_items()
        return self.__all_items_ext_code_map.get(code)

    def get_items_by_type(self, item_type: str) -> Iterator[ItemSchemaExtension]:
        if not self.__all_items_ext_type_map:
            self.init_items()
        yield from self.__all_items_ext_type_map[item_type]

    def get_all_items(self) -> Iterator[ItemSchemaExtension]:
        if not self.__all_items_ext_list:
            self.init_items()
        yield from self.__all_items_ext_list

    def get_teleport_item_codes(self) -> List[str]:
        if not self.__teleport_item_codes:
            self.init_items()
        return self.__teleport_item_codes

    def get_tools(self, skill: str, max_level: int = 50, character: CharacterSchemaExtension = None) -> Iterator[ItemSchemaExtension]:
        if not self.__all_tools:
            self.init_items()
        for tool in self.__all_tools[skill]:
            if character:
                if character.can_equip(tool):
                    yield tool
            else:
                if max_level >= tool.level:
                    yield tool

    def get_item_types(self) -> Dict[str, str]:
        if not self.__item_types_map:
            self.init_items()
        return self.__item_types_map

    def get_processed_food(self) -> Set[ItemSchemaExtension]:
        if not self.__processed_food_list:
            self.init_items()
        return self.__processed_food_list

    def get_unprocessed_food(self) -> Set[ItemSchemaExtension]:
        if not self.__unprocessed_food_list:
            self.init_items()
        return self.__unprocessed_food_list
