from datetime import datetime
from typing import Tuple, Type

from type_base import T, TypeBase

from artifactsmmo.models import GeOrderHistorySchema
from artifactsmmo.service.helpers import format_level


class GeBuyHandler(TypeBase[GeOrderHistorySchema]):
    def _get_schema(self) -> Type[GeOrderHistorySchema]:
        return GeOrderHistorySchema

    def _get_message_timestamp(self, content: T) -> datetime:
        return content.sold_at

    def _handle_content(self, content: GeOrderHistorySchema) -> Tuple[str, bool]:
        message = ''
        item_code = content.code
        item = self.service.get_item(item_code)
        if item.level >= 10 or content.buyer == self.player_account:
            message = (
                f'⚖️ {content.buyer} bought {content.quantity}x {content.code} {format_level(item.level)} from {content.seller} '
                f'for {content.price}g ({content.quantity * content.price}g total).'
            )

        return message, True
