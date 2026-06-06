from dataclasses import dataclass, field
from datetime import datetime
from functools import cache
from itertools import chain, repeat
import os
import re
from typing import Dict, List, Optional, Set, Tuple

import requests
from urllib3 import Retry

from artifactsmmo.extensions import CharacterSchemaExtension
from artifactsmmo.game_constants import ELEMENTS
from artifactsmmo.log.logger import logger
from artifactsmmo.models import GEOrderSchema, MapSchema
from artifactsmmo.service.tasks import NextMove, Task
from artifactsmmo.service.until import Until

# Precompiled patterns (unchanged)
_special_chars = re.compile(r'([_*[\]()~`>#\+\-=|{}.!])')
_code_block_fix = re.compile(r'(`+)([^`]*)([`\\])')
_link_escape = re.compile(r'(\[[^\]]*\]\([^\)]*)([\\\)])')
_underline_disambiguate = re.compile(r'___')

# Fast-path set for early exit
_fast_check_set = set(r'\\_*[]()~`>#+-=|{}.!')


def escape_string(s: str) -> str:
    if not s or not any(c in _fast_check_set for c in s):
        return s

    s = s.replace('\\', r'\\')

    # Apply substitutions in order
    s = _special_chars.sub(r'\\\1', s)
    s = _code_block_fix.sub(r'\1\2\\\3', s)
    s = _link_escape.sub(r'\1\\\2', s)
    s = _underline_disambiguate.sub(r'__\\_', s)

    return s


def format_dict(dict_to_format: Dict) -> str:
    return ', '.join(f'{v}x {k}' for k, v in dict_to_format.items())


def escape_string_v1(s: str) -> str:
    # Step 1: Escape '\' character globally
    s = re.sub(r'\\', r'\\\\', s)  # Escape the backslash character everywhere

    # Step 2: Escape special characters '_', '*', '[', ']', '(', ')', '~', '`', '>', '#', '+', '-', '=', '|', '{', '}', '.', '!' globally, except where rules say otherwise
    special_chars = r'([_*[\]()~`>#\+\-=|{}.!])'
    s = re.sub(special_chars, r'\\\1', s)

    # Step 3: Handle backticks and backslashes inside pre/code blocks (assuming code blocks are surrounded by ``` or inline `)
    s = re.sub(r'(`+)([^`]*)([`\\])', r'\1\2\\\3', s)  # Escaping ` and \ inside pre/code blocks

    # Step 4: Escape ')' and '\' inside inline link (...) part
    s = re.sub(r'(\[[^\]]*\]\([^\)]*)([\\\)])', r'\1\\\2', s)

    # Step 5: Greedily treat `__` as underline (resolve ambiguity with ___italic underline___)
    s = re.sub(r'___', r'__\\_', s)  # Escape the ambiguous combination with an empty bold entity

    return s


def list_to_string(lst: List[str], fmt: str = None) -> str:
    if fmt is not None:
        lst = [f'{fmt}{escape_string(item)}{fmt}' for item in lst]
    if len(lst) == 0:
        return ''
    elif len(lst) == 1:
        return lst[0]
    else:
        return ', '.join(lst[:-1]) + ' and ' + lst[-1]


def is_item_available(currently_equipped: bool = False, bank_count: int = 0, item_index: int = 1) -> bool:
    return currently_equipped or bank_count >= item_index


@dataclass
class Bucket:
    quantity: int
    full: bool


class BucketFiller:
    def __init__(self, initial_bucket_capacity):
        self.initial_bucket_capacity = initial_bucket_capacity
        self.remaining_bucket_capacity = initial_bucket_capacity

    def generate_buckets(self, item_count: int) -> List[Bucket]:
        buckets: List[Bucket] = []

        while item_count > 0:
            if self.remaining_bucket_capacity == 0:
                self.remaining_bucket_capacity = self.initial_bucket_capacity

            current_bucket = min(self.remaining_bucket_capacity, item_count)
            self.remaining_bucket_capacity -= current_bucket
            item_count -= current_bucket
            buckets.append(Bucket(current_bucket, self.remaining_bucket_capacity == 0))

        return buckets


@dataclass
class ItemDropRate:
    item_code: str
    drop_rate_min: int
    drop_rate_max: int
    drop_rate_avg: int = field(init=False)

    def __post_init__(self):
        self.drop_rate_avg = (self.drop_rate_min + self.drop_rate_max) // 2


@dataclass
class ResolvedItemRecipe:
    available_items: Dict[str, int]
    missing_items: Dict[str, int]
    all_items: Dict[str, int]


@dataclass
class ResolvedItemRecipeDetails:
    code: str
    quantity: int
    resolved_recipe: ResolvedItemRecipe


@dataclass
class RecyclableItem:
    item_code: str
    item_level: int
    quantity: int
    total_drop_rate: int
    missing_items: Dict[str, int]


@dataclass
class ProcessTaskResult:
    new_tasks: List[Task]
    expiration: datetime
    character: CharacterSchemaExtension
    quest_result: Optional[str]
    quest_status: str | None
    clear_until: Optional[bool]
    hibernate: Optional[bool]


@dataclass
class ShoppingBasket:
    quantity: int
    item: str
    order_id: str


@dataclass
class CraftableItem:
    code: str
    quantity: int
    level: int
    required_parts: Dict[str, int]


def calculate_ge_stock(ge_items: List[GEOrderSchema]) -> int:
    return sum(ge.quantity for ge in ge_items)


def get_next_move(current_map: MapSchema, is_event_content: bool = False) -> NextMove:
    if is_event_content:
        return NextMove(map_id=current_map.map_id)
    else:
        return NextMove(content_type=current_map.interactions.content.type, content_code=current_map.interactions.content.code)


def calculate_total_sell_price(ge_items: List[GEOrderSchema], quantity: int) -> Tuple[int, int]:
    sorted_ge_items = sorted(ge_items, key=lambda item: item.price)
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


def get_sell_order_map(sell_orders: List[GEOrderSchema], quantity: int) -> Dict[str, int]:
    sell_order_map: Dict[str, int] = {}
    sorted_sell_orders = sorted(sell_orders, key=lambda item: (item.price, -item.quantity))

    quantity_remaining = quantity
    for sell_order in sorted_sell_orders:
        if quantity_remaining <= 0:
            break

        quantity_to_buy = min(quantity_remaining, sell_order.quantity)
        quantity_remaining -= quantity_to_buy
        sell_order_map[sell_order.id] = quantity_to_buy

    return sell_order_map


def format_until(until: Until) -> str:
    if until:
        return (
            f'status={until.status}, date_time={until.date_time}, drop_item={until.drop_item}, '
            f'drop_count={until.drop_count}, progress={until.progress}, '
        )
    else:
        return 'None'


class CustomRetry(Retry):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.status_forcelist = {486, 500, 502, 503, 504, 520}

    def is_retry(self, method, status_code, has_retry_after=False):
        if status_code in self.status_forcelist:
            logger.info(f'Retry request due to received status_code={status_code}')
            return True

        return super().is_retry(method, status_code, has_retry_after)

    def increment(self, *args, **kwargs):
        error = kwargs.get('error')
        if error:
            exc_type = self.get_exception_type(error)
            if isinstance(error, requests.exceptions.ReadTimeout):
                logger.info(f'Retryable error triggered due to instance {exc_type}.')
                return super().increment(*args, **kwargs)
            elif exc_type == 'ReadTimeoutError':
                logger.info(f'Retryable error triggered due to type {exc_type}.')
                return super().increment(*args, **kwargs)
            else:
                logger.error(f'Non-retryable error of type {exc_type} encountered: {error}')
                raise error  # Reraise the error to prevent retrying

        return super().increment(*args, **kwargs)

    @staticmethod
    def get_exception_type(error):
        if error:
            return error.__class__.__name__
        else:
            return 'Unknown'


@cache
def account_name() -> str:
    return os.getenv('ACCOUNT_NAME', '')


@cache
def character_1_name() -> str:
    return get_character_list()[0]


@cache
def character_2_name() -> str:
    return get_character_list()[1]


@cache
def character_3_name() -> str:
    return get_character_list()[2]


@cache
def character_4_name() -> str:
    return get_character_list()[3]


@cache
def character_5_name() -> str:
    return get_character_list()[4]


@cache
def get_character_list() -> List[str]:
    return os.getenv('CHARACTER_NAMES', '').split(',')


def format_number(number: int) -> str:
    if number < 10000:
        return str(number)
    else:
        return f'{number:,}'.replace(',', "'")


# subscript = str.maketrans("0123456789", "₀₁₂₃₄₅₆₇₈₉")
superscript = str.maketrans('0123456789', '⁰¹²³⁴⁵⁶⁷⁸⁹')


def format_level(level: int) -> str:
    return str(level).translate(superscript)


def format_elements_emojis(elements: Set[str]) -> str:
    emojis: List[str] = []
    for element in ELEMENTS:
        if element in elements:
            emojis.append(item_to_emoji(element))
    return ''.join(emojis)


def item_to_emoji(element: str) -> str:
    match element:
        case 'air':
            return '🌪️'
        case 'fire':
            return '🔥'
        case 'earth':
            return '🪨'
        case 'water':
            return '💧'
    return ''


def stats_iterator(value: int | float, count: int = None):
    if count is None:
        return repeat(value)
    return chain(repeat(value, count), repeat(0))


def format_long_number(int_number: int) -> str:
    return f'{int_number:,}'.replace(',', "'")
