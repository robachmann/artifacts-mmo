from datetime import datetime
from typing import Tuple, Type

from type_base import T, TypeBase

from artifactsmmo.extensions import ItemSchemaExtension
from artifactsmmo.log.logger import logger
from artifactsmmo.models import GEOrderSchema
from artifactsmmo.service.helpers import format_level, format_number


class BuyOrderHandler(TypeBase[GEOrderSchema]):
    def _get_schema(self) -> Type[GEOrderSchema]:
        return GEOrderSchema

    def _get_message_timestamp(self, content: T) -> datetime:
        return content.created_at

    def _handle_content(self, content: GEOrderSchema) -> Tuple[str, bool]:
        message = ''
        silent = False
        item_code = content.code
        item: ItemSchemaExtension = self.service.get_item(item_code)
        is_recycling_candidate = item.is_recyclable and self.service.is_recycling_candidate(content.price)
        if item.level >= 10 or is_recycling_candidate or content.account == self.player_account:
            silent = not is_recycling_candidate
            if content.quantity > 1:
                message = (
                    f'🙋‍♂️⚖️ {content.account} requests {content.quantity}x {content.code} {format_level(item.level)} for '
                    f'{format_number(content.price)}g each ({format_number(content.quantity * content.price)}g total); '
                    f'order id: {content.id}{" ♻️" if is_recycling_candidate else ""}.'
                )
            else:
                message = (
                    f'🙋‍♂️⚖️ {content.account} requests 1x {content.code} {format_level(item.level)} for '
                    f'{format_number(content.price)}g; order id: {content.id}{" ♻️" if is_recycling_candidate else ""}.'
                )
        else:
            logger.info(
                f'Ignored notification about new GE order: {content.quantity}x {content.code} {format_level(item.level)} for '
                f'{format_number(content.price)}'
            )
        return message, silent
