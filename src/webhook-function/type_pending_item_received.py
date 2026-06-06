from datetime import datetime
from typing import Tuple, Type

from type_base import T, TypeBase

from artifactsmmo.models import PendingItemSchema
from artifactsmmo.service.helpers import escape_string


class PendingItemReceivedHandler(TypeBase[PendingItemSchema]):
    def _get_schema(self) -> Type[PendingItemSchema]:
        return PendingItemSchema

    def _get_message_timestamp(self, content: T) -> datetime:
        return content.created_at

    def _handle_content(self, content: PendingItemSchema) -> Tuple[str, bool]:
        claimed_items = ', '.join(f'{item.quantity}x {item.code}' for item in content.items) if content.items else ''
        gold_str = f', {content.gold} gold' if content.gold else ''
        message = f'🎁 Pending items received ({content.description}): {claimed_items}{gold_str}.'
        return message, False
