from dataclasses import dataclass
from decimal import Decimal
import os
from typing import List

import boto3 as boto3
from botocore.exceptions import ClientError

from artifactsmmo.fights.fight_bundle import self_round
from artifactsmmo.log.logger import logger


@dataclass
class SkillStat:
    level: int
    subject: str
    gained_xp: int


class SkillStatsTable:
    HASH_KEY = 'action.skill'
    RANGE_KEY = 'level.subject'

    def __init__(self):
        table_name = os.environ.get('SKILL_STATS_TABLE_NAME')
        self.is_cloud = bool(table_name)

        if self.is_cloud:
            self.table = boto3.resource('dynamodb').Table(table_name)

    def put_skill_stats(
        self,
        action: str,
        skill: str,
        level: int,
        subject: str,
        gained_xp: int,
        cooldown: int,
        subject_level: int,
        wisdom: int = None,
        count: int = 1,
    ):
        if self.is_cloud:
            if not wisdom:
                wisdom = 0

            normalized_xp = gained_xp / (1 + wisdom * 0.001) / count
            normalized_xp_decimal = Decimal(str(round(normalized_xp, 1)))

            action_skill = f'{action}.{skill}'
            level_subject = f'{level}.{subject}'

            item = {
                self.HASH_KEY: action_skill,
                self.RANGE_KEY: level_subject,
                'skill_level': level,
                'subject': subject,
                'subject_level': subject_level,
                'gained_xp': normalized_xp_decimal,
            }

            try:
                self.table.put_item(
                    Item=item,
                    ConditionExpression='attribute_not_exists(#hk) AND attribute_not_exists(#rk)',
                    ExpressionAttributeNames={
                        '#hk': self.HASH_KEY,
                        '#rk': self.RANGE_KEY,
                    },
                )

                logger.info(
                    f'Inserted skill-stats for {self.HASH_KEY}={action_skill}, {self.RANGE_KEY}={level_subject}, '
                    f'subject_level={subject_level}, gained_xp={normalized_xp_decimal}, cooldown={cooldown}'
                )

            except ClientError as e:
                if e.response['Error']['Code'] != 'ConditionalCheckFailedException':
                    logger.error(f'Error writing to DynamoDB: {e}')

    def get_skill_stats(self, action: str, skill: str, skill_level: int, subject_filter: str) -> List[SkillStat]:
        action_skill = f'{action}.{skill}'
        return_list: List[SkillStat] = []
        if self.is_cloud:
            level_subject = f'{skill_level}.{subject_filter}'
            response = self.table.query(
                KeyConditionExpression='#pk = :pkval AND #sk = :skval',
                ExpressionAttributeNames={'#pk': self.HASH_KEY, '#sk': self.RANGE_KEY},
                ExpressionAttributeValues={':pkval': action_skill, ':skval': level_subject},
            )

            result_items = response['Items']
            logger.info(f'Found {len(result_items)} stats for {self.HASH_KEY}={action_skill} and {self.RANGE_KEY}={level_subject}')

            for item in result_items:
                skill_level = int(item['skill_level'])
                gained_xp = self_round(item['gained_xp'])
                subject = item['subject']
                if not subject_filter or (subject_filter and subject == subject_filter):
                    return_list.append(SkillStat(level=skill_level, subject=subject, gained_xp=gained_xp))

        return return_list
