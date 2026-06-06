from datetime import datetime
from typing import Tuple, Type

from type_base import T, TypeBase

from artifactsmmo.models import ActiveEventSchema


class EventRemovedHandler(TypeBase[ActiveEventSchema]):
    def _get_schema(self) -> Type[ActiveEventSchema]:
        return ActiveEventSchema

    def _get_message_timestamp(self, content: T) -> datetime:
        return content.expiration

    def _handle_content(self, content: ActiveEventSchema) -> Tuple[str, bool]:
        return f'🪫 Event {content.name} ({content.map.interactions.content.code}) ended.', True
