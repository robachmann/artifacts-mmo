from dataclasses import dataclass
from datetime import datetime, timedelta, UTC
from itertools import groupby
import os
from typing import Dict, List

import boto3 as boto3

from artifactsmmo.log.logger import logger


@dataclass
class SkipEvent:
    character_name: str
    event_content: str


class SkipEventsTable:
    def __init__(self):
        if os.environ.get('AWS_LAMBDA_FUNCTION_NAME') is None:
            self.is_cloud = False
        else:
            self.is_cloud = True
            self.dynamodb = boto3.client('dynamodb')
            self.table_name = os.environ.get('SKIP_EVENTS_TABLE_NAME')

    def add_skip_entry(self, character_name: str, event_content: str):
        if self.is_cloud:
            now_ts = int(datetime.now(UTC).timestamp())
            delete_at_ts = now_ts + timedelta(hours=2).total_seconds()
            item = {
                'character_name': {'S': character_name},
                'event_name': {'S': event_content},
                'delete_at_ts': {'N': str(delete_at_ts)},
            }
            self.dynamodb.put_item(TableName=self.table_name, Item=item)
            logger.info(f'Added skip_event entry for character_name={character_name}, event_content={event_content}')

    def get_all_skip_event_entries(self) -> Dict[str, List[str]]:
        skip_event_entries = []
        if self.is_cloud:
            response = self.dynamodb.scan(TableName=self.table_name)
            if 'Items' in response:
                skips = response['Items']
                now_ts = datetime.now(UTC).timestamp()
                for skip in skips:
                    character_name = skip.get('character_name', {}).get('S')
                    event_name = skip.get('event_name', {}).get('S')
                    delete_at_ts = int(skip.get('delete_at_ts', {}).get('N', '0'))
                    if delete_at_ts > now_ts:
                        skip_event_entries.append(SkipEvent(character_name, event_name))

        sorted_events = sorted(skip_event_entries, key=lambda e: e.character_name)
        return {
            character_name: [e.event_content for e in group] for character_name, group in groupby(sorted_events, key=lambda e: e.character_name)
        }

    def delete_skip_entry(self, character_name: str, event_name: str):
        if self.is_cloud:
            try:
                self.dynamodb.delete_item(
                    TableName=self.table_name, Key={'character_name': {'S': character_name}, 'event_name': {'S': event_name}}
                )
                logger.info(f'Cleared skip event entry for character_name={character_name} ')
            except Exception as e:
                logger.warning(e)
