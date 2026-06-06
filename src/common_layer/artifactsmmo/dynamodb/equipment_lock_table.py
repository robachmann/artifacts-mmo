from datetime import datetime, timedelta, UTC
import os
from typing import List

import boto3
from botocore.exceptions import ClientError

from artifactsmmo.log.logger import logger


class EquipmentLockTable:
    def __init__(self):
        self.is_cloud = os.environ.get('EQUIPMENT_LOCK_TABLE_NAME') is not None
        self.lock_id = 'equipment_lock'

        if self.is_cloud:
            dynamodb = boto3.resource('dynamodb')
            self.table_name = os.environ.get('EQUIPMENT_LOCK_TABLE_NAME')
            self.table = dynamodb.Table(self.table_name)

    def acquire_lock(self, locked_by: str) -> bool:
        if not self.is_cloud:
            return True

        now = datetime.now(UTC)
        now_ts = int(now.timestamp())
        delete_at_ts = int(now_ts + timedelta(minutes=20).total_seconds())

        try:
            response = self.table.update_item(
                Key={'lock_id': self.lock_id},
                UpdateExpression='SET locked_by = :locked_by, inserted_at = :inserted_at, delete_at_ts = :delete_at_ts',
                ConditionExpression='attribute_not_exists(lock_id) OR delete_at_ts < :now_ts',
                ExpressionAttributeValues={
                    ':locked_by': locked_by,
                    ':inserted_at': now.isoformat(),
                    ':delete_at_ts': delete_at_ts,
                    ':now_ts': now_ts,
                },
                ReturnValues='ALL_NEW',
                ReturnValuesOnConditionCheckFailure='ALL_OLD',
            )

            attributes = response.get('Attributes', {})
            db_locked_by = attributes.get('locked_by')
            if isinstance(db_locked_by, dict):
                db_locked_by = db_locked_by.get('S')

            if db_locked_by == locked_by:
                logger.info(f'🔐 Lock acquired by {locked_by}')
                return True

            logger.info(f'🔒 Lock cannot be acquired by character={locked_by}, already locked by character={db_locked_by}')
            return False

        except ClientError as e:
            error_code = e.response.get('Error', {}).get('Code')

            if error_code != 'ConditionalCheckFailedException':
                logger.error(f'Unexpected Error while acquiring lock: {e}')
                return False

            item = e.response.get('Item')  # type: ignore[index]
            if not item:
                logger.error(f'Unexpected response: {e.response}')
                return False

            db_locked_by = item.get('locked_by')
            if isinstance(db_locked_by, dict):
                db_locked_by = db_locked_by.get('S')

            if db_locked_by == locked_by:
                logger.info(f'🔐 Lock acquired by {locked_by}')
                return True

            logger.info(f'🔒 Lock cannot be acquired by character={locked_by}, already locked by character={db_locked_by}')
            return False

    def release_lock(self, locked_by: str):
        if not self.is_cloud:
            return

        try:
            self.table.delete_item(
                Key={'lock_id': self.lock_id},
                ConditionExpression='locked_by = :locked_by',
                ExpressionAttributeValues={':locked_by': locked_by},
            )
            logger.info(f'🔓 Lock released by {locked_by}')

        except ClientError as e:
            error_code = e.response.get('Error', {}).get('Code')

            if error_code != 'ConditionalCheckFailedException':
                logger.error(f'Unexpected Error while releasing lock: {e}')
                return

            item = e.response.get('Item')  # type: ignore[index]
            if not item:
                logger.info(f'No locks found to delete for character={locked_by}')
                return

            db_locked_by = item.get('locked_by')
            if db_locked_by == locked_by:
                logger.info(f'🔓 Lock released by {locked_by}')
            else:
                logger.warning(f'Lock cannot be released by character={locked_by}, already locked by character={db_locked_by}')

    def get_locked_characters(self, now: datetime) -> List[str]:
        locked_characters: List[str] = []

        if not self.is_cloud:
            return locked_characters

        response = self.table.scan()
        items = response.get('Items', [])

        logger.debug('Found %d locks', len(items))

        now_ts = int(now.timestamp())

        for reservation in items:
            delete_at_ts = int(reservation.get('delete_at_ts', 0))
            if delete_at_ts > now_ts:
                locked_by = reservation.get('locked_by')
                if locked_by:
                    locked_characters.append(locked_by)

        return locked_characters
