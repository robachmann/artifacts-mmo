from collections import Counter, defaultdict
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from datetime import datetime, timedelta, UTC
from functools import cache
import math
import re
from typing import Dict, Iterator, List, Optional, Set, Tuple

from artifactsmmo import game_constants
from artifactsmmo.client.client import Client
from artifactsmmo.dynamodb.bank_reservations_table import BankReservation, BankReservationsTable
from artifactsmmo.dynamodb.logs_table import LogLine, LogsTable
from artifactsmmo.extensions import CharacterSchemaExtension, ItemSchemaExtension, MonsterSchemaExtension, NPCSchemaExtension
from artifactsmmo.extensions.account_achievement_schema_extension import AccountAchievementSchemaExtension
from artifactsmmo.extensions.CharacterSchemaExtension import CharacterSkill
from artifactsmmo.extensions.MapSchemaExtension import MapSchemaExtension
from artifactsmmo.extensions.resource_schema_extension import ResourceSchemaExtension
from artifactsmmo.game_constants import (
    MAX_LEVEL,
    RECYCLING_SKILLS,
    REST_THRESHOLD_SECONDS,
    RESTART_COOK_UPON_EMPTY_HEALING_CAPACITY,
    RESTART_FISHER_UPON_EMPTY_HEALING_CAPACITY,
    STATIC_RESERVATIONS,
)
from artifactsmmo.log.logger import logger
from artifactsmmo.models import (
    AccountAchievementObjectiveSchema,
    AccountLeaderboardSchema,
    AchievementType,
    ActiveEventSchema,
    BankSchema,
    EventSchema,
    GatheringSkill,
    GEOrderSchema,
    GEOrderType,
    LogSchema,
    LogType,
    MapContentType,
    MyAccountDetails,
    PendingItemSchema,
    SimpleItemSchema,
    StatusSchema,
    TaskFullSchema,
)
from artifactsmmo.service.execution_context import ExecutionContext
from artifactsmmo.service.helpers import (
    character_1_name,
    character_2_name,
    character_3_name,
    character_4_name,
    character_5_name,
    CraftableItem,
    escape_string,
    format_long_number,
    is_item_available,
    ItemDropRate,
    RecyclableItem,
    ResolvedItemRecipe,
    ResolvedItemRecipeDetails,
    ShoppingBasket,
)
from artifactsmmo.service.item_origin_service import ItemOrigin, ItemOriginService
from artifactsmmo.service.item_service import ItemService
from artifactsmmo.service.map_service import MapService, Route
from artifactsmmo.service.monster_service import MonsterService
from artifactsmmo.service.npc_service import NPCService
from artifactsmmo.service.resource_service import ResourceService
from artifactsmmo.service.tasks import Task


@dataclass(slots=True)
class AccountItems:
    account: Counter[str]
    bank: Counter[str]
    character_equipment: Dict[str, Counter[str]]
    character_inventory: Dict[str, Counter[str]]

    def __init__(self):

        self.account = Counter()
        self.bank = Counter()
        self.character_equipment = {
            character_1_name(): Counter(),
            character_2_name(): Counter(),
            character_3_name(): Counter(),
            character_4_name(): Counter(),
            character_5_name(): Counter(),
        }
        self.character_inventory = {
            character_1_name(): Counter(),
            character_2_name(): Counter(),
            character_3_name(): Counter(),
            character_4_name(): Counter(),
            character_5_name(): Counter(),
        }


class Service:
    def __init__(self, client: Client):
        self.client: Client = client
        self.__bank_reservations_table: BankReservationsTable = BankReservationsTable()
        self.__map_service: MapService = MapService(client)
        self.__item_service: ItemService = ItemService(client)
        self.__monster_service: MonsterService = MonsterService(client)
        self.__resource_service: ResourceService = ResourceService(client)
        self.__npc_service: NPCService = NPCService(client)
        self.__item_origin_service = ItemOriginService(
            client, self.__item_service, self.__monster_service, self.__resource_service, self.__npc_service
        )
        self.__logs_table: LogsTable = LogsTable()

    def get_all_characters_inventory_map(
        self,
        characters: List[CharacterSchemaExtension] = None,
        include_equipment: bool = True,
    ) -> Dict[str, int]:
        characters = characters or self.get_all_character_details()
        characters_inventory: Dict[str, int] = defaultdict(int)
        for character in characters:
            for item_code, item_quantity in character.inventory_map.items():
                if item_code:
                    characters_inventory[item_code] += item_quantity

            if include_equipment:
                for item_code in character.equipment.values():
                    if item_code:
                        characters_inventory[item_code] += 1

        return characters_inventory

    def get_bank_items(self) -> List[SimpleItemSchema]:
        return self.client.get_bank_items()

    def get_pending_items(self) -> List[PendingItemSchema]:
        return self.client.get_pending_items()

    def get_bank_items_map_without_reservations(self) -> Dict[str, int]:
        return {item.code: item.quantity for item in self.get_bank_items()}

    def get_bank_items_map(
        self,
        task_id: str = None,
        ignore_reservations: bool = False,
        context: ExecutionContext = None,
        character_name: str = None,
    ) -> Dict[str, int]:
        if (
            context
            and context.bank_items_maps
            and str(task_id) in context.bank_items_maps
            and str(ignore_reservations) in context.bank_items_maps[str(task_id)]
        ):
            logger.info(f'Returning cached bank_items_map from context for task_id={task_id}, ignore_reservations={ignore_reservations}.')
            return context.bank_items_maps[str(task_id)][str(ignore_reservations)]
        else:
            bank_items_map: Dict[str, int] = self.get_bank_items_map_without_reservations()

            if not ignore_reservations:
                bank_reservations: List[BankReservation] = self.__bank_reservations_table.get_reservations()
                for reservation in bank_reservations:
                    if task_id is None or reservation.task_id != task_id:
                        item_code = reservation.item_code

                        if item_code in bank_items_map:
                            old_value = bank_items_map[item_code]
                            bank_items_map[item_code] = max(old_value - reservation.quantity, 0)

                if character_name:
                    for static_character_name, item_reservation_map in STATIC_RESERVATIONS.items():
                        if static_character_name != character_name:
                            for static_item_code, static_item_quantity in item_reservation_map.items():
                                if static_item_code in bank_items_map:
                                    old_value = bank_items_map[static_item_code]
                                    bank_items_map[static_item_code] = max(old_value - static_item_quantity, 0)

            if context:  # TODO: Might interfere with character_name's static reservation
                context.set_bank_items_map(bank_items_map, task_id, ignore_reservations)
                logger.info(f'Cached bank_items_map in context for task_id={task_id}, ignore_reservations={ignore_reservations}.')
            return bank_items_map

    def get_bank_details(self) -> BankSchema:
        return self.client.get_bank_details()

    def get_items_craft_into(self):
        craft_into_map: Dict[str, List[str]] = defaultdict(list)
        for item in self.get_all_items():
            if item.craft:
                for i in item.craft.items:
                    craft_into_map[i.code].append(item.code)
        return craft_into_map

    def get_closest_location(
        self, content_type: str = None, content_code: str = None, current_map: MapSchemaExtension = None
    ) -> Optional[MapSchemaExtension]:
        locations: List[MapSchemaExtension] = self.get_maps(content_type=content_type, content_code=content_code)

        if not locations:
            return None

        location_map: Dict[int, int] = {}
        location_ids_map: Dict[int, MapSchemaExtension] = {}
        for location in locations:
            location_ids_map[location.map_id] = location
            location_map[location.map_id] = self.get_distance_between(current_map, location)

        lowest_key = min(location_map, key=location_map.get)
        return location_ids_map[lowest_key]

    def get_character_details(self, character_name: str) -> CharacterSchemaExtension:
        return CharacterSchemaExtension(self.client.get_character(character_name))

    def get_all_character_details(self, account: str = None) -> List[CharacterSchemaExtension]:
        return [CharacterSchemaExtension(c) for c in self.client.get_characters(account)]

    def get_logs(self, character_name: str = None, count: int = 5) -> List[LogSchema]:
        return self.client.get_logs(size=count, character_name=character_name)

    def generate_uncraftable_sell_list(self, threshold: int = 500) -> List[SimpleItemSchema]:
        bank_items: List[SimpleItemSchema] = self.get_bank_items()
        craftable_parts = set()
        for item in self.get_all_items():
            if item.craft:
                for craft_item in item.craft.items:
                    craftable_parts.add(craft_item.code)
            if item.type == 'utility':
                craftable_parts.add(item.code)
            if item.subtype == 'tool':
                craftable_parts.add(item.code)

        sell_items: List[SimpleItemSchema] = []
        for item in bank_items:
            item_code = item.code

            if item_code not in craftable_parts and item_code != 'tasks_coin':
                item_quantity = item.quantity
                sell_quantity_max = max(item_quantity - threshold, 0)
                if sell_quantity_max > 0:
                    logger.info(f'Will sell {sell_quantity_max} {item_code}')
                    sell_items.append(SimpleItemSchema.from_dict({'code': item_code, 'quantity': sell_quantity_max}))
        return sell_items

    # TODO: Deserves some optimizations
    def generate_excess_sell_list(self, threshold, item_type='all', item_subtype='all', max_level: int = None) -> List[SimpleItemSchema]:
        bank_items: List[SimpleItemSchema] = self.get_bank_items()

        # Add items of specified type
        item_type_param = None
        if item_type != 'all':
            item_type_param = item_type
        items_of_type: List[ItemSchemaExtension] = list(self.get_items_by_type(item_type=item_type_param, max_level=max_level))
        items_of_type_map = {item.code: {'type': item.type, 'subtype': item.subtype} for item in items_of_type}

        # Remove items of wrong subtype
        for item in items_of_type:
            if item_subtype != 'all' and item.subtype != item_subtype:
                items_of_type_map.pop(item.code)

        # Create Sell Items List for Excess
        sell_items: List[SimpleItemSchema] = []
        for item in bank_items:
            if item.code in items_of_type_map and item.quantity > threshold and item.code != 'tasks_coin':
                item_quantity = item.quantity
                sell_quantity_max = max(item_quantity - threshold, 0)
                logger.info(f'Will sell {sell_quantity_max} {item.code}')
                sell_items.append(SimpleItemSchema.from_dict({'code': item.code, 'quantity': sell_quantity_max}))
        return sell_items

    def generate_recipe_buy_list(self, item_code: str, quantity: int) -> List[SimpleItemSchema]:
        resource_list: List[SimpleItemSchema] = []

        item: ItemSchemaExtension = self.get_item(item_code)
        if item.craft is not None:
            for item_to_buy in item.craft.items:
                item_stock = sum(a.quantity for a in self.client.get_ge_sell_orders(item_code=item_to_buy.code))
                if item_to_buy.quantity * quantity > item_stock:
                    missing_quantity = item_to_buy.quantity * quantity - item_stock
                    logger.info(f'Missing {missing_quantity} of item {item_to_buy.code}. GE Stock: {item_stock}')
                    if item_stock > 0:
                        logger.info(f'Buying {item_stock} of {item_to_buy.code}')
                        resource_list.append(SimpleItemSchema.from_dict({'code': item_to_buy.code, 'quantity': item_stock}))
                    resource_list.extend(self.generate_recipe_buy_list(item_to_buy.code, missing_quantity))
                else:
                    logger.info(f'Buying {item_to_buy.quantity * quantity} of {item_to_buy.code}')
                    resource_list.append(SimpleItemSchema.from_dict({'code': item_to_buy.code, 'quantity': item_to_buy.quantity * quantity}))
        return resource_list

    def get_ge_order(self, order_id: str) -> GEOrderSchema:
        return self.client.get_ge_order(order_id)

    def get_map(self, x, y, layer: str = 'overworld') -> MapSchemaExtension:
        return self.__map_service.get_map(layer, x, y)

    def get_map_by_id(self, map_id: int) -> MapSchemaExtension:
        return self.__map_service.get_map_by_id(map_id)

    def get_maps(self, content_type: str, content_code: str = None) -> List[MapSchemaExtension]:
        found_tiles = self.__map_service.get_maps(content_type, content_code)
        logger.debug(f'Found {len(found_tiles)} tiles with content_type={content_type} and content_code={content_code}')

        overloaded_map_ids: List[int] = []
        for tile in found_tiles:
            if tile.event_content and tile.interactions.content and tile.interactions.content.code:
                overloaded_map_ids.append(tile.map_id)
        if overloaded_map_ids:
            active_event_map_ids: List[int] = [active_event.map.map_id for active_event in self.get_active_events()]
            return [tile for tile in found_tiles if tile.map_id not in overloaded_map_ids or tile.map_id not in active_event_map_ids]
        else:
            return found_tiles

    def get_all_maps(self) -> Iterator[MapSchemaExtension]:
        return self.__map_service.get_all_maps()

    def get_route(self, from_cluster: str, to_cluster: str) -> Optional[Route]:
        if from_cluster == to_cluster:
            return Route.is_same_cluster(from_cluster, to_cluster)
        else:
            return self.__map_service.get_route(from_cluster, to_cluster)

    def get_gather_equipment(
        self,
        skill: GatheringSkill,
        character: CharacterSchemaExtension,
        bank_items_map: Dict[str, int] = None,
        equip_prospecting_gear: bool = True,
    ) -> Dict[str, str]:
        bank_items_map = bank_items_map or self.get_bank_items_map()
        equip_map: Dict[str, str] = {}

        sorted_bags = sorted(self.get_items_by_type('bag', max_level=character.level), key=lambda x: x.level, reverse=True)
        for item in sorted_bags:
            if character.bag_slot == item.code:
                equip_map['bag'] = item.code
                break
            if is_item_available(bank_count=bank_items_map.get(item.code, 0)):
                equip_map['bag'] = item.code
                break

        skill_str = str(skill)
        character_skill = character.skills.get(skill_str)

        for item in self.get_tools(skill=skill_str, max_level=character_skill.level, character=character):
            item_type = item.type.replace('artifact', 'artifact1')

            if item_type in equip_map:
                continue

            if character.equipment.get(item_type) == item.code:
                equip_map[item_type] = item.code
                continue

            if is_item_available(bank_count=bank_items_map.get(item.code, 0)):
                equip_map[item_type] = item.code

        if equip_prospecting_gear:
            equipped_items = character.equipment
            for gear_position in game_constants.GEAR_POSITIONS:
                if gear_position not in equip_map:
                    slot_item_code = equipped_items.get(gear_position)
                    if slot_item_code:
                        equipped_prospecting_value = self.get_item(slot_item_code).prospecting_value()
                    else:
                        equipped_prospecting_value = 0

                    item_type = gear_position.rstrip('123')
                    sorted_items = sorted(
                        [
                            item
                            for item in self.get_items_by_type(item_type, max_level=character.level)
                            if item.prospecting_value() > equipped_prospecting_value and not item.is_confining_gear()
                        ],
                        key=lambda x: x.prospecting_value(),
                        reverse=True,
                    )
                    for item in sorted_items:
                        if is_item_available(
                            currently_equipped=item.code in equipped_items,
                            bank_count=bank_items_map.get(item.code, 0),
                            item_index=item.item_index(),
                        ) and character.can_equip(item):
                            if item.type != 'artifact' or item.code not in equip_map.values():
                                equip_map[gear_position] = item.code
                                break

        return equip_map

    def get_ge_sell_orders(self, item_code: str = None) -> List[GEOrderSchema]:
        return self.client.get_ge_sell_orders(item_code, order_type=GEOrderType.SELL)

    def get_ge_buy_orders(self, item_code: str = None) -> List[GEOrderSchema]:
        return self.client.get_ge_sell_orders(item_code, order_type=GEOrderType.BUY)

    def get_account_ge_sell_orders(self) -> List[GEOrderSchema]:
        return self.client.get_account_sell_orders()

    def get_account_ge_buy_orders(self) -> List[GEOrderSchema]:
        return self.client.get_account_buy_orders()

    def get_ge_items_map(self) -> Dict[str, List[GEOrderSchema]]:
        ge_items: List[GEOrderSchema] = self.client.get_ge_sell_orders()
        grouped_orders: Dict[str, List[GEOrderSchema]] = defaultdict(list)
        for order in ge_items:
            grouped_orders[order.code].append(order)
        return grouped_orders

    def get_global_quantity(self, item_code: str, include_equipment: bool = True) -> int:
        bank_items_map = self.get_bank_items_map(ignore_reservations=True)
        all_characters_inventory_map = self.get_all_characters_inventory_map(include_equipment=include_equipment)
        return bank_items_map.get(item_code, 0) + all_characters_inventory_map.get(item_code, 0)

    def add_bank_reservation(self, task_id: str, item_code: str, quantity: int, character_name: str):
        self.__bank_reservations_table.add_reservation(task_id, item_code, quantity, character_name)

    def add_bank_reservations(self, reservation_id: str, equipment_map: Dict[str, int], character_name: str):
        self.__bank_reservations_table.add_reservations(reservation_id, equipment_map, character_name)

    def increment_bank_reservation(self, task_id: str, item_code: str, quantity: int, character_name: str):
        self.__bank_reservations_table.increment_reservation(task_id, item_code, quantity, character_name)

    def subtract_from_bank_reservation(self, task_id: str, item_code: str, quantity: int, character_name: str):
        bank_reservations: List[BankReservation] = self.__bank_reservations_table.get_reservations_of_task(task_id)
        for bank_reservation in bank_reservations:
            if bank_reservation.item_code == item_code:
                reserved_quantity = bank_reservation.quantity
                if quantity < reserved_quantity:
                    remaining_quantity = reserved_quantity - quantity
                    self.add_bank_reservation(task_id, item_code, remaining_quantity, character_name)
                    logger.info(
                        f'Replaced bank reservation for item={item_code}, character={character_name}: '
                        f'reserved_quantity={reserved_quantity}, quantity={quantity}, remaining_quantity={remaining_quantity}.'
                    )
                else:
                    self.delete_bank_reservation(task_id, item_code)
                break

    def delete_bank_reservation(self, task_id: str, item_code: str):
        self.__bank_reservations_table.delete_reservation(task_id=task_id, item_code=item_code)

    def delete_bank_reservations(self, task_id: str = None, character_name: str = None, character_list: List[CharacterSchemaExtension] = None):
        if character_name or character_list:
            character_names: List[str] = []
            if character_name:
                character_names.append(character_name)
            if character_list:
                for character in character_list:
                    character_names.append(character.name)

            all_bank_reservations = self.__bank_reservations_table.get_reservations()
            logger.info(f'Found {len(all_bank_reservations)} reservations: {[f"{r.task_id}: {r.character}" for r in all_bank_reservations]}')
            for bank_reservation in all_bank_reservations:
                if bank_reservation.character in character_names:
                    self.delete_bank_reservation(bank_reservation.task_id, bank_reservation.item_code)
        elif task_id:
            bank_reservations = self.__bank_reservations_table.get_reservations_of_task(task_id=task_id)
            for bank_reservation in bank_reservations:
                self.delete_bank_reservation(bank_reservation.task_id, bank_reservation.item_code)

    def get_bank_reservations_map(self) -> Dict[str, int]:
        result_map: Dict[str, int] = defaultdict(int)
        all_reservations = self.__bank_reservations_table.get_reservations()
        for reservation in all_reservations:
            result_map[reservation.item_code] += reservation.quantity
        return result_map

    def get_bank_reservations(self) -> List[BankReservation]:
        return self.__bank_reservations_table.get_reservations()

    def get_crafts(self, single_item: ItemSchemaExtension) -> List[ItemSchemaExtension]:
        result: List[ItemSchemaExtension] = []

        item: ItemSchemaExtension = self.get_item(single_item.code)
        if item.craft:
            for craft in item.craft.items:
                dep: ItemSchemaExtension = self.get_item(craft.code)
                result.extend(self.get_crafts(dep))
        else:
            result.append(single_item)

        return result

    def get_drop_rates(self, simple_item: SimpleItemSchema = None, item_code: str = None, all_max_level: bool = False) -> List[ItemDropRate]:
        return self.get_drop_rate(simple_item=simple_item, item_code=item_code, all_max_level=all_max_level)

    # TODO: Replace with above function
    def get_drop_rate(self, simple_item: SimpleItemSchema = None, item_code: str = None, all_max_level: bool = False) -> List[ItemDropRate]:
        drop_rate_list: List[ItemDropRate] = []

        if simple_item:
            item = self.get_item(simple_item.code)
        else:
            item = self.get_item(item_code)

        if item.craft:
            for craft in item.craft.items:
                dependencies: List[ItemDropRate] = self.get_drop_rate(simple_item=craft, all_max_level=all_max_level)
                for dependency in dependencies:
                    min_rate = int(craft.quantity * dependency.drop_rate_min)  # 10% markup for crafting time
                    max_rate = int(craft.quantity * dependency.drop_rate_max)  # 10% markup for crafting time
                    drop_rate_list.append(ItemDropRate(dependency.item_code, min_rate, max_rate))
        else:
            resource_drop_list: List[ResourceSchemaExtension] = self.get_resources_by_drop(item.code)
            drop_rate_min = None
            drop_rate_max = None
            if len(resource_drop_list) > 0:
                for r in resource_drop_list:
                    for drop in r.drops:
                        if drop.code == item.code:
                            min_rate = drop.rate / drop.max_quantity
                            max_rate = drop.rate / drop.min_quantity

                            should_break = False
                            if not drop_rate_min or min_rate < drop_rate_min:
                                drop_rate_min = min_rate
                                should_break = True
                            if not drop_rate_max or max_rate > drop_rate_max:
                                drop_rate_max = max_rate
                                should_break = True

                            if should_break:
                                break
            else:
                monster_drop_list: List[MonsterSchemaExtension] = self.get_monsters_by_drop(item.code)

                if len(monster_drop_list) > 0:
                    for monster in monster_drop_list:
                        monster_drop_modifier = 1 if all_max_level and monster.level < 8 else 2
                        for drop in monster.drops:
                            if drop.code == item.code:
                                min_rate = drop.rate / drop.max_quantity * monster_drop_modifier  # 3x markup for monster based drops
                                max_rate = drop.rate / drop.min_quantity * monster_drop_modifier  # 3x markup for monster based drops

                                should_break = False
                                if not drop_rate_min or min_rate < drop_rate_min:
                                    drop_rate_min = min_rate
                                    should_break = True
                                if not drop_rate_max or max_rate > drop_rate_max:
                                    drop_rate_max = max_rate
                                    should_break = True

                                if should_break:
                                    break

            if drop_rate_min and drop_rate_max:
                drop_rate_list.append(ItemDropRate(item.code, int(drop_rate_min), int(drop_rate_max)))

        return drop_rate_list

    def get_account_details(self) -> MyAccountDetails:
        return self.client.get_account_details()

    def get_account_achievements(self, account: str = None) -> List[AccountAchievementSchemaExtension]:
        return [AccountAchievementSchemaExtension(a) for a in self.client.get_account_achievements(account)]

    def get_account_achievement(self, account: str, achievement_code: str) -> Optional[AccountAchievementSchemaExtension]:
        for achievement in self.get_account_achievements(account):
            if achievement.code == achievement_code:
                return AccountAchievementSchemaExtension(achievement)
        return None

    def get_account_leaderboard(self) -> List[AccountLeaderboardSchema]:
        return self.client.get_account_leaderboard()

    def get_confining_gear_positions(self, character: CharacterSchemaExtension) -> List[str]:
        confining_gear_positions: List[str] = []
        for gear_position in game_constants.GEAR_POSITIONS:
            item_code = character.equipment.get(gear_position)
            if item_code:
                item = self.get_item(item_code)
                if item.is_confining_gear():
                    confining_gear_positions.append(gear_position)
                    break
        return confining_gear_positions

    def resolve_item_recipe(
        self,
        item_code: str,
        bank_items_map: Dict[str, int],
        quantity: int = 1,
        force_gather: bool = False,
        read_only: bool = True,
    ) -> ResolvedItemRecipe:
        if read_only:
            local_bank_items_map = bank_items_map.copy()
        else:
            local_bank_items_map = bank_items_map

        result_map_available = defaultdict(int)
        result_map_missing = defaultdict(int)
        result_map_all = defaultdict(int)

        item = self.get_item(item_code)
        craft = item.craft
        if craft:
            craft_items = craft.items
            for craft_item in craft_items:
                required_quantity = craft_item.quantity * quantity
                withdraw_quantity = 0
                if not force_gather:
                    bank_available = local_bank_items_map.get(craft_item.code, 0)
                    withdraw_quantity = min(required_quantity, bank_available)
                    if withdraw_quantity > 0:
                        result_map_available[craft_item.code] += withdraw_quantity
                        result_map_all[craft_item.code] += withdraw_quantity
                        local_bank_items_map[craft_item.code] -= withdraw_quantity

                craft_quantity = required_quantity - withdraw_quantity
                if craft_quantity > 0:
                    resolved_item_recipe = self.resolve_item_recipe(
                        item_code=craft_item.code,
                        quantity=craft_quantity,
                        force_gather=force_gather,
                        bank_items_map=local_bank_items_map,
                        read_only=False,
                    )

                    for code, qty in resolved_item_recipe.available_items.items():
                        result_map_available[code] += qty
                        result_map_all[code] += qty

                    for code, qty in resolved_item_recipe.missing_items.items():
                        result_map_missing[code] += qty
                        result_map_all[code] += qty
        else:
            origin = self.get_item_origin(item_code)
            if origin and not origin.monsters and not origin.resources and not origin.tasks and origin.npcs:
                for npc_code, npc_offer in origin.npcs.items():
                    if npc_offer.currency != 'gold':
                        required_quantity = npc_offer.price * quantity
                        withdraw_quantity = 0
                        if not force_gather:
                            bank_available = local_bank_items_map.get(npc_offer.currency, 0)
                            withdraw_quantity = min(required_quantity, bank_available)
                            if withdraw_quantity > 0:
                                result_map_available[npc_offer.currency] += withdraw_quantity
                                result_map_all[npc_offer.currency] += withdraw_quantity
                                local_bank_items_map[npc_offer.currency] -= withdraw_quantity

                        craft_quantity = required_quantity - withdraw_quantity
                        if craft_quantity > 0:
                            resolved_item_recipe = self.resolve_item_recipe(
                                item_code=npc_offer.currency,
                                quantity=craft_quantity,
                                force_gather=force_gather,
                                bank_items_map=local_bank_items_map,
                                read_only=False,
                            )

                            for code, qty in resolved_item_recipe.available_items.items():
                                result_map_available[code] += qty
                                result_map_all[code] += qty

                            for code, qty in resolved_item_recipe.missing_items.items():
                                result_map_missing[code] += qty
                                result_map_all[code] += qty
                        break
            elif quantity > 0:
                bank_available = 0  # FIXME: bank_items_map.get(item_code, 0)
                missing_quantity = max(0, quantity - bank_available)
                if missing_quantity > 0:
                    result_map_missing[item_code] += missing_quantity
                available_quantity = quantity - missing_quantity
                if available_quantity > 0:
                    result_map_available[item_code] += quantity - missing_quantity
                result_map_all[item_code] += quantity

        return ResolvedItemRecipe(
            available_items=dict(result_map_available), missing_items=dict(result_map_missing), all_items=dict(result_map_all)
        )

    def get_craftable_recipe_count(self, item_code: str, bank_items_map: Dict[str, int]) -> int:
        # First, check if we can craft at least one
        if self.resolve_item_recipe(item_code, bank_items_map, 1).missing_items:
            return 0

        # Exponential search to find an upper bound
        low, high = 0, 1
        exponential_search = self.resolve_item_recipe(item_code, bank_items_map, high)
        while exponential_search.all_items and not exponential_search.missing_items:
            low = high
            high *= 2
            exponential_search = self.resolve_item_recipe(item_code, bank_items_map, high)

        # Binary search between low and high
        while low < high:
            mid = (low + high + 1) // 2
            resolved_recipe = self.resolve_item_recipe(item_code, bank_items_map, mid)
            if resolved_recipe.missing_items:
                high = mid - 1
            else:
                low = mid

        return low

    def get_currently_craftable_items(
        self,
        character: CharacterSchemaExtension,
        item_type: str = None,
        use_task_rewards: bool = False,
        use_rare_items: bool = False,
        skill_filter: List[str] = None,
    ) -> List[CraftableItem]:
        result: List[CraftableItem] = []
        bank_items_map = self.get_bank_items_map()
        skill_map = self.get_skill_map([character])
        task_items: List[str] = self.get_task_rewards()
        rare_items = self.get_rare_drop_codes()
        level_cap = 25

        eligible_items: List[ItemSchemaExtension] = []

        item_iterator = self.get_items_by_type(item_type) if item_type else self.get_all_items()
        for item in item_iterator:
            if item.craft:
                skill = str(item.craft.skill)
                if skill_filter is None or skill in skill_filter:
                    character_skill_level = skill_map.get(skill, 1)
                    if character_skill_level >= item.craft.level and level_cap > item.craft.level:
                        eligible_items.append(item)

        while True:
            temp_result: List[CraftableItem] = []
            for item in eligible_items:
                qty = 1
                last_qty = 0
                available_items = {}

                while True:
                    resolved_recipe = self.resolve_item_recipe(item_code=item.code, bank_items_map=bank_items_map, quantity=qty)

                    if not resolved_recipe.missing_items:
                        if (use_task_rewards or all(elem not in resolved_recipe.all_items for elem in task_items)) and (
                            use_rare_items or all(elem not in resolved_recipe.all_items for elem in rare_items)
                        ):
                            last_qty = qty
                            available_items = resolved_recipe.available_items
                            qty += 1
                        else:
                            break
                    else:
                        break

                if last_qty > 0:
                    temp_result.append(CraftableItem(item.code, last_qty, item.level, available_items))

            if len(temp_result) > 0:
                top_item = min(temp_result, key=lambda x: (-x.quantity, x.level))
                result.append(top_item)
                for part_code, part_qty in top_item.required_parts.items():
                    bank_items_map[part_code] -= part_qty
            else:
                break

        return result

    def reserve_equipment(
        self,
        character: CharacterSchemaExtension,
        equipment: Dict[str, str] = None,
        utilities: Dict[str, int] = None,
        consumables: Dict[str, int] = None,
        reservation_id: str = None,
    ) -> str:
        if reservation_id is None:
            reservation_id = Task.generate_task_id()

        equipment_map: Dict[str, int] = defaultdict(int)

        if consumables is not None and len(consumables) > 0:
            for item_code, quantity in consumables.items():
                equipment_map[item_code] += quantity

        if equipment is not None and len(equipment) > 0:
            for item_code in equipment.values():
                equipment_map[item_code] += 1

        if utilities is not None and len(utilities) > 0:
            for item_code, quantity in utilities.items():
                equipment_map[item_code] += quantity

        for item_code, quantity in character.equipped_items.items():
            equipment_map[item_code] -= quantity

        for item_code, quantity in character.inventory_map.items():
            if item_code in equipment_map:
                equipment_map[item_code] -= quantity
                logger.info(f"Reduced quantity to reserve of item {item_code} by {quantity} based on character's inventory.")

        self.add_bank_reservations(reservation_id, equipment_map, character.name)

        return reservation_id

    @cache
    def is_event_content(self, content_code: str):
        all_events: List[EventSchema] = self.get_all_events()
        for event in all_events:
            if event.content.code == content_code:
                return True
        return False

    @cache
    def is_event_exclusive_content(self, item_code: str) -> Tuple[bool, Optional[str]]:
        all_events: List[EventSchema] = self.get_all_events()
        for event in all_events:
            if event.content.type == 'resource':
                res: ResourceSchemaExtension = self.get_resource(event.content.code)
                if res:
                    for drop in res.drops:
                        if drop.code == item_code:
                            resources = self.get_resources_by_drop(item_code)
                            return len(resources) == 1, event.code
            elif event.content.type == 'monster':
                mob: Optional[MonsterSchemaExtension] = self.get_monster(event.content.code)
                if mob:
                    for drop in mob.drops:
                        if drop.code == item_code:
                            monsters: List[MonsterSchemaExtension] = self.get_monsters_by_drop(item_code)
                            return len(monsters) == 1, event.code

        return False, None

    @cache
    def is_event_resource_drop(self, item_code: str):
        all_events: List[EventSchema] = self.get_all_events()
        for event in all_events:
            if event.content.type == 'resource':
                res: ResourceSchemaExtension = self.get_resource(event.content.code)
                if res:
                    for drop in res.drops:
                        if drop.code == item_code:
                            return True
        return False

    def create_character(self, idx, character_name) -> Optional[CharacterSchemaExtension]:
        skins = ['men1', 'men2', 'men3', 'women1', 'women2', 'women3']
        skin = skins[idx % 6]
        return CharacterSchemaExtension(self.client.create_character(character_name, skin))

    def resolve_buy_order(self, basket: ShoppingBasket) -> int:
        required_gold = 0
        quantity = 0
        item_code = ''
        if basket.order_id:
            sell_order = self.get_ge_order(basket.order_id)
            item_code = sell_order.code
            if basket.quantity is not None and basket.quantity > 0:
                quantity = min(sell_order.quantity, basket.quantity)
            else:
                quantity = sell_order.quantity
            required_gold = sell_order.price * quantity
        elif basket.item:
            item_code = basket.item
            sell_orders: List[GEOrderSchema] = self.get_ge_sell_orders(basket.item)
            if basket.quantity is not None and basket.quantity > 0:
                quantity = basket.quantity
            else:
                quantity = 1
            total_price, quantity = self.calculate_total_sell_price(sell_orders, quantity)
            required_gold = total_price

        logger.info(f'Resolved shopping basket to required gold={required_gold} for quantity={quantity} of item={item_code}.')

        return required_gold

    @staticmethod
    def calculate_total_sell_price(ge_items: List[GEOrderSchema], quantity: int) -> Tuple[int, int]:
        sorted_ge_items = sorted(ge_items, key=lambda i: i.price)
        total_price = 0
        quantity_available = 0
        quantity_remaining = quantity
        for item in sorted_ge_items:
            if quantity_remaining <= 0:
                break

            quantity_to_buy = min(quantity_remaining, item.quantity)
            total_price += quantity_to_buy * item.price
            quantity_remaining -= quantity_to_buy
            quantity_available += quantity_to_buy

        return total_price, quantity_available

    def get_characters_by_param(
        self,
        parameters: List[str] = None,
        characters: List[CharacterSchemaExtension] = None,
    ) -> List[CharacterSchemaExtension]:
        parameters = parameters if parameters else []
        character_details: List[CharacterSchemaExtension] = characters or self.get_all_character_details()
        return_characters: Set[CharacterSchemaExtension] = set()
        if 'all' in parameters:
            return_characters.update(character_details)
        else:
            for parameter in parameters:
                if bool(re.fullmatch(r'[1-4]-[2-5]', parameter)):
                    indices = parameter.split('-')
                    start_index = min(5, max(0, int(indices[0]) - 1))
                    end_index = min(5, max(0, int(indices[-1])))
                    for idx in range(start_index, end_index):
                        return_characters.add(character_details[idx])
                elif parameter.isnumeric():
                    idx = int(parameter)
                    character_index = min(5, max(0, idx - 1))
                    return_characters.add(character_details[character_index])
                else:
                    for character in character_details:
                        if character.name == parameter:
                            return_characters.add(character)

        return sorted(list(return_characters), key=lambda c: c.name)

    def get_skill_map(self, characters: List[CharacterSchemaExtension] = None) -> Dict[str, int]:
        characters = characters if characters else self.get_all_character_details()
        skill_map: Dict[str, int] = defaultdict(int)
        for c in characters:
            for skill_name, skill in c.skills.items():
                skill_map[str(skill_name)] = max(skill.level, skill_map[str(skill_name)])
        return skill_map

    def get_disposal_quantity(
        self, item_code, available_tools, available_items_map, min_character_level_threshold, bank_quantity, skill_filter, skill_map
    ):
        thresholds = {'weapon': 5, 'boots': 5, 'helmet': 5, 'shield': 5, 'leg_armor': 5, 'body_armor': 5, 'amulet': 5, 'ring': 10}

        available_tools = available_tools if available_tools else self.get_available_tools(available_items_map)
        skill_map = skill_map if skill_map else self.get_skill_map()

        item = self.get_item(item_code)

        if item.is_recyclable and item.type in thresholds.keys():
            if item.subtype == 'tool':
                threshold = self.calculate_tool_threshold(item, available_tools)
            elif item.level < min_character_level_threshold:
                threshold = 0
            else:
                threshold = thresholds.get(item.type)

            global_quantity = available_items_map[item.code]
            if global_quantity > threshold:
                dispose_quantity = min(global_quantity - threshold, bank_quantity)
                if item.craft:
                    skill = str(item.craft.skill)
                    skill_level = item.craft.level
                    if not skill_filter or skill == skill_filter:
                        if skill_map.get(skill, 1) >= skill_level:
                            return dispose_quantity
        return 0

    def get_available_tools(self, available_items_map: Dict[str, int]):
        available_tools_map: Dict[str, Dict[int, int]] = defaultdict(lambda: defaultdict(int))
        for item_code, item_quantity in available_items_map.items():
            item = self.get_item(item_code)
            if item.subtype == 'tool':
                for skill in game_constants.SKILLS:
                    if item.item_effects.get(skill, 0) < 0:
                        available_tools_map[skill][item.level] += item_quantity
                        break
        return available_tools_map

    @staticmethod
    def calculate_tool_threshold(item: ItemSchemaExtension, available_tools: Dict[str, Dict[int, int]]) -> int:
        threshold = 5
        target_skill: Optional[str] = None
        for skill in game_constants.SKILLS:
            if item.item_effects.get(skill, 0) < 0:
                target_skill = skill
                break

        if target_skill:
            skill_tools = available_tools[target_skill]
            better_tool_count = 0
            for tool_level, tool_qty in skill_tools.items():
                if tool_level > item.level:
                    better_tool_count += tool_qty

            threshold = max(5 - better_tool_count, 0)

        return threshold

    def get_global_quantity_map(
        self, bank_items_map: Dict[str, int] = None, all_characters_inventory_map: Dict[str, int] = None
    ) -> Dict[str, int]:
        available_items_map = Counter()
        if bank_items_map and all_characters_inventory_map:
            available_items_map.update(bank_items_map)
            available_items_map.update(all_characters_inventory_map)
        elif bank_items_map and not all_characters_inventory_map:
            available_items_map.update(bank_items_map)
            available_items_map.update(self.get_all_characters_inventory_map())
        elif not bank_items_map and all_characters_inventory_map:
            available_items_map.update(all_characters_inventory_map)
            available_items_map.update(self.get_bank_items_map(ignore_reservations=True))
        else:
            with ThreadPoolExecutor() as executor:
                future_bank_items = executor.submit(self.get_bank_items_map, task_id=None, ignore_reservations=True)
                future_inventory = executor.submit(self.get_all_characters_inventory_map)

                bank_items_map = future_bank_items.result()
                all_characters_inventory_map = future_inventory.result()

            available_items_map = Counter(bank_items_map)
            available_items_map.update(all_characters_inventory_map)

        return available_items_map

    def get_recyclable_ge_orders(self) -> List[GEOrderSchema]:
        result: List[GEOrderSchema] = []
        ge_sell_orders: List[GEOrderSchema] = self.get_ge_sell_orders()
        for order in ge_sell_orders:
            item = self.get_item(order.code)
            if item.is_recyclable and self.is_recycling_candidate(order.price):
                result.append(order)
        return result

    @staticmethod
    def is_recycling_candidate(price: int):
        return price <= game_constants.GE_RECYCLING_THRESHOLD

    def get_highest_task_achievement(self, account: str) -> AccountAchievementSchemaExtension:
        achievements = filter(
            lambda achievement: all(objective.type == AchievementType.TASK for objective in achievement.objectives),
            self.get_account_achievements(account),
        )
        return max(achievements, key=lambda a: a.total)

    def get_task(self, task_code: str) -> Optional[TaskFullSchema]:
        all_tasks_map = self.get_all_tasks_map()
        return all_tasks_map.get(task_code)

    @cache
    def get_all_tasks_map(self) -> Dict[str, TaskFullSchema]:
        all_tasks: List[TaskFullSchema] = self.client.get_all_tasks()
        return {task.code: task for task in all_tasks}

    # Monsters

    def get_monster(self, monster_code: str) -> Optional[MonsterSchemaExtension]:
        return self.__monster_service.get_monster(monster_code)

    def get_monsters_by_drop(self, drop_code: str) -> List[MonsterSchemaExtension]:
        return self.__monster_service.get_monsters_by_drop(drop_code)

    def get_all_monsters(self) -> Iterator[MonsterSchemaExtension]:
        yield from self.__monster_service.get_all_monsters()

    def get_monsters_by_level(self, min_level: int = 1, max_level: int = 55) -> List[MonsterSchemaExtension]:
        return self.__monster_service.get_monsters_by_level(min_level, max_level)

    # Items

    def get_item(self, item_code: str) -> Optional[ItemSchemaExtension]:
        return self.__item_service.get_item_by_code(item_code)

    def get_item_types(self) -> Dict[str, str]:
        return self.__item_service.get_item_types()

    def get_unprocessed_food(self) -> Set[ItemSchemaExtension]:
        return self.__item_service.get_unprocessed_food()

    def get_processed_food(self) -> Set[ItemSchemaExtension]:
        return self.__item_service.get_processed_food()

    def get_processed_food_by_level(self, level: int, highest_level_first: bool = False) -> List[ItemSchemaExtension]:
        consumables = [c for c in self.get_processed_food() if c.level <= level]
        return sorted(consumables, key=lambda c: c.level, reverse=highest_level_first)

    def get_items_by_type(self, item_type: str, max_level: int = 50) -> Iterator[ItemSchemaExtension]:
        for item in self.__item_service.get_items_by_type(item_type):
            if item.level <= max_level:
                yield item

    def get_all_items(self, min_level: int = 1, max_level: int = 50) -> Iterator[ItemSchemaExtension]:
        for item in self.__item_service.get_all_items():
            if min_level <= item.level <= max_level:
                yield item

    def get_tools(self, skill: str, max_level: int = 50, character: CharacterSchemaExtension = None) -> Iterator[ItemSchemaExtension]:
        yield from sorted(self.__item_service.get_tools(skill, max_level, character), key=lambda x: (-x.level, x.item_effects[skill]))

    @cache
    def get_task_rewards(self) -> List[str]:
        return [i.code for i in self.get_all_items() if i.subtype == 'task']

    @cache
    def get_uncraftable_gear(self) -> List[str]:
        gear_positions: Set[str] = {s.rstrip('123') for s in game_constants.GEAR_POSITIONS}
        return [i.code for i in self.get_all_items() if i.type in gear_positions and not i.craft]

    def get_item_origin(self, item_code: str) -> Optional[ItemOrigin]:
        return self.__item_origin_service.get_item_origin(item_code)

    def get_item_products(self, item_code: str) -> List[ItemSchemaExtension]:
        return self.__item_origin_service.get_item_products(item_code)

    def is_item_rare_drop(self, item_code: str) -> bool:
        return self.__item_origin_service.is_rare_drop(item_code)

    def get_rare_drop_codes(self) -> Set[str]:
        return self.__item_origin_service.get_rare_drop_codes()

    # NPCs

    def get_all_npcs(self) -> Iterator[NPCSchemaExtension]:
        return self.__npc_service.get_all_npcs()

    def get_all_npc_items(self) -> Dict[str, List[str]]:
        return self.__npc_service.get_all_npc_items()

    def get_npc(self, npc_code: str) -> NPCSchemaExtension:
        return self.__npc_service.get_npc(npc_code)

    def get_npcs_by_item_code(self, item_code: str) -> List[NPCSchemaExtension]:
        return self.__npc_service.get_npcs_by_item_code(item_code)

    # Resources

    def get_resource(self, resource_name: str) -> Optional[ResourceSchemaExtension]:
        return self.__resource_service.get_resource(resource_name)

    def get_resources_by_level(
        self, min_level: int = 1, max_level: int = 50, skill: str = None, include_event_resources: bool = True
    ) -> List[ResourceSchemaExtension]:
        return sorted(
            filter(
                lambda r: (not skill or r.skill == skill) and (include_event_resources or not r.is_event_drop),
                self.__resource_service.get_resources_by_level(min_level, max_level),
            ),
            key=lambda r: r.level,
            reverse=True,
        )

    def get_resources_by_skill(self, skill: GatheringSkill | str) -> List[ResourceSchemaExtension]:
        return self.__resource_service.get_resources_by_skill(skill)

    def get_resources_by_drop(self, drop_code: str) -> List[ResourceSchemaExtension]:
        return self.__resource_service.get_resources_by_drop(drop_code)

    # Others

    def get_active_events(self) -> List[ActiveEventSchema]:
        now = datetime.now(UTC)
        return [e for e in self.client.get_active_events() if e.expiration > now]

    def get_all_events(self) -> List[EventSchema]:
        return self.client.get_all_events()

    def get_event_by_content_if_active(self, content_code: str) -> Optional[ActiveEventSchema]:
        for active_event in self.get_active_events():
            if active_event.map.interactions.content.code == content_code:
                return active_event
        return None

    def get_quickest_recyclable_items(
        self,
        item_count: int = 1,
        min_level: int = 1,
        max_level: int = 50,
        skill_filter: List[str] = None,
        ignore_bank_reservations: bool = False,
        include_task_drops: bool = False,
        include_event_drops: bool = False,
    ) -> List[RecyclableItem]:
        result_list: List[RecyclableItem] = []
        bank_items_map = self.get_bank_items_map(ignore_reservations=ignore_bank_reservations)
        for item in self.get_all_items(min_level=min_level, max_level=max_level):
            if item.craft and (skill_filter is None or str(item.craft.skill) in skill_filter):
                resolved_recipe = self.resolve_item_recipe(item.code, bank_items_map, item_count, read_only=False)
                total_drop_rate = 0
                for missing_item_code, missing_item_count in resolved_recipe.missing_items.items():
                    missing_item_origin = self.get_item_origin(missing_item_code)
                    if missing_item_origin:
                        min_drop_rate = missing_item_origin.min_drop_rate(
                            include_task_drops=include_task_drops,
                            include_event_drops=include_event_drops,
                        )
                    else:
                        min_drop_rate = None
                    if min_drop_rate is None:
                        total_drop_rate = None
                        break
                    else:
                        total_drop_rate += missing_item_count * min_drop_rate

                if total_drop_rate:
                    result_list.append(
                        RecyclableItem(
                            item_code=item.code,
                            item_level=item.level,
                            quantity=item_count,
                            total_drop_rate=total_drop_rate,
                            missing_items=resolved_recipe.missing_items,
                        )
                    )

        sorted_items = sorted(result_list, key=lambda x: x.total_drop_rate)
        return sorted_items

    def resolve_recipes(
        self,
        recipe_map: Dict[str, int],
        bank_items_map: Dict[str, int] = None,
        context: ExecutionContext = None,
    ) -> Tuple[ResolvedItemRecipe, Dict[str, int]]:
        bank_items_map = bank_items_map or self.get_bank_items_map(context=context)
        immediately_craftable: Dict[str, int] = {}

        resolved_recipes: List[ResolvedItemRecipeDetails] = []
        for item_code, item_quantity in recipe_map.items():
            resolved_recipe = self.resolve_item_recipe(item_code, bank_items_map, item_quantity, read_only=False)
            if not resolved_recipe.missing_items:
                immediately_craftable[item_code] = item_quantity
            elif resolved_recipe.available_items:
                craftable_count = self.get_craftable_recipe_count(item_code, resolved_recipe.available_items)
                if craftable_count > 0:
                    immediately_craftable[item_code] = craftable_count
            resolved_recipes.append(ResolvedItemRecipeDetails(item_code, item_quantity, resolved_recipe))

        combined_resolved_recipe = ResolvedItemRecipe(defaultdict(int), defaultdict(int), defaultdict(int))
        for recipe in resolved_recipes:
            for code, qty in recipe.resolved_recipe.available_items.items():
                combined_resolved_recipe.available_items[code] += qty

            for code, qty in recipe.resolved_recipe.missing_items.items():
                combined_resolved_recipe.missing_items[code] += qty

            for code, qty in recipe.resolved_recipe.all_items.items():
                combined_resolved_recipe.all_items[code] += qty

        combined_resolved_recipe.available_items = dict(combined_resolved_recipe.available_items)
        combined_resolved_recipe.missing_items = dict(combined_resolved_recipe.missing_items)
        combined_resolved_recipe.all_items = dict(combined_resolved_recipe.all_items)
        return combined_resolved_recipe, immediately_craftable

    def get_craftable_items(
        self,
        crafting_skill: str,
        min_level: int = 1,
        max_level: int = None,
        allow_task_parts: bool = False,
        allow_event_parts: bool = False,
        allow_boss_parts: bool = False,
    ) -> List[ItemSchemaExtension]:
        result_dicts: List[dict] = []
        for item in self.get_all_items(min_level, max_level):
            if item.craft and item.craft.skill == crafting_skill and (crafting_skill not in RECYCLING_SKILLS or item.is_recyclable):
                resolved_recipe = self.resolve_item_recipe(item_code=item.code, bank_items_map={})
                valid_item = True
                if not allow_task_parts or not allow_event_parts or not allow_boss_parts:
                    for part_code in resolved_recipe.all_items.keys():
                        part_origin = self.get_item_origin(part_code)
                        if part_origin:
                            if not allow_task_parts and part_origin.is_task_exclusive():
                                valid_item = False
                                break
                            if not allow_event_parts and part_origin.is_event_exclusive():
                                valid_item = False
                                break
                            if not allow_boss_parts and part_origin.is_boss_exclusive():
                                valid_item = False
                                break
                if valid_item:
                    drop_rates = self.get_drop_rate(item_code=item.code)
                    min_drop_rate = 0
                    for drop_rate in drop_rates:
                        q = resolved_recipe.all_items[drop_rate.item_code]
                        min_drop_rate += q * drop_rate.drop_rate_min

                    result_dicts.append({'item': item, 'drop_rate': min_drop_rate})

        results: List[ItemSchemaExtension] = []
        if result_dicts:
            for result in sorted(result_dicts, key=lambda x: (-x['item'].level, x['drop_rate'])):
                results.append(result['item'])

        return results

    def estimate_fight_times(
        self,
        task: Task = None,
        ttl: int = 1,
        monster: MonsterSchemaExtension = None,
        character: CharacterSchemaExtension = None,
    ) -> int:
        if task and task.until:
            if task.until.drop_count:
                quantity = task.until.drop_count - task.until.progress
                if monster:
                    for drops in monster.drops:
                        if drops.code == task.until.drop_item:
                            return max(ttl, drops.rate * quantity)
                else:
                    return max(ttl, 10 * quantity)
            elif task.until.date_time:
                return int((task.until.date_time - datetime.now(UTC)).total_seconds()) // 30
            elif task.until.achievement_code and character:
                achievement = self.get_account_achievement(character.account, task.until.achievement_code)
                if achievement and not achievement.completed_at:
                    remaining = achievement.total - achievement.current

                    monster_code = task.extra.get('monster')
                    if monster_code:
                        for objective in achievement.objectives:
                            if objective.type == AchievementType.COMBAT_DROP:
                                monster = self.get_monster(monster_code)
                                if monster:
                                    for drop in monster.drops:
                                        if drop.code == objective.target:
                                            return min(100, remaining * drop.rate)

                    return min(100, remaining)
        return ttl

    def get_best_wisdom_gear_by_level(self, max_level: int) -> Dict[str, List[ItemSchemaExtension]]:
        wisdom_map: Dict[str, List[ItemSchemaExtension]] = {}
        for item in self.get_all_items(max_level=max_level):
            wisdom_value = item.wisdom_value()
            if wisdom_value:
                if item.type not in wisdom_map:
                    wisdom_map[item.type] = [item]
                elif wisdom_value > wisdom_map[item.type][0].wisdom_value():
                    wisdom_map[item.type] = [item]
                elif wisdom_value == wisdom_map[item.type][0].wisdom_value():
                    wisdom_map[item.type].append(item)
        return wisdom_map

    @staticmethod
    def get_xp_map() -> Dict[int, int]:
        return {
            1: 150,
            2: 250,
            3: 350,
            4: 450,
            5: 700,
            6: 950,
            7: 1200,
            8: 1450,
            9: 1700,
            10: 2100,
            11: 2500,
            12: 2900,
            13: 3300,
            14: 3700,
            15: 4400,
            16: 5100,
            17: 5800,
            18: 6500,
            19: 7200,
            20: 8200,
            21: 9200,
            22: 10200,
            23: 11200,
            24: 12200,
            25: 13400,
            26: 14600,
            27: 15800,
            28: 17000,
            29: 18200,
            30: 19700,
            31: 21200,
            32: 22700,
            33: 24200,
            34: 25700,
            35: 27500,
            36: 29300,
            37: 31100,
            38: 32900,
            39: 34700,
            40: 36500,
            41: 38600,
            42: 40700,
            43: 42800,
            44: 44900,
            45: 47000,
            46: 48800,
            47: 50600,
            48: 52400,
            49: 54200,
            50: 56000,
        }

    def get_missing_xp(self, skill: CharacterSkill, target_level: int):
        xp_map = self.get_xp_map()
        total_xp = skill.max_xp - skill.xp
        for level in range(skill.level + 1, target_level):
            total_xp += xp_map[level]
        return total_xp

    def get_teleport_item_codes(self) -> List[str]:
        return self.__item_service.get_teleport_item_codes()

    def get_distance_between(self, current_map: MapSchemaExtension, destination_map: MapSchemaExtension):
        if not current_map:
            current_map = self.get_map(0, 0)
        elif current_map.map_id == destination_map.map_id:
            return 0

        distance = 0
        if destination_map.cluster_id == current_map.cluster_id:
            distance = abs(destination_map.x - current_map.x) + abs(destination_map.y - current_map.y)
        else:
            route = self.get_route(from_cluster=current_map.cluster_id, to_cluster=destination_map.cluster_id)
            if route:
                for idx in range(len(route.gateways)):
                    gateway = route.gateways[idx]
                    if idx == 0:
                        distance = abs(gateway.x - current_map.x) + abs(gateway.y - current_map.y)
                    else:
                        previous_gateway = route.gateways[idx - 1]
                        distance += abs(gateway.x - previous_gateway.interactions.transition.x) + abs(
                            gateway.y - previous_gateway.interactions.transition.y
                        )
                last_gateway = route.gateways[-1]
                distance += abs(destination_map.x - last_gateway.interactions.transition.x) + abs(
                    destination_map.y - last_gateway.interactions.transition.y
                )
                distance += len(route.gateways)
            else:
                content_code = ''
                if destination_map.interactions and destination_map.interactions.content:
                    content_code = f' ({destination_map.interactions.content.code})'
                logger.error(f'Could not find route for from_map_id={current_map.map_id}, to_map_id={destination_map.map_id} {content_code}')
                distance += 10_000
        return distance

    def get_cost_between(self, current_map: MapSchemaExtension, location: MapSchemaExtension):
        if not current_map:
            current_map = self.get_map(0, 0)
        elif current_map.map_id == location.map_id:
            return 0

        cost = 0
        if location.cluster_id != current_map.cluster_id:
            route = self.get_route(from_cluster=current_map.cluster_id, to_cluster=location.cluster_id)
            for gw in route.gateways:
                for condition in gw.interactions.transition.conditions:
                    if condition.code == 'gold':
                        cost += int(condition.value)

        return cost

    def format_achievement_process(self, achievements_by_type, bank_items_map):
        lines = []
        for achievement_type in sorted(achievements_by_type):
            achievements = achievements_by_type[achievement_type]
            lines.append(f'*{escape_string(achievement_type)}*')
            for achievement in achievements:
                lines.append(f'└ _{escape_string(achievement.code)}_ for {achievement.points} pts\\.')
                for objective in achievement.objectives:
                    progress = objective.progress / objective.total * 100
                    progress_emoji = ' ✅' if objective.progress == objective.total else ''
                    progress_str = f'({progress:.1f}%){progress_emoji}'
                    if objective.target:
                        achievement_str = escape_string(
                            f'{format_long_number(objective.total)}x {objective.target}: {objective.progress}/{objective.total} {progress_str}'
                        )
                    elif achievement_type in (AchievementType.COMBAT_LEVEL, AchievementType.RECYCLING, AchievementType.TASK):
                        achievement_str = escape_string(f'{achievement.total} {progress_str}')
                    else:
                        achievement_str = escape_string(
                            f'{achievement.description.removesuffix(".").replace(" 000", "'000")}: {achievement.current}/{achievement.total} '
                            f'{progress_str}'
                        )

                    event_required = self.__is_event_required_objective(objective, bank_items_map)
                    achievement_format = achievement_str if achievement.total_progress else f'_{achievement_str}_'
                    achievement_format += ' ⚡️' if event_required else ''
                    lines.append(f'└─ {achievement_format}')
                # achievement_efforts = self.__estimate_achievement_efforts(achievement, bank_items_map)
                # if achievement_efforts:
                #     lines.append(f' └ {escape_string(achievement_efforts)}')

            lines.append('')
        return lines

    def __estimate_achievement_efforts(self, achievement: AccountAchievementSchemaExtension, bank_items_map: Dict[str, int]) -> str:
        results = []
        for objective in achievement.objectives:
            remaining_qty = objective.total - objective.progress
            efforts_map = defaultdict(list)
            match objective.type:
                case AchievementType.COMBAT_DROP:
                    origin = self.get_item_origin(objective.target)
                    for monster_code, monster_drop in origin.monsters.items():
                        efforts_map[objective.target].append(f'~{format_long_number(monster_drop.drop_rate * remaining_qty)}x {monster_code}')

                case AchievementType.CRAFTING:
                    resolved_recipe = self.resolve_item_recipe(
                        item_code=objective.target,
                        bank_items_map=bank_items_map,
                        quantity=remaining_qty,
                    )
                    if resolved_recipe.all_items:
                        for item_code, item_qty in resolved_recipe.missing_items.items():
                            origin = self.get_item_origin(item_code)
                            for monster_code, monster_drop in origin.monsters.items():
                                efforts_map[item_code].append(f'~{format_long_number(monster_drop.drop_rate * item_qty)}x {monster_code}')

                            for resource_code, resource_drop in origin.resources.items():
                                efforts_map[item_code].append(f'~{format_long_number(resource_drop.drop_rate * item_qty)}x {resource_code}')

                case AchievementType.GATHERING:
                    origin = self.get_item_origin(objective.target)
                    for resource_code, resource_drop in origin.resources.items():
                        if resource_drop.drop_rate > 1:
                            efforts_map[objective.target].append(
                                f'~{format_long_number(resource_drop.drop_rate * remaining_qty)}x {resource_code}'
                            )

                case AchievementType.USE:
                    resolved_recipe = self.resolve_item_recipe(
                        item_code=objective.target,
                        bank_items_map=bank_items_map,
                        quantity=remaining_qty,
                    )
                    if resolved_recipe.all_items:
                        for item_code, item_qty in resolved_recipe.missing_items.items():
                            origin = self.get_item_origin(item_code)
                            for monster_code, monster_drop in origin.monsters.items():
                                efforts_map[item_code].append(f'~{format_long_number(monster_drop.drop_rate * item_qty)}x {monster_code}')

                            for resource_code, resource_drop in origin.resources.items():
                                efforts_map[item_code].append(f'~{format_long_number(resource_drop.drop_rate * item_qty)}x {resource_code}')

                            for npc_code, npc_offer in origin.npcs.items():
                                efforts_map[item_code].append(f'{format_long_number(npc_offer.price * remaining_qty)}x {npc_offer.currency}')

                    else:
                        origin = self.get_item_origin(objective.target)
                        for npc_code, npc_offer in origin.npcs.items():
                            efforts_map[npc_code].append(f'{format_long_number(npc_offer.price * remaining_qty)}x {npc_offer.currency}')

            parts: List[str] = []
            for alternatives in efforts_map.values():
                parts.append(' or '.join(alternatives))

            results.append(' and '.join(parts))
        return '\n'.join(results)

    def __is_event_required(self, achievement: AccountAchievementSchemaExtension, bank_items_map: Dict[str, int]):
        return any(self.__is_event_required_objective(o, bank_items_map) for o in achievement.objectives)

    def __is_event_required_objective(self, objective: AccountAchievementObjectiveSchema, bank_items_map: Dict[str, int]):
        result = False
        match objective.type:
            case AchievementType.COMBAT_DROP:
                origin = self.get_item_origin(objective.target)
                result = origin.is_event_exclusive()
            case AchievementType.COMBAT_KILL:
                monster = self.get_monster(objective.target)
                result = monster.is_event_monster
            case AchievementType.CRAFTING:
                resolved_recipe = self.resolve_item_recipe(
                    item_code=objective.target,
                    bank_items_map=bank_items_map,
                    quantity=objective.total - objective.progress,
                )
                for item_code in resolved_recipe.missing_items:
                    item_origin = self.get_item_origin(item_code)
                    if item_origin.is_event_exclusive():
                        result = True
                        break
            case AchievementType.GATHERING:
                origin = self.get_item_origin(objective.target)
                result = origin.is_event_exclusive()
            case AchievementType.USE:
                resolved_recipe = self.resolve_item_recipe(
                    item_code=objective.target,
                    bank_items_map=bank_items_map,
                    quantity=objective.total - objective.progress,
                )
                for item_code in resolved_recipe.missing_items:
                    item_origin = self.get_item_origin(item_code)
                    if item_origin.is_event_exclusive():
                        result = True
                        break

        return result

    def perform_health_check(self, all_character_details: List[CharacterSchemaExtension]) -> Tuple[Optional[str], Set[str]]:
        character_messages = []
        now = datetime.now(UTC)
        one_hour_ago = now - timedelta(minutes=15)
        bank_items_map: Dict[str, int] = {}
        restart_characters = set()
        any_cooking_position, any_fishing_position = self.check_positions(all_character_details)
        max_potential_healing_capacity = 0
        for character in all_character_details:
            logs: List[LogLine] = self.__logs_table.get_logs(character.name, one_hour_ago, now)

            character_rest_counter = Counter()
            for log in logs:
                if log.action == LogType.REST:
                    if log.cooldown > REST_THRESHOLD_SECONDS:
                        character_rest_counter[log.cooldown] += 1

            if character_rest_counter.total() > 1:
                total_percent = 0
                for percentage, count in character_rest_counter.items():
                    total_percent += percentage * count

                if not bank_items_map:
                    bank_items_map = self.get_bank_items_map()

                available_healing_capacity, potential_healing_capacity = self.get_healing_capacity(bank_items_map, character.level)
                if not available_healing_capacity:
                    if potential_healing_capacity > 10_000:
                        if not any_cooking_position:
                            max_potential_healing_capacity = max(max_potential_healing_capacity, potential_healing_capacity)
                            character_messages.append(
                                f'🍽️ {character.name} rested a total of {character_rest_counter.total()} times '
                                f'over the past 15m to heal {total_percent}% of their HP. '
                            )

                            if RESTART_COOK_UPON_EMPTY_HEALING_CAPACITY:
                                cook = max(all_character_details, key=lambda c: c.cooking_level)
                                restart_characters.add(cook.name)
                    else:
                        if not any_cooking_position and not any_fishing_position:
                            character_messages.append(
                                f'⚠️ {character.name} rested a total of {character_rest_counter.total()} times '
                                f'over the past 15m to heal {total_percent}% of their HP. '
                                f'There is neither processed nor unprocessed food available. '
                            )
                            if RESTART_FISHER_UPON_EMPTY_HEALING_CAPACITY:
                                fisher = max(all_character_details, key=lambda c: c.fishing_level)
                                restart_characters.add(fisher.name)

        if max_potential_healing_capacity:
            character_messages.append(
                f'\nCooking unprocessed food would yield {format_long_number(max_potential_healing_capacity)} healing capacity ❤️‍🩹.'
            )

        if character_messages:
            message = '\n'.join(character_messages)
            logger.info(message)
            return message, restart_characters
        else:
            return None, restart_characters

    def calculate_craft_recipe_time(
        self,
        recipes: Dict[str, int],
        character_inventory_capacity: int = 100,
        bank_items_map: Dict[str, int] = None,
    ):

        if not bank_items_map:
            bank_items_map = self.get_bank_items_map()

        total_seconds = 0
        for item_code, quantity in recipes.items():
            item_seconds = 0
            item = self.get_item(item_code)

            if item:
                if item.craft:
                    for craft in item.craft.items:
                        part_seconds = self.calculate_craft_recipe_time(
                            {craft.code: craft.quantity},
                            character_inventory_capacity,
                            bank_items_map,
                        )

                        # if not part_seconds:
                        turns = math.ceil(quantity * item.craft.quantity * craft.quantity / character_inventory_capacity)

                        bank_map = self.get_closest_location('workshop', str(item.craft.skill))
                        workshop_map = self.get_closest_location('bank')
                        distance_tiles = self.get_distance_between(bank_map, workshop_map)
                        walk_time = turns * distance_tiles * 2 * 5
                        withdraw_time = 3
                        craft_time = quantity * item.craft.quantity * 5

                        part_seconds += walk_time + withdraw_time + craft_time
                        item_seconds += part_seconds

            total_seconds += item_seconds

            # if item_seconds:
            #    logger.debug(f'{quantity}x {item_code} takes {item_seconds} seconds to craft.')
        return total_seconds

    def get_healing_capacity(self, item_quantity_map: Dict[str, int], max_level: int = None) -> Tuple[int, int]:
        if not max_level:
            max_level = MAX_LEVEL
        available_healing_capacity = 0
        craftable_healing_capacity = 0

        for item in self.get_processed_food():
            if item.level <= max_level and item.code not in ['corrupted_fruit', 'maple_syrup']:
                item_qty = item_quantity_map.get(item.code, 0)
                available_healing_capacity += item_qty * item.heal_value()
                craftable_qty = self.get_craftable_recipe_count(item.code, item_quantity_map)
                craftable_healing_capacity += craftable_qty * item.heal_value()
                if craftable_qty:
                    logger.info(
                        f'Crafting {craftable_qty}x {item.code} would yield {craftable_qty * item.heal_value()} additional healing capacity.'
                    )

        return available_healing_capacity, craftable_healing_capacity

    def check_positions(self, all_character_details) -> Tuple[bool, bool]:
        any_cooking_position = False
        any_fishing_position = False
        for character in all_character_details:
            current_map = self.get_map_by_id(character.map_id)
            if current_map.interactions and current_map.interactions.content:
                if current_map.interactions.content.type == 'resource':
                    resource = self.get_resource(current_map.interactions.content.code)
                    if resource and resource.skill == GatheringSkill.FISHING:
                        any_fishing_position = True
                elif current_map.interactions.content.type == MapContentType.WORKSHOP and current_map.interactions.content.code == 'cooking':
                    any_cooking_position = True
        return any_cooking_position, any_fishing_position

    def get_missing_recipes(self, recipes: Counter[str], sets: int = 1, global_quantity_map: Dict[str, int] = None):
        global_quantity_map = global_quantity_map or self.get_global_quantity_map()
        for item_code in recipes:
            recipes[item_code] *= sets
        delta = recipes - Counter(global_quantity_map)
        return delta

    def get_server_status(self) -> StatusSchema:
        return self.client.get_server_status()

    def get_account_items(self, characters: List[CharacterSchemaExtension] = None, bank_items: Dict[str, int] = None) -> AccountItems:
        account_items = AccountItems()
        characters = characters or self.get_all_character_details()
        for character in characters:
            account_items.character_equipment[character.name] += character.equipped_items
            account_items.character_inventory[character.name] += character.inventory_map
            account_items.account += character.equipped_items + character.inventory_map
        if bank_items:
            bank_items_counter = Counter(bank_items)
        else:
            bank_items_counter = Counter(self.get_bank_items_map(ignore_reservations=True))
        account_items.bank += bank_items_counter
        account_items.account += bank_items_counter
        return account_items
