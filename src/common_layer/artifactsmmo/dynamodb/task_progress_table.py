from dataclasses import dataclass
from datetime import datetime, timedelta, UTC
from decimal import Decimal
import os
from typing import List, Optional, Set

import boto3 as boto3
from botocore.exceptions import ClientError

from artifactsmmo.log.logger import logger


@dataclass
class TaskProgress:
    quest_id: str
    drop_item: str
    counter: int
    target: int
    delete_at_ts: float
    elapsed: float
    task_start: Optional[float] = None
    task_end: Optional[float] = None
    leader: Optional[str] = None
    characters: Optional[Set[str]] = None


class TaskProgressTable:
    HASH_KEY = 'quest_id'
    RANGE_KEY = 'drop_item'

    def __init__(self):
        table_name = os.environ.get('TASK_PROGRESS_TABLE_NAME')
        self.is_cloud = bool(table_name)

        if self.is_cloud:
            self.table = boto3.resource('dynamodb').Table(table_name)

    def create(self, quest_id: str, drop_item: str, drop_count: int, character_name: str = None):
        if self.is_cloud and quest_id and drop_item:
            now = Decimal(str(int(datetime.now(UTC).timestamp())))
            delete_at_ts = Decimal(str(int(now) + int(timedelta(days=4).total_seconds())))

            item = {
                self.HASH_KEY: quest_id,
                self.RANGE_KEY: drop_item,
                'counter': Decimal(0),
                'target': Decimal(drop_count),
                'delete_at_ts': delete_at_ts,
                'elapsed': Decimal(0),
            }

            if character_name:
                item['leader'] = character_name

            try:
                self.table.put_item(
                    Item=item,
                    ConditionExpression='attribute_not_exists(elapsed)',
                )
                logger.info(f'Created quest-details for quest_id={quest_id}, drop_item={drop_item}, drop_count={drop_count}')
            except ClientError as e:
                if e.response['Error']['Code'] != 'ConditionalCheckFailedException':
                    logger.error(f'Error writing to DynamoDB: {e}')

    def update(self, quest_id: str, drop_item: str, drop_count: int, character_name: str, increment: int) -> int:
        if self.is_cloud and quest_id and drop_item:
            now_int = int(datetime.now(UTC).timestamp())
            now = Decimal(str(now_int))
            delete_at_ts = Decimal(str(now_int + int(timedelta(days=3).total_seconds())))

            response = self.table.update_item(
                Key={
                    self.HASH_KEY: quest_id,
                    self.RANGE_KEY: drop_item,
                },
                UpdateExpression=(
                    'ADD #counter :increment, characters :character_name '
                    'SET target = if_not_exists(target, :drop_count), '
                    'task_start = if_not_exists(task_start, :now), '
                    'task_end = :now, '
                    'elapsed = :now - if_not_exists(task_start, :now), '
                    'delete_at_ts = :delete_at_ts'
                ),
                ExpressionAttributeNames={
                    '#counter': 'counter',
                },
                ExpressionAttributeValues={
                    ':increment': Decimal(increment),
                    ':character_name': set(character_name),  # string set
                    ':drop_count': Decimal(drop_count),
                    ':now': now,
                    ':delete_at_ts': delete_at_ts,
                },
                ReturnValues='ALL_NEW',
            )

            if 'Attributes' in response:
                return int(response['Attributes'].get('counter', 0))

        return 0

    def get_progress(self, quest_id: str, drop_item: str) -> Optional[TaskProgress]:
        if self.is_cloud and quest_id and drop_item:
            response = self.table.get_item(
                Key={
                    self.HASH_KEY: quest_id,
                    self.RANGE_KEY: drop_item,
                },
                ConsistentRead=True,
            )
            if 'Item' in response:
                return self.db_to_obj(response['Item'])
        return None

    def get_quest_progress(self, quest_id: str) -> List[TaskProgress]:
        if self.is_cloud and quest_id:
            response = self.table.query(
                KeyConditionExpression=f'{self.HASH_KEY} = :quest_id',
                ExpressionAttributeValues={':quest_id': quest_id},
            )
            if 'Items' in response:
                return [self.db_to_obj(item) for item in response['Items']]

        return []

    @staticmethod
    def db_to_obj(item: dict) -> TaskProgress:
        return TaskProgress(
            quest_id=item.get('quest_id', ''),
            drop_item=item['drop_item'],
            counter=int(item.get('counter', 0)),
            target=int(item.get('target', 0)),
            delete_at_ts=float(item.get('delete_at_ts', 0)),
            elapsed=float(item.get('elapsed', 0)),
            task_start=float(item['task_start']) if 'task_start' in item else None,
            task_end=float(item['task_end']) if 'task_end' in item else None,
            leader=item.get('leader'),
            characters=set(item.get('characters', [])) if 'characters' in item else None,
        )
