from dataclasses import dataclass
from datetime import datetime, timedelta
from decimal import Decimal
import os
from typing import List, Optional

import boto3 as boto3
from botocore.exceptions import ClientError

from artifactsmmo.log.logger import logger
from artifactsmmo.models import LogSchema, LogType


@dataclass
class LogLine:
    created_ts: Optional[int] = None
    character_name: Optional[str] = None
    action: Optional[str] = None
    skill: Optional[str] = None
    subject: Optional[str] = None
    xp_gained: Optional[int] = None
    quantity: Optional[int] = None
    cooldown: Optional[int] = None

    @classmethod
    def from_db_dict(cls, data: dict):
        return cls(
            created_ts=int(data['created_ts']) if 'created_ts' in data else None,
            character_name=data.get('character_name'),
            action=data.get('action'),
            skill=data.get('skill'),
            subject=data.get('subject'),
            xp_gained=int(data['xp_gained']) if 'xp_gained' in data else None,
            quantity=int(data['quantity']) if 'quantity' in data else None,
            cooldown=int(data['cooldown']) if 'cooldown' in data else None,
        )

class LogsTable:
    HASH_KEY = 'character_name'
    RANGE_KEY = 'created_ts'

    def __init__(self):
        table_name = os.environ.get('LOGS_TABLE_NAME')
        self.is_cloud = bool(table_name)
        self.logs_ttl = int(timedelta(days=2).total_seconds())

        if self.is_cloud:
            self.table = boto3.resource('dynamodb').Table(table_name)

    def get_logs(self, character_name, from_dt: datetime, to_dt: datetime) -> List[LogLine]:
        result: List[LogLine] = []
        if self.is_cloud:
            from_timestamp = Decimal(str(from_dt.timestamp()))
            to_timestamp = Decimal(str(to_dt.timestamp()))

            response = self.table.query(
                KeyConditionExpression='#pk = :character_name AND #sk BETWEEN :from_timestamp AND :to_timestamp',
                ExpressionAttributeNames={'#pk': self.HASH_KEY, '#sk': self.RANGE_KEY},
                ExpressionAttributeValues={
                    ':character_name': character_name,
                    ':from_timestamp': from_timestamp,
                    ':to_timestamp': to_timestamp,
                },
            )

            result_items = response['Items']
            logger.info(f'Found {len(result_items)} logs for {character_name} between {from_timestamp} and {to_timestamp}')

            for log in result_items:
                result.append(LogLine.from_db_dict(log))

        return result

    def upload_logs(self, logs: List[LogSchema]) -> List[LogSchema]:
        inserted_logs: List[LogSchema] = []
        if self.is_cloud:
            for log in logs:
                created_at = log.created_at
                if created_at:
                    character_name = log.character
                    action_str = str(log.type)
                    created_ts = int(created_at.timestamp())
                    delete_at_ts = created_ts + self.logs_ttl
                    log_dict = log.to_dict()
                    cooldown = log.cooldown
                    subject = None
                    quantity = None
                    xp_gained = None
                    skill = None

                    match log.type:
                        case LogType.DEPOSIT_GOLD:
                            content = log_dict.get('content', {})
                            quantity = content.get('golds')

                        case (
                            LogType.SELL_GE
                            | LogType.BUY_GE
                            | LogType.DEPOSIT_ITEM
                            | LogType.CRAFTING
                            | LogType.WITHDRAW_ITEM
                            | LogType.EQUIP
                            | LogType.UNEQUIP
                            | LogType.RECYCLING
                            | LogType.USE
                            | LogType.SPAWN
                            | LogType.BUY_NPC
                            | LogType.SELL_NPC
                        ):
                            content = log_dict.get('content', {})
                            subject = content.get('item')
                            quantity = content.get('quantity')

                            if 'xp_gained' in content:
                                skill = content.get('skill')
                                xp_gained = content.get('xp_gained')

                        case LogType.FIGHT:
                            skill = 'fight'
                            content = log_dict.get('content', {}).get('fight', {})
                            subject = content.get('opponent')
                            fight_result = content.get('result')

                            if fight_result == 'loss':
                                action_str = 'fight-lost'

                            xp_gained = 0
                            characters = content.get('characters', [])
                            for character in characters:
                                xp_gained += character.get('xp', 0)

                        case LogType.GATHERING:
                            content = log_dict.get('content', {}).get('gathering', {})
                            subject = content.get('resource')

                            if 'xp_gained' in content:
                                skill = content.get('skill')
                                xp_gained = content.get('xp_gained')

                    item = {
                        self.HASH_KEY: character_name,
                        self.RANGE_KEY: created_ts,
                        'created_at': str(created_at),
                        'delete_at_ts': delete_at_ts,
                        'action': action_str,
                    }

                    if subject is not None:
                        item['subject'] = str(subject)

                    if quantity is not None:
                        item['quantity'] = quantity

                    if xp_gained is not None:
                        item['xp_gained'] = xp_gained

                    if skill is not None:
                        item['skill'] = str(skill)

                    if cooldown is not None:
                        item['cooldown'] = cooldown

                    try:
                        self.table.put_item(
                            Item=item,
                            ConditionExpression='attribute_not_exists(#hk) AND attribute_not_exists(#rk)',
                            ExpressionAttributeNames={'#hk': self.HASH_KEY, '#rk': self.RANGE_KEY},
                        )
                        inserted_logs.append(log)
                    except ClientError as e:
                        if e.response['Error']['Code'] != 'ConditionalCheckFailedException':
                            logger.error(f'Error writing to DynamoDB: {e}')
        return inserted_logs
