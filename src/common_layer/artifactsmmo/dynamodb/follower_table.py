from dataclasses import dataclass
from datetime import datetime, timedelta, UTC
import os
from typing import List, Optional

import boto3

from artifactsmmo.log.logger import logger


@dataclass
class FollowerSubscription:
    character_name: str
    delete_at_ts: int
    message: Optional[str]
    message_id: Optional[str]
    type: Optional[str]


class FollowerTable:
    def __init__(self):
        table_name = os.environ.get('FOLLOWER_SUBSCRIPTIONS_TABLE_NAME')
        self.is_cloud = bool(table_name)

        if self.is_cloud:
            self.table = boto3.resource('dynamodb').Table(table_name)

    def add_subscription(self, character_name: str, minutes: int, subscription_type: str = 'follow'):
        if not self.is_cloud:
            return

        now_ts = int(datetime.now(UTC).timestamp())
        delete_at_ts = int(now_ts + timedelta(minutes=minutes).total_seconds())

        item = {
            'character_name': character_name,
            'delete_at_ts': delete_at_ts,
            'subscription_type': subscription_type,
            'static_partition': 'all-subscriptions',
        }

        self.table.put_item(Item=item)
        logger.info(f'Added follower subscription for character={character_name}')

    def get_all_subscriptions(self) -> List[FollowerSubscription]:
        subscriptions: List[FollowerSubscription] = []
        if not self.is_cloud:
            return subscriptions

        now_ts = datetime.now(UTC).timestamp()

        response = self.table.query(
            IndexName='all-subscriptions-index',
            KeyConditionExpression='static_partition = :all',
            ExpressionAttributeValues={':all': 'all-subscriptions'},
        )

        items = response.get('Items', [])
        logger.debug('Found %d follower subscriptions', len(items))

        for subscription in items:
            character_name = subscription.get('character_name')
            delete_at_ts = int(subscription.get('delete_at_ts', 0))
            message = subscription.get('message')
            message_id = subscription.get('message_id')
            subscription_type = subscription.get('subscription_type')

            if delete_at_ts > now_ts:
                subscriptions.append(FollowerSubscription(character_name, delete_at_ts, message, message_id, subscription_type))

        return subscriptions

    def delete_subscription(self, character_name: str):
        if not self.is_cloud:
            return

        self.table.delete_item(Key={'character_name': character_name})
        logger.info(f'Cleared follower subscription for character={character_name}')

    def update_subscription(self, follower_subscription: FollowerSubscription):
        if not self.is_cloud:
            return

        item = {
            'character_name': follower_subscription.character_name,
            'delete_at_ts': follower_subscription.delete_at_ts,
            'static_partition': 'all-subscriptions',
        }

        if follower_subscription.message_id:
            item['message_id'] = str(follower_subscription.message_id)
        if follower_subscription.message:
            item['message'] = follower_subscription.message
        if follower_subscription.type:
            item['subscription_type'] = follower_subscription.type

        self.table.put_item(Item=item)
        logger.info(
            f'Updated follower subscription for character={follower_subscription.character_name}, message_id={follower_subscription.message_id}'
        )
