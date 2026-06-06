from datetime import datetime, timedelta
from typing import Tuple, Type

from type_base import T, TypeBase

from artifactsmmo.log.logger import logger
from artifactsmmo.models import ActiveEventSchema


class EventSpawnHandler(TypeBase[ActiveEventSchema]):
    def _get_schema(self) -> Type[ActiveEventSchema]:
        return ActiveEventSchema

    def _get_message_timestamp(self, content: T) -> datetime:
        return content.created_at

    def _handle_content(self, content: ActiveEventSchema) -> Tuple[str, bool]:
        try:
            self.dispatcher_queue.invoke()
        except Exception as e:
            logger.error(e)
        return f'🔋 Event {content.name} ({content.map.interactions.content.code}) spawned (⏱️ {timedelta(minutes=content.duration)}).', False
