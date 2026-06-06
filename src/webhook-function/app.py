import json
import os

from aws_lambda_powertools.utilities.data_classes import event_source, SQSEvent
from aws_lambda_powertools.utilities.data_classes.sqs_event import SQSRecord
from aws_lambda_powertools.utilities.typing import LambdaContext
from type_account_log import AccountLogHandler
from type_achievement_unlocked import AchievementUnlockedHandler
from type_announcement import AnnouncementHandler
from type_event_removed import EventRemovedHandler
from type_event_spawn import EventSpawnHandler
from type_grandexchange_buy import GeBuyHandler
from type_grandexchange_buy_order import BuyOrderHandler
from type_grandexchange_neworder import GeNewOrderHandler
from type_grandexchange_sell import GeSellHandler
from type_grandexchange_sell_order import SellOrderHandler
from type_pending_item_received import PendingItemReceivedHandler
from type_version import VersionHandler

from artifactsmmo.client.client import Client
from artifactsmmo.log.logger import logger
from artifactsmmo.queue.dispatcher_queue import DispatcherQueue
from artifactsmmo.service.helpers import account_name
from artifactsmmo.service.service import Service
from artifactsmmo.telegram.client import TelegramClient


class WebhookFunction:
    def __init__(self):
        if not os.environ.get('AWS_LAMBDA_FUNCTION_NAME'):
            from dotenv import load_dotenv

            load_dotenv()

        self.telegram_client = TelegramClient()
        self.service = Service(Client())
        self.dispatcher_queue = DispatcherQueue()
        self.player_account = account_name()

        self.message_handlers = {
            'account_log': AccountLogHandler(self.service, self.telegram_client, self.dispatcher_queue, self.player_account),
            'achievement_unlocked': AchievementUnlockedHandler(self.service, self.telegram_client, self.dispatcher_queue, self.player_account),
            'announcement': AnnouncementHandler(self.service, self.telegram_client, self.dispatcher_queue, self.player_account),
            'event_removed': EventRemovedHandler(self.service, self.telegram_client, self.dispatcher_queue, self.player_account),
            'event_spawn': EventSpawnHandler(self.service, self.telegram_client, self.dispatcher_queue, self.player_account),
            'grandexchange_buy': GeBuyHandler(self.service, self.telegram_client, self.dispatcher_queue, self.player_account),
            'grandexchange_buy_order': BuyOrderHandler(self.service, self.telegram_client, self.dispatcher_queue, self.player_account),
            'grandexchange_neworder': GeNewOrderHandler(self.service, self.telegram_client, self.dispatcher_queue, self.player_account),
            'grandexchange_sell': GeSellHandler(self.service, self.telegram_client, self.dispatcher_queue, self.player_account),
            'grandexchange_sell_order': SellOrderHandler(self.service, self.telegram_client, self.dispatcher_queue, self.player_account),
            'pending_item_received': PendingItemReceivedHandler(self.service, self.telegram_client, self.dispatcher_queue, self.player_account),
            'version': VersionHandler(self.service, self.telegram_client, self.dispatcher_queue, self.player_account),
        }

    def handler(self, event: SQSEvent = None, context: LambdaContext = None):
        for record in event.records:
            logger.append_keys(message_id=record.message_id)
            if record.json_body:
                self.handle_record(record)
            logger.remove_keys(['message_id'])
        return {'statusCode': 200, 'body': json.dumps({'status': 'ok'})}

    def handle_record(self, record: SQSRecord):
        message_type = record.json_body['type']
        message_data = record.json_body['data']

        json_body = record.json_body or {}
        data = json_body.get('data', {}) if isinstance(json_body, dict) else {}
        character_name = data.get('character', '') if data else ''
        fields = {'kind': message_type, 'character_name': character_name}

        if character_name:
            logger.info(f'Received webhook message of type {message_type}.', extra=fields)
        else:
            logger.info(f'Received webhook message of type {message_type}: {record.json_body}', extra=fields)

        if message_type in self.message_handlers:
            self.message_handlers[message_type].handle(message_data)
        else:
            logger.error(f'Unknown message type {message_type}')


webhook_function = WebhookFunction()


@event_source(data_class=SQSEvent)
def handler(event: SQSEvent, context: LambdaContext):
    webhook_function.handler(event, context)


if __name__ == '__main__':
    webhook_function.handler()
