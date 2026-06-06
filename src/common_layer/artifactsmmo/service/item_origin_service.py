from collections import defaultdict
from dataclasses import dataclass, field
import os
from typing import Dict, List, Optional, Set

from artifactsmmo.client.client import Client
from artifactsmmo.extensions import ItemSchemaExtension
from artifactsmmo.service.item_service import ItemService
from artifactsmmo.service.monster_service import MonsterService
from artifactsmmo.service.npc_service import NPCService
from artifactsmmo.service.resource_service import ResourceService


@dataclass
class NpcOffer:
    price: int
    currency: str
    is_event: bool


@dataclass
class ItemDrop:
    drop_rate: int
    is_event: bool
    is_boss: bool


@dataclass
class ItemOrigin:
    monsters: Dict[str, ItemDrop] = field(default_factory=dict)
    resources: Dict[str, ItemDrop] = field(default_factory=dict)
    tasks: List[ItemDrop] = field(default_factory=list)
    npcs: Dict[str, NpcOffer] = field(default_factory=dict)
    monster_tree: List[List[str]] = field(default_factory=list)

    def min_drop_rate(self, include_event_drops: bool = False, include_task_drops: bool = False) -> Optional[int]:
        all_drop_rates: List[int] = []
        for drop in self.monsters.values():
            if not drop.is_event or include_event_drops:
                all_drop_rates.append(drop.drop_rate)

        for drop in self.resources.values():
            if not drop.is_event or include_event_drops:
                all_drop_rates.append(drop.drop_rate)

        if include_task_drops:
            for drop in self.tasks:
                all_drop_rates.append(drop.drop_rate)

        if all_drop_rates:
            return min(all_drop_rates)

    def is_task_exclusive(self) -> bool:
        return not self.monsters and not self.resources and self.tasks

    def is_event_exclusive(self) -> bool:
        result = True
        for monster in self.monsters.values():
            if not monster.is_event:
                return False
        for resource in self.resources.values():
            if not resource.is_event:
                return False
        for npc in self.npcs.values():
            if not npc.is_event:
                return False
        return result

    def is_boss_exclusive(self) -> bool:
        if self.resources or self.npcs or self.tasks:
            return False
        for monster in self.monsters.values():
            if not monster.is_boss:
                return False
        return True

    def is_npc_exclusive(self) -> bool:
        if self.monsters or self.resources or self.tasks:
            return False
        else:
            return bool(self.npcs)


class ItemOriginService:
    def __init__(
        self,
        client: Client,
        item_service: ItemService,
        monster_service: MonsterService,
        resource_service: ResourceService,
        npc_service: NPCService,
    ):
        self.__client = client
        self.__item_service = item_service
        self.__monster_service = monster_service
        self.__resource_service = resource_service
        self.__npc_service = npc_service
        self.__all_item_origins_map: Dict[str, ItemOrigin] = {}
        self.__all_item_products_map: Dict[str, List[ItemSchemaExtension]] = {}
        self.__rare_drop_codes: Set[str] = {code for code in os.getenv('DROP_CODES', '').split(',') if code}

    def init_items(self):
        npc_currency_map: Dict[str, List[str]] = defaultdict(list)
        for npc in self.__npc_service.get_all_npcs():
            for item_code, item_obj in npc.items.items():
                if item_obj.currency != 'gold':
                    npc_currency_map[item_obj.currency].append(item_code)

        for item in self.__item_service.get_all_items():
            origin = self.__resolve_item_origin(item)
            if origin and (origin.resources or origin.monsters or origin.npcs or origin.tasks or origin.monster_tree):
                self.__all_item_origins_map[item.code] = origin
                if self.__is_rare_drop(origin):
                    self.__rare_drop_codes.add(item.code)
            if item.craft:
                for craft in item.craft.items:
                    if craft.code not in self.__all_item_products_map:
                        self.__all_item_products_map[craft.code] = []
                    self.__all_item_products_map[craft.code].append(item)
            if item.code in npc_currency_map:
                if item.code not in self.__all_item_products_map:
                    self.__all_item_products_map[item.code] = []
                for product_code in npc_currency_map[item.code]:
                    self.__all_item_products_map[item.code].append(self.__item_service.get_item_by_code(product_code))

    def get_item_origin(self, item_code: str) -> Optional[ItemOrigin]:
        if not self.__all_item_origins_map:
            self.init_items()
        return self.__all_item_origins_map.get(item_code)

    def get_item_products(self, item_code: str) -> List[ItemSchemaExtension]:
        if not self.__all_item_products_map:
            self.init_items()
        return self.__all_item_products_map.get(item_code, [])

    def get_rare_drop_codes(self) -> Set[str]:
        if not self.__rare_drop_codes:
            self.init_items()
        return self.__rare_drop_codes

    def is_rare_drop(self, item_code: str) -> bool:
        if not self.__rare_drop_codes:
            self.init_items()
        return item_code in self.__rare_drop_codes

    def __resolve_item_origin(self, item: ItemSchemaExtension) -> Optional[ItemOrigin]:
        origin = ItemOrigin()
        for monster in self.__monster_service.get_monsters_by_drop(item.code):
            origin.monsters[monster.code] = next(ItemDrop(d.rate, monster.is_event_monster, monster.is_boss_monster) for d in monster.drops if d.code == item.code)

        for resource in self.__resource_service.get_resources_by_drop(item.code):
            origin.resources[resource.code] = next(ItemDrop(d.rate, resource.is_event_drop, False) for d in resource.drops if d.code == item.code)

        if item.is_task_reward:
            for task_reward in self.__client.get_all_task_rewards():
                if task_reward.code == item.code:
                    origin.tasks.append(ItemDrop(task_reward.rate, False, False))
                    break

        npcs = self.__npc_service.get_npcs_by_item_code(item.code)
        for npc in npcs:
            npc_item = npc.items[item.code]
            if npc_item.buy_price:
                origin.npcs[npc.code] = NpcOffer(npc_item.buy_price, npc_item.currency, npc.is_event_npc)

        monster_tree = self.__resolve_monster_tree(item)
        origin.monster_tree = self.clean_list(monster_tree)
        return origin

    def is_recursively_empty(self, item):
        if isinstance(item, list):
            return all(self.is_recursively_empty(sub) for sub in item)
        return False

    def clean_list(self, lst, depth=0):
        if not isinstance(lst, list):
            return lst
        if depth == 0 and all(isinstance(l, str) for l in lst):
            return [lst]

        # Step 1: Recursively clean and remove empty lists
        cleaned = [self.clean_list(item, depth + 1) for item in lst if not self.is_recursively_empty(item)]

        # Step 2: Flatten one level at top
        if depth == 0:
            result = []
            for item in cleaned:
                if isinstance(item, list) and all(isinstance(sub, list) for sub in item):
                    result.extend(item)
                else:
                    result.append(item)

            # Step 3: Deduplicate based on contents
            seen = set()
            deduped = []
            for elem in result:
                key = tuple(elem) if isinstance(elem, list) else elem
                if key not in seen:
                    seen.add(key)
                    deduped.append(elem)
            return deduped

        # Step 4: Unwrap single-item lists (only at depth > 0)
        if len(cleaned) == 1 and isinstance(cleaned[0], list):
            return cleaned[0]

        return cleaned

    def __resolve_monster_tree(self, item: ItemSchemaExtension) -> List[List[str]]:
        monster_tree = []

        for monster in self.__monster_service.get_monsters_by_drop(item.code):
            monster_tree.append(monster.code)

        npcs = self.__npc_service.get_npcs_by_item_code(item.code)
        for npc in npcs:
            npc_item = npc.items[item.code]
            if npc_item.buy_price:
                if npc_item.currency != 'gold':
                    drop_item = npc_item.currency
                    monsters = [monster.code for monster in self.__monster_service.get_monsters_by_drop(drop_item)]
                    monster_tree.append(monsters)

        if item.craft:
            depending_monster_tree = []
            for craft in item.craft.items:
                dependency_item = self.__item_service.get_item_by_code(craft.code)
                depending_monster_tree.append(self.__resolve_monster_tree(dependency_item))
            monster_tree.extend(depending_monster_tree)

        return monster_tree

    @staticmethod
    def __is_rare_drop(origin: ItemOrigin) -> bool:
        for drop in origin.monsters.values():
            if drop.drop_rate >= 100:
                return True

        for drop in origin.resources.values():
            if drop.drop_rate > 200 or (drop.drop_rate >= 100 and drop.is_event):
                return True

        for drop in origin.tasks:
            if drop.drop_rate > 5:
                return True

        return False
