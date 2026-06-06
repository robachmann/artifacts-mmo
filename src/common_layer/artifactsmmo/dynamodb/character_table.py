from datetime import datetime, UTC
from decimal import Decimal
import json
import os
from typing import List, Optional, Tuple

import boto3 as boto3
from botocore.exceptions import ClientError
import xxhash

from artifactsmmo.log.logger import logger
from artifactsmmo.quests.quests import Quest
from artifactsmmo.service.execution_context import ExecutionContext
from artifactsmmo.service.tasks import Task


class CharacterTable:
    HASH_KEY = 'character_name'

    def __init__(self):
        table_name = os.environ.get('CHARACTER_TABLE_NAME')
        self.is_cloud = bool(table_name)

        if self.is_cloud:
            self.table = boto3.resource('dynamodb').Table(table_name)

    def put_quest(self, character_name: str, quest: Quest, context: ExecutionContext) -> Tuple[Optional[Quest], bool]:
        continue_quest = True
        tasks_dict = [t.to_dict() for t in quest.tasks]
        tasks_str = json.dumps(tasks_dict, default=str)
        quest_hash = xxhash.xxh64(tasks_str).hexdigest()
        same_hash = quest.quest_hash == quest_hash

        if not context:
            context = ExecutionContext(character_name)
        elif not context.started_at_ts:
            logger.error(f'context.started_at_ts={context.started_at_ts}')
            context.started_at_ts = datetime.now(UTC).timestamp()

        new_updated_at_ts = Decimal(str(context.started_at_ts))

        if same_hash:
            logger.debug(f'Quest object has not changed, will not update DB entry, hash={quest_hash}.')
        elif self.is_cloud:
            item = {
                self.HASH_KEY: character_name,
                'quest_hash': quest_hash,
                'quest_id': quest.quest_id,
                'created_at': str(quest.created_at),
                'last_updated_at_ts': new_updated_at_ts,
            }

            if quest.description:
                item['description'] = str(quest.description)

            if quest.status:
                item['status'] = str(quest.status)

            if quest.result:
                item['result'] = str(quest.result)

            if quest.leader:
                item['leader'] = str(quest.leader)

            if tasks_str:
                item['tasks'] = tasks_str
                item['remaining_task_count'] = Decimal(len(tasks_dict))

            try:
                self.table.put_item(
                    Item=item,
                    ConditionExpression='attribute_not_exists(#pk) OR attribute_not_exists(last_updated_at_ts) OR last_updated_at_ts <= :new_updated_at_ts',
                    ExpressionAttributeNames={'#pk': self.HASH_KEY},
                    ExpressionAttributeValues={':new_updated_at_ts': new_updated_at_ts},
                )
                quest.quest_hash = quest_hash
            except ClientError as e:
                error_code = e.response.get('Error', {}).get('Code')
                if error_code == 'ConditionalCheckFailedException':
                    logger.info('Could not overwrite quest in table because a newer quest is already present. Will not continue quest.')
                else:
                    logger.error(f'Unexpected response: {e.response}, item={item}')
                quest = self.get_quest(character_name)
                context.started_at_ts = float(quest.updated_at_ts) if quest.updated_at_ts else None
                continue_quest = False

        return quest, continue_quest

    def get_quest(self, character_name: str) -> Optional[Quest]:
        if self.is_cloud:
            response = self.table.get_item(Key={self.HASH_KEY: character_name}, ConsistentRead=True)
            if 'Item' in response:
                return self.db_to_quest(response['Item'])
            else:
                logger.info(f'No active quest found for character_name={character_name}')

    def get_all_quests(self) -> List[Quest]:
        if self.is_cloud:
            response = self.table.scan()
            if 'Items' in response:
                items = response['Items']
                return [self.db_to_quest(item) for item in items]
        return []

    def delete_quest(self, character_name):
        if self.is_cloud:
            self.table.delete_item(Key={self.HASH_KEY: character_name})
            logger.info(f'Deleted quest for character_name={character_name}')

    @staticmethod
    def db_to_quest(response_item: dict) -> Quest:
        character_name = response_item['character_name']
        quest_hash = response_item.get('quest_hash')
        tasks_dict = json.loads(response_item.get('tasks', ''))
        tasks = [Task.from_dict(task_dict) for task_dict in tasks_dict]
        description = response_item.get('description')
        quest_id = response_item.get('quest_id')
        status = response_item.get('status')
        result = response_item.get('result')
        leader = response_item.get('leader')
        created_at_obj = response_item.get('created_at')
        created_at = datetime.fromisoformat(created_at_obj)
        updated_at_ts = response_item.get('updated_at_ts')
        return Quest(
            character_name=character_name,
            tasks=tasks,
            description=description,
            created_at=created_at,
            quest_id=quest_id,
            status=status,
            quest_hash=quest_hash,
            result=result,
            leader=leader,
            updated_at_ts=updated_at_ts,
        )
