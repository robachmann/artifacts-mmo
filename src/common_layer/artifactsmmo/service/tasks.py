import random
import string
from typing import Any, Dict, List, Optional, Set

from artifactsmmo.game_constants import FAILURE_POSITION_ID, SUCCESS_POSITION_ID
from artifactsmmo.models import AchievementType, CraftSkill, GatheringSkill, MapContentType, TaskType
from artifactsmmo.service.until import Until


class NextMove:
    def __init__(self, map_id: int = None, content_type: str | MapContentType = None, content_code: str = None):
        self.map_id = map_id
        self.content_type = content_type
        self.content_code = content_code

    def to_dict(self) -> dict:
        result_dict = {}
        if self.map_id:
            result_dict['map_id'] = self.map_id
        if self.content_type:
            result_dict['content_type'] = self.content_type
        if self.content_code:
            result_dict['content_code'] = self.content_code
        return result_dict


class Task:
    def __init__(
        self,
        action: str,
        kind: str,
        ttl: int = 1,
        task_id: Optional[str] = None,
        extra: Optional[Dict[str, Any]] = None,
        until: Optional[Until] = None,
    ):
        self.task_id = task_id

        if extra is None:
            extra = {}

        self.kind: str = kind
        self.action: str = action
        self.ttl: int = ttl
        self.extra: Dict[str, Any] = extra
        self.until: Optional[Until] = until

    @classmethod
    def from_dict(cls, task_json):
        until = None
        until_dict = task_json.get('until')
        if until_dict is not None:
            until = Until.from_dict(until_dict)
        return cls(
            action=task_json['action'],
            kind=task_json['kind'],
            ttl=task_json['ttl'],
            extra=task_json.get('extra', {}),
            until=until,
            task_id=task_json.get('task_id'),
        )

    def to_dict(self) -> dict:
        return_dict = {
            'kind': self.kind,
            'action': self.action,
            'ttl': self.ttl,
            'task_id': self.task_id,
            'extra': self.extra,
        }
        if self.until is not None:
            return_dict['until'] = self.until.to_dict()
        return return_dict

    @staticmethod
    def generate_task_id() -> str:
        return ''.join(random.choices(string.ascii_letters, k=4))

    @classmethod
    def solve_achievements(cls, achievement_type: AchievementType | str = None, ignore_achievements: List[str] = None):
        achievement_type_str = str(achievement_type) if achievement_type else None
        return cls(
            action='solve-achievements',
            kind='template',
            extra={
                'type': achievement_type_str,
                'ignore_achievements': ignore_achievements,
            },
        )

    @classmethod
    def solve_recycling_achievements(cls, gather_parts: bool = True):
        return cls(
            action='solve-recycling-achievements',
            kind='template',
            extra={'gather_parts': gather_parts},
        )

    @classmethod
    def solve_tasks_achievements(cls, task_type: str = TaskType.MONSTERS):
        return cls(action='solve-tasks-achievements', kind='template', extra={'type': task_type})

    @classmethod
    def fight_strongest_monster(cls, ttl: int = 1, target_level: int = None):
        return cls(action='fight-strongest-monster', kind='template', extra={'force_fight': True, 'ttl': ttl, 'target_level': target_level})

    @classmethod
    def sell_uncraftable_parts(cls, ttl: int = 1, threshold: int = 500):
        return cls(action='sell-uncraftable-parts', kind='template', ttl=ttl, extra={'threshold': threshold})

    @classmethod
    def sell_excess_parts(
        cls,
        threshold: int = 1000,
        item_type: str = 'all',
        item_subtype: str = 'all',
        max_level: int = None,
        ttl: int = 1,
    ):
        return cls(
            action='sell-excess-parts',
            kind='template',
            ttl=ttl,
            extra={
                'threshold': threshold,
                'item_type': item_type,
                'item_subtype': item_subtype,
                'max_level': max_level,
            },
        )

    @classmethod
    def dispose_excess_items(cls, skill: str = None):
        return cls(action='dispose-excess-items', kind='template', extra={'skill': skill})

    @classmethod
    def recycle_excess_items(cls, skill: CraftSkill | str = None):
        return cls(action='recycle-excess-items', kind='template', extra={'skill': skill})

    @classmethod
    def fight_monster(
        cls,
        monster: str = None,
        ttl: int = 1,
        utilities: Dict[str, int] = None,
        until: Until = None,
        equip_map: Dict[str, str] = None,
        exclude_items: List[str] = None,
        reservation_id: str = None,
        task_id: str = None,
        required_hp: int = None,
        expected_win_rate: float = None,
        map_id: int = None,
    ):
        return cls(
            action='fight-monster',
            kind='template',
            task_id=task_id,
            until=until,
            extra={
                'monster': monster,
                'ttl': ttl,
                'equip_map': equip_map,
                'utilities': utilities,
                'exclude_items': exclude_items,
                'reservation_id': reservation_id,
                'required_hp': required_hp,
                'expected_win_rate': expected_win_rate,
                'map_id': map_id,
            },
        )

    @classmethod
    def fight_boss_monster(
        cls,
        monster: str = None,
        participants: List[str] = None,
        ttl: int = 1,
        utilities: Dict[str, int] = None,
        utilities_map: Dict[str, Set[str]] = None,
        until: Until = None,
        equipments_map: Dict[str, Dict[str, str]] = None,
        equipments: List[Dict[str, Any]] = None,
        exclude_items: List[str] = None,
        reservation_id: str = None,
        task_id: str = None,
        required_hp: int = None,
        expected_win_rate: float = None,
        map_id: int = None,
        force_utilities: bool = False,
    ):
        return cls(
            action='fight-boss-monster',
            kind='template',
            task_id=task_id,
            until=until,
            extra={
                'monster': monster,
                'ttl': ttl,
                'participants': participants or [],
                'equipments_map': equipments_map,
                'equipments': equipments,
                'utilities': utilities,
                'utilities_map': utilities_map,
                'exclude_items': exclude_items,
                'reservation_id': reservation_id,
                'required_hp': required_hp,
                'expected_win_rate': expected_win_rate,
                'map_id': map_id,
                'force_utilities': force_utilities,
            },
        )

    @classmethod
    def fight(
        cls,
        ttl: int = 1,
        force_fight: bool = False,
        until: Until = None,
        task_id: str = None,
        monster: str = None,
        utilities: Dict[str, int] = None,
        required_hp: int = 0,
        expected_win_rate: float = None,
    ):
        return cls(
            action='fight',
            kind='action',
            ttl=ttl,
            task_id=task_id,
            until=until,
            extra={
                'force_fight': force_fight,
                'monster': monster,
                'utilities': utilities,
                'required_hp': required_hp,
                'expected_win_rate': expected_win_rate,
            },
        )

    @classmethod
    def force_fight(cls, monster: str):
        return cls.fight(monster=monster, force_fight=True, expected_win_rate=0)

    @classmethod
    def multi_character_fight(
        cls,
        leader: str,
        ttl: int = 1,
        force_fight: bool = False,
        until: Until = None,
        task_id: str = None,
        monster: str = None,
        participants: List[str] = None,
        utilities: Dict[str, int] = None,
        required_hp: int = 0,
        expected_win_rate: float = None,
        map_id: int = None,
    ):
        return cls(
            action='multi-character-fight',
            kind='action',
            ttl=ttl,
            task_id=task_id,
            until=until,
            extra={
                'force_fight': force_fight,
                'monster': monster,
                'utilities': utilities,
                'required_hp': required_hp,
                'expected_win_rate': expected_win_rate,
                'leader': leader,
                'participants': participants or [],
                'map_id': map_id,
            },
        )

    @classmethod
    def deliver_food(cls, map_id: int = None, ttl: int = 1):
        return cls(
            action='deliver-food',
            kind='template',
            ttl=ttl,
            extra={'map_id': map_id},
        )

    @classmethod
    def distribute_food(cls, task_id: str = None):
        return cls(action='distribute-food', kind='action', task_id=task_id, extra={})

    @classmethod
    def buy_recipe(cls, item: str, quantity: int, force_buy: bool = False, ttl: int = 1):
        return cls(
            action='buy-recipe',
            kind='template',
            ttl=ttl,
            extra={'item': item, 'quantity': quantity, 'force_buy': force_buy},
        )

    @classmethod
    def gather_reward(cls, item: str, quantity: int = 1, leader: str = None, task_id: str = None, task_type: str = 'items'):
        return cls(
            action='gather-reward',
            kind='template',
            ttl=1,
            task_id=task_id,
            extra={'item': item, 'quantity': quantity, 'leader': leader, 'task_type': task_type},
        )

    @classmethod
    def gather_resource(cls, resource: str, quantity: int = 1, until: Until = None, task_id: str = None, craft: str = None):
        return cls(
            action='gather-resource',
            kind='template',
            ttl=1,
            task_id=task_id,
            until=until,
            extra={'resource': resource, 'quantity': quantity, 'craft': craft},
        )

    @classmethod
    def prepare_recipe(cls, item: str, max_quantity: int = None, ttl: int = 1, task_id: str = None):
        return cls(
            action='prepare-recipe',
            kind='template',
            ttl=ttl,
            task_id=task_id,
            extra={'item': item, 'max_quantity': max_quantity},
        )

    @classmethod
    def gather_recipe(
        cls,
        item: str,
        quantity: int = 1,
        force_gather: bool = False,
        ttl: int = 1,
        global_max: int = None,
        task_id: str = None,
        leader: str = None,
        request_support: bool = False,
        reserve_target_product: bool = True,
        add_sleep_task: bool = True,
        total_quantity: int = None,
        missing_quantity: int = None,
        keep_equipment: bool = False,
    ):
        if quantity:
            if not total_quantity:
                total_quantity = quantity
            if not missing_quantity:
                missing_quantity = quantity

        return cls(
            action='gather-recipe',
            kind='template',
            ttl=ttl,
            task_id=task_id,
            extra={
                'item': item,
                'quantity': quantity,
                'force_gather': force_gather,
                'global_max': global_max,
                'leader': leader,
                'request_support': request_support,
                'reserve_target_product': reserve_target_product,
                'add_sleep_task': add_sleep_task,
                'total_quantity': total_quantity,
                'missing_quantity': missing_quantity,
                'keep_equipment': keep_equipment,
            },
        )

    @classmethod
    def craft_recipe(
        cls,
        item: str,
        quantity: int = 1,
        ttl: int = 1,
        allow_fewer: bool = False,
        global_max: int = None,
        target: str = 'bank',
        task_id: str = None,
        leader: str = None,
    ):
        return cls(
            action='craft-recipe',
            kind='template',
            ttl=ttl,
            task_id=task_id,
            extra={
                'item': item,
                'quantity': quantity,
                'allow_fewer': allow_fewer,
                'global_max': global_max,
                'target': target,
                'leader': leader,
            },
        )

    @classmethod
    def craft(
        cls,
        item: str,
        quantity: int = 1,
        allow_fewer: bool = False,
        skill: str = None,
        target: str = 'bank',
        recraft: bool = False,
        task_id: str = None,
    ):
        return cls(
            action='craft',
            kind='action',
            task_id=task_id,
            extra={'item': item, 'quantity': quantity, 'allow_fewer': allow_fewer, 'skill': skill, 'target': target, 'recraft': recraft},
        )

    @classmethod
    def craft_stronger_gear(cls, quantity: int = 1):
        return cls(action='craft-stronger-gear', kind='template', extra={'quantity': quantity})

    @classmethod
    def report(cls, include_task_report: bool = True):
        return cls(action='report', kind='action', extra={'include_task_report': include_task_report})

    @classmethod
    def withdraw(cls, item: str = None, quantity: int = 1, task_id: str = None, items: Dict[str, int] = None):
        if item and not items:
            items = {item: quantity}
        return cls(
            action='withdraw',
            kind='action',
            task_id=task_id,
            extra={
                'items': items,
            },
        )

    @classmethod
    def withdraw_gold(cls, quantity: int = 1):
        return cls(action='withdraw-gold', kind='action', extra={'quantity': quantity})

    @classmethod
    def withdraw_teleport_item(cls):
        return cls(action='withdraw-teleport-item', kind='template')

    @classmethod
    def buy_bank_expansion(cls):
        return cls(action='buy-bank-expansion', kind='action')

    @classmethod
    def rest(cls):
        return cls(action='rest', kind='action')

    @classmethod
    def move(cls, content_type: str = None, content_code: str = None, map_id: int = None):
        if map_id is not None:
            return cls(action='move', kind='action', extra={'map_id': map_id})
        else:
            return cls(action='move', kind='action', extra={'content_type': content_type, 'content_code': content_code})

    @classmethod
    def transition(cls):
        return cls(action='transition', kind='action')

    @classmethod
    def move_success(cls):
        return cls.move(map_id=SUCCESS_POSITION_ID)

    @classmethod
    def move_failure(cls):
        return cls.move(map_id=FAILURE_POSITION_ID)

    @classmethod
    def equip_best_gear(cls):
        return cls(action='equip-best-gear', kind='template')

    @classmethod
    def solve_task(
        cls,
        use_utilities: bool = False,
        allow_cancellation: bool = True,
        task_type: str = 'monsters',
        start_solving: bool = True,
        task_id: str = None,
        deposit_coins: bool = False,
        priority: str = 'time',
    ):
        return cls(
            action='solve-task',
            kind='template',
            task_id=task_id,
            extra={
                'use_utilities': use_utilities,
                'allow_cancellation': allow_cancellation,
                'start_solving': start_solving,
                'type': task_type,
                'deposit_coins': deposit_coins,
                'priority': priority,
            },
        )

    @classmethod
    def solve_event(
        cls,
        use_utilities: bool = False,
        content_type: MapContentType = None,
        content_code: str = None,
        map_id: int = None,
        event_parameters: Dict[str, Dict[str, int]] = None,
    ):
        return cls(
            action='solve-event',
            kind='template',
            extra={
                'use_utilities': use_utilities,
                'content_type': str(content_type) if content_type else None,
                'content_code': content_code,
                'map_id': map_id,
                'event_parameters': event_parameters,
            },
        )

    @classmethod
    def accept_new_task(
        cls,
        solve_task: bool = True,
        task_id: str = None,
        allow_cancellation: bool = False,
        priority: str = 'time',
    ):
        return cls(
            action='accept-new-task',
            kind='action',
            task_id=task_id,
            extra={'solve_task': solve_task, 'allow_cancellation': allow_cancellation, 'priority': priority},
        )

    @classmethod
    def finish_task(cls):
        return cls(action='finish-task', kind='template')

    @classmethod
    def complete_task(cls, deposit_coins: bool = True):
        return cls(action='complete-task', kind='action', extra={'deposit_coins': deposit_coins})

    @classmethod
    def cancel_task(cls):
        return cls(action='cancel-task', kind='action')

    @classmethod
    def exchange_task_coins(cls, reward: str = None):
        return cls(action='exchange-task-coins', kind='template', extra={'reward': reward})

    @classmethod
    def exchange_gifts(cls):
        return cls(action='exchange-gifts', kind='template')

    @classmethod
    def trade(cls, item: str, quantity: int = 1):
        return cls(action='trade', kind='action', extra={'item': item, 'quantity': quantity})

    @classmethod
    def exchange(cls, ttl: int = 1):
        return cls(action='exchange', kind='action', ttl=ttl)

    @classmethod
    def christmas_exchange(cls, ttl: int = 1):
        return cls(action='christmas-exchange', kind='action', ttl=ttl)

    @classmethod
    def deposit(cls, item: str = None, quantity: int = 1, task_id: str = None, items: Dict[str, int] = None):
        if item and not items:
            items = {item: quantity}
        return cls(action='deposit', kind='action', task_id=task_id, extra={'items': items})

    @classmethod
    def deposit_gold(cls, quantity: int = 1):
        return cls(action='deposit-gold', kind='action', extra={'quantity': quantity})

    @classmethod
    def equip_utility(
        cls,
        item: str,
        slot: str = 'utility1',
        quantity: int = 1,
        return_previous_position: bool = False,
        task_id: str = None,
    ):
        return cls(
            action='equip-utility',
            kind='template',
            task_id=task_id,
            extra={
                'item': item,
                'slot': slot,
                'quantity': quantity,
                'return_previous_position': return_previous_position,
            },
        )

    @classmethod
    def equip_items(cls, items_map: Dict[str, str] = None, task_id: str = None):
        return cls(action='equip-items', kind='template', task_id=task_id, extra={'items_map': items_map})

    @classmethod
    def verify_equipment(cls, items_map: Dict[str, str]):
        return cls(action='verify-equipment', kind='template', extra={'items_map': items_map})

    @classmethod
    def upgrade_basic_parts(
        cls,
        skill: CraftSkill | str = None,
        gather_missing_parts: bool = False,
        exclude_items: List[str] = None,
        include_items: List[str] = None,
        participants: List[str] = None,
    ):
        skill_str = str(skill) if skill else None
        return cls(
            action='upgrade-basic-parts',
            kind='template',
            extra={
                'gather_missing_parts': gather_missing_parts,
                'skill': skill_str,
                'exclude_items': exclude_items,
                'include_items': include_items,
                'participants': participants,
            },
        )

    @classmethod
    def unequip_all(cls, task_id: str = None):
        return cls(action='unequip-all', task_id=task_id, kind='template')

    @classmethod
    def unequip(cls, slot: str, quantity: int = 1):
        return cls(action='unequip', kind='action', extra={'slot': slot, 'quantity': quantity})

    @classmethod
    def unequip_utilities(cls, return_previous_position: bool = False):
        return cls(action='unequip-utilities', kind='template', extra={'return_previous_position': return_previous_position})

    @classmethod
    def equip(cls, item: str, slot: str, quantity: int = 1):
        return cls(action='equip', kind='action', extra={'item': item, 'slot': slot, 'quantity': quantity})

    @classmethod
    def recycle_item(
        cls,
        item: str = None,
        quantity: int = None,
        keep_quantity: int = None,
        recraft: bool = False,
        keep_map: Dict[str, int] = None,
    ):
        return cls(
            action='recycle-item',
            kind='template',
            extra={'item': item, 'quantity': quantity, 'keep_quantity': keep_quantity, 'recraft': recraft, 'keep_map': keep_map},
        )

    @classmethod
    def sell_item(cls, item: str, sell_price: int, quantity: int = None, keep_quantity: int = None):
        return cls(
            action='sell-item',
            kind='template',
            extra={'item': item, 'sell_price': sell_price, 'quantity': quantity, 'keep_quantity': keep_quantity},
        )

    @classmethod
    def fill_order(cls, buy_order_id: str):
        return cls(action='fill-order', kind='template', extra={'buy_order_id': buy_order_id})

    @classmethod
    def fill_ge(cls, buy_order_id: str, quantity: int):
        return cls(action='fill', kind='action', extra={'buy_order_id': buy_order_id, 'quantity': quantity})

    @classmethod
    def sell_ge(cls, item: str, sell_price: int, quantity: int = 1, ttl: int = 1):
        return cls(action='sell', kind='action', ttl=ttl, extra={'item': item, 'quantity': quantity, 'sell_price': sell_price})

    @classmethod
    def buy_item(cls, item: str, quantity: int = 1, force_buy: bool = False):
        return cls(action='buy-item', kind='template', extra={'item': item, 'quantity': quantity, 'force_buy': force_buy})

    @classmethod
    def buy_order(cls, order_id: str, max_quantity: int = None):
        return cls(action='buy-order', kind='template', extra={'order_id': order_id, 'max_quantity': max_quantity})

    @classmethod
    def cancel_sell_order(cls, order_id: str):
        return cls(action='cancel-sell-order', kind='template', extra={'order_id': order_id})

    @classmethod
    def cancel_order(cls, order_id: str):
        return cls(action='cancel-order', kind='action', extra={'order_id': order_id})

    @classmethod
    def sell_npc(cls, item: str, npc: str, event_end_ts: int = None, quantity: int = 1, ttl: int = 1):
        return cls(
            action='sell-npc',
            kind='action',
            ttl=ttl,
            extra={
                'item': item,
                'quantity': quantity,
                'npc': npc,
                'event_end_ts': event_end_ts,
            },
        )

    @classmethod
    def buy_ge(cls, order_id: str, quantity: int = 1, ttl: int = 1):
        return cls(action='buy', kind='action', ttl=ttl, extra={'order_id': order_id, 'quantity': quantity})

    @classmethod
    def buy_npc(cls, item: str, npc: str, event_end_ts: int = None, quantity: int = 1, ttl: int = 1):
        return cls(
            action='buy-npc',
            kind='action',
            ttl=ttl,
            extra={
                'item': item,
                'quantity': quantity,
                'npc': npc,
                'event_end_ts': event_end_ts,
            },
        )

    @classmethod
    def recycle(cls, item: str, quantity: int = 1, ttl: int = 1, recraft: bool = False):
        return cls(action='recycle', kind='action', ttl=ttl, extra={'item': item, 'quantity': quantity, 'recraft': recraft})

    @classmethod
    def use_item(cls, item: str, quantity: int = 1, ttl: int = 1, task_id: str = None):
        return cls(action='use-item', kind='action', ttl=ttl, task_id=task_id, extra={'item': item, 'quantity': quantity})

    @classmethod
    def gather(cls, skill: str, resource: str, ttl: int = 1, until: Until = None, task_id: str = None, craft: str = None):
        return cls(
            action='gather',
            kind='action',
            ttl=ttl,
            task_id=task_id,
            extra={'skill': skill, 'resource': resource, 'craft': craft},
            until=until,
        )

    @classmethod
    def level_skill(
        cls,
        skill: str,
        target_level: int = None,
        stock_only: bool = False,
        allow_task_parts: bool = False,
        allow_event_parts: bool = False,
        item: str = None,
        request_support: bool = False,
        level_approach: str = None,
        task_id: str = None,
    ):
        return cls(
            action='level-skill',
            kind='template',
            task_id=task_id,
            extra={
                'skill': skill,
                'level': target_level,
                'stock_only': stock_only,
                'item': item,
                'allow_task_parts': allow_task_parts,
                'allow_event_parts': allow_event_parts,
                'request_support': request_support,
                'level_approach': level_approach,
            },
        )

    @classmethod
    def level_crafting_skill(
        cls,
        skill: CraftSkill | str,
        target_level: int = None,
        stock_only: bool = False,
        allow_task_parts: bool = False,
        allow_event_parts: bool = False,
        allow_boss_parts: bool = False,
        item: str = None,
        request_support: bool = False,
        task_id: str = None,
    ):
        return cls(
            action='level-crafting-skill',
            kind='template',
            task_id=task_id,
            extra={
                'skill': str(skill),
                'level': target_level,
                'stock_only': stock_only,
                'item': item,
                'allow_task_parts': allow_task_parts,
                'allow_event_parts': allow_event_parts,
                'allow_boss_parts': allow_boss_parts,
                'request_support': request_support,
            },
        )

    @classmethod
    def level_gathering_skill(cls, skill: GatheringSkill | str, target_level: int = None):
        return cls(
            action='level-gathering-skill',
            kind='template',
            extra={'skill': str(skill), 'level': target_level},
        )

    @classmethod
    def level_fight(cls, target_level: int = None, monster: str = None):
        return cls(action='level-fight', kind='template', extra={'level': target_level, 'monster': monster})

    @classmethod
    def sleep(
        cls,
        task_id: str = None,
        leader: str = None,
        ttl: int = 1,
        seconds: int = 30,
        items_map: Dict[str, int] = None,
        reload_character: bool = True,
    ):
        return cls(
            action='sleep',
            kind='action',
            ttl=ttl,
            task_id=task_id,
            extra={'seconds': seconds, 'leader': leader, 'items_map': items_map, 'reload_character': reload_character},
        )

    @classmethod
    def buy_from_npc(
        cls,
        item: str,
        npc: str,
        event_end_ts: int = None,
        quantity: int = 1,
        task_id: str = None,
        map_id: int = None,
    ):
        return cls(
            action='buy-from-npc',
            kind='template',
            task_id=task_id,
            extra={
                'item': item,
                'quantity': quantity,
                'npc': npc,
                'map_id': map_id,
                'event_end_ts': event_end_ts,
            },
        )

    @classmethod
    def sell_to_npc(
        cls,
        item: str,
        content_type: str,
        npc: str,
        event_end_ts: int = None,
        quantity: int = 1,
        task_id: str = None,
        map_id: int = None,
    ):
        return cls(
            action='sell-to-npc',
            kind='template',
            task_id=task_id,
            extra={
                'item': item,
                'quantity': quantity,
                'content_type': content_type,
                'npc': npc,
                'map_id': map_id,
                'event_end_ts': event_end_ts,
            },
        )

    @classmethod
    def send_message(cls, message: str):
        return cls(action='send-message', kind='template', extra={'message': message})

    @classmethod
    def ensure_item(cls, item: str, global_max: int, reserve_target_product: bool = False, request_support: bool = False):
        return cls(
            action='ensure-item',
            kind='template',
            extra={
                'item': item,
                'global_max': global_max,
                'reserve_target_product': reserve_target_product,
                'request_support': request_support,
            },
        )

    @classmethod
    def ensure_equipment(
        cls,
        exact_map: Dict[str, int] = None,
        equipment_list: List[str] = None,
        equipment_map: Dict[str, str] = None,
        quantity: int = 1,
        exact_list: List[str] = None,
        equipment_str: str = None,
        request_support: bool = False,
        craft_available_first: bool = True,
    ):
        if equipment_str:
            equipment_list = equipment_str.split(' ')
        return cls(
            action='ensure-equipment',
            kind='template',
            extra={
                'equipment_list': equipment_list,
                'equipment_map': equipment_map,
                'quantity': quantity,
                'exact_list': exact_list,
                'exact_map': exact_map,
                'request_support': request_support,
                'craft_available_first': craft_available_first,
            },
        )

    @classmethod
    def ensure_inventory(
        cls,
        item_map: Dict[str, int] = None,
        gold: int = 0,
        keep_consumables: bool = False,
        keep_teleport_items: bool = True,
        keep_items: List[str] = None,
        return_previous_position: bool = False,
        use_city_bank: bool = False,
        next_move: NextMove = None,
        deposit_gold: bool = True,
        task_id: str = None,
    ):
        return cls(
            action='ensure-inventory',
            kind='template',
            task_id=task_id,
            extra={
                'items': dict(item_map) if item_map else {},
                'gold': gold,
                'keep_consumables': keep_consumables,
                'keep_teleport_items': keep_teleport_items,
                'return_previous_position': return_previous_position,
                'use_city_bank': use_city_bank,
                'keep_items': keep_items,
                'next_move': next_move.to_dict() if next_move else None,
                'deposit_gold': deposit_gold,
            },
        )

    @classmethod
    def ensure_tools(
        cls,
        level: int,
        mining: int = 0,
        woodcutting: int = 0,
        fishing: int = 0,
        alchemy: int = 0,
        gather_all_first: bool = False,
    ):
        return cls(
            action='ensure-tools',
            kind='template',
            extra={
                'level': level,
                'mining': mining,
                'woodcutting': woodcutting,
                'fishing': fishing,
                'alchemy': alchemy,
                'gather_all_first': gather_all_first,
            },
        )

    @classmethod
    def equip_wisdom_gear(cls, task_id: str = None):
        return cls(action='equip-wisdom-gear', kind='template', task_id=task_id, extra={})

    @classmethod
    def finish_quest(cls, skip_post_tasks: bool = False, rest: bool = True, task_id: str = None):
        return cls(
            action='finish-quest',
            kind='template',
            task_id=task_id,
            extra={
                'skip_post_tasks': skip_post_tasks,
                'rest': rest,
            },
        )

    @classmethod
    def exchange_currency(cls, item: str, currency: str, keep_currency: int = 0, task_id: str = None):
        return cls(
            action='exchange-currency',
            kind='template',
            task_id=task_id,
            extra={'item': item, 'currency': currency, 'keep_currency': keep_currency},
        )

    @classmethod
    def claim_pending_items(cls):
        return cls(action='claim-pending-items', kind='template')

    @classmethod
    def claim_pending_item(cls, _id: str):
        return cls(action='claim-pending-item', kind='action', extra={'id': _id})

    @classmethod
    def ensure_healing_capacity(cls, min_level: int = None, max_level: int = None):
        return cls(
            action='ensure-healing-capacity',
            kind='template',
            extra={'min_level': min_level, 'max_level': max_level},
        )

    @classmethod
    def compact_grand_exchange_orders(cls):
        return cls(
            action='compact-grand-exchange-orders',
            kind='template',
            extra={},
        )

    @classmethod
    def delete_items(cls):
        return cls(
            action='delete-items',
            kind='template',
            extra={},
        )

    @classmethod
    def delete_inventory(cls, item: str, quantity: int):
        return cls(
            action='delete-inventory',
            kind='action',
            extra={'item': item, 'quantity': quantity},
        )

    @classmethod
    def craft_items_parallel(cls, item: str, quantity: int, participants: List[str], task_id: str = None):
        return cls(
            action='craft-items-parallel',
            kind='template',
            task_id=task_id,
            extra={'item': item, 'quantity': quantity, 'participants': participants},
        )

    @classmethod
    def reload_character(cls):
        return cls(action='reload-character', kind='action')

    @classmethod
    def from_kwargs(cls, params: list[str]):
        kwargs = dict(p.split('=', 1) for p in params)
        action = kwargs.pop('action')
        if 'ttl' in kwargs:
            kwargs['ttl'] = int(kwargs['ttl'])
        return getattr(cls, action.replace('-', '_'))(**kwargs)
