from datetime import datetime
from typing import Dict, List, Tuple, Type

from type_base import T, TypeBase

from artifactsmmo.dynamodb.follower_table import FollowerSubscription
from artifactsmmo.dynamodb.logs_table import LogsTable
from artifactsmmo.models import LogSchema
from artifactsmmo.queue.dispatcher_queue import DispatcherQueue
from artifactsmmo.service.follower_service import FollowerService
from artifactsmmo.service.service import Service
from artifactsmmo.telegram.client import TelegramClient


class AccountLogHandler(TypeBase[LogSchema]):
    def __init__(self, service: Service, telegram_client: TelegramClient, dispatcher_queue: DispatcherQueue, player_account: str):
        super().__init__(service, telegram_client, dispatcher_queue, player_account)
        self.logs_table: LogsTable = LogsTable()
        self.follower_service = FollowerService()

    def _get_schema(self) -> Type[LogSchema]:
        return LogSchema

    def _get_message_timestamp(self, content: T) -> datetime:
        return content.created_at

    def _handle_content(self, log: LogSchema) -> Tuple[str, bool]:
        inserted_logs = self.logs_table.upload_logs([log])
        follower_subscriptions: Dict[str, List[FollowerSubscription]] = self.follower_service.get_all_follower_subscriptions()
        if inserted_logs and follower_subscriptions:
            character_name = log.character
            if character_name in follower_subscriptions:
                self.follower_service.notify_updates(follower_subscriptions[character_name], inserted_logs)

        return '', False
