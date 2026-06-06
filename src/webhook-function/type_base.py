from abc import ABC, abstractmethod
from datetime import datetime, timedelta, UTC
from typing import Generic, Tuple, Type, TypeVar

from artifactsmmo.log.logger import logger
from artifactsmmo.queue.dispatcher_queue import DispatcherQueue
from artifactsmmo.service.service import Service
from artifactsmmo.telegram.client import TelegramClient

T = TypeVar('T')


class TypeBase(ABC, Generic[T]):
    def __init__(self, service: Service, telegram_client: TelegramClient, dispatcher_queue: DispatcherQueue, player_account: str):
        self.service = service
        self.telegram_client = telegram_client
        self.dispatcher_queue = dispatcher_queue
        self.player_account = player_account

    def handle(self, data: dict):
        schema_class = self._get_schema()
        try:
            content = schema_class.from_dict(data)
        except AttributeError:
            content = data
        timestamp = self._get_message_timestamp(content)
        time_ago = self._get_time_delta(timestamp) if timestamp else None
        message, silent = self._handle_content(content)
        if message:
            self.telegram_client.send_notification(message=message, silent=silent)
            logger.info(f'Took {time_ago} to process event with resulting message: {message}')

    @abstractmethod
    def _get_schema(self) -> Type[T]:
        pass

    @abstractmethod
    def _handle_content(self, content: T) -> Tuple[str, bool]:
        pass

    @abstractmethod
    def _get_message_timestamp(self, content: T) -> datetime:
        pass

    @staticmethod
    def _get_time_delta(dt: datetime) -> timedelta:
        return datetime.now(UTC) - dt
