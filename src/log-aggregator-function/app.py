from collections import Counter
import os
from typing import Dict, List

from aws_lambda_powertools.utilities.data_classes import event_source, SNSEvent
from aws_lambda_powertools.utilities.typing import LambdaContext
from dotenv import load_dotenv

from artifactsmmo.client.client import Client
from artifactsmmo.dynamodb.follower_table import FollowerSubscription
from artifactsmmo.dynamodb.logs_table import LogsTable
from artifactsmmo.log.logger import logger
from artifactsmmo.models import LogSchema
from artifactsmmo.service.follower_service import FollowerService
from artifactsmmo.service.service import Service


class LogAggregator:
    def __init__(self):
        if os.environ.get('AWS_LAMBDA_FUNCTION_NAME') is None:
            load_dotenv()

        self.logs_table: LogsTable = LogsTable()
        self.service: Service = Service(Client())
        self.follower_service = FollowerService()

    def handler(self, event: SNSEvent, context: LambdaContext):
        if event:
            character_logs_map = Counter()
            for r in event.records:
                message = str(r.sns.message)
                character_logs_map[message] += 1
                logger.append_keys(message_id=r.sns.message_id)

            received_logs: Dict[str, int] = {}
            inserted_logs_map: Dict[str, int] = {}

            follower_subscriptions: Dict[str, List[FollowerSubscription]] = self.follower_service.get_all_follower_subscriptions()
            for character_name, count in character_logs_map.items():
                count += 1
                logs: List[LogSchema] = self.service.get_logs(count=count, character_name=character_name)
                inserted_logs = self.logs_table.upload_logs(logs)
                received_logs[character_name] = len(logs)
                inserted_logs_map[character_name] = len(inserted_logs)
                if inserted_logs and character_name in follower_subscriptions:
                    self.follower_service.notify_updates(follower_subscriptions[character_name], inserted_logs)

            logger.info(f'requested_logs={dict(character_logs_map)}, received_logs={received_logs}, inserted_logs={inserted_logs_map}')


log_aggregator = LogAggregator()


@event_source(data_class=SNSEvent)
def handler(event: SNSEvent, context: LambdaContext):
    log_aggregator.handler(event, context)


if __name__ == '__main__':
    log_aggregator.handler(SNSEvent(data={}), LambdaContext())
