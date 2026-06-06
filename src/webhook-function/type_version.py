from datetime import datetime, UTC
from types import NoneType
from typing import Dict, Tuple, Type

from type_base import T, TypeBase


class VersionHandler(TypeBase[NoneType]):
    def _get_schema(self) -> Type[NoneType]:
        return NoneType

    def _get_message_timestamp(self, content: T) -> datetime:
        return datetime.now(UTC)

    def _handle_content(self, content: Dict) -> Tuple[str, bool]:
        content_str = ', '.join(f'{key}: {value}' for key, value in content.items())
        message = f'⚙️ Connected to websocket server {content_str}'
        return message, True
