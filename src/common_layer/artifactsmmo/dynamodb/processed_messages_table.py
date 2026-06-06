from datetime import timedelta
import os
import time

import boto3 as boto3
from botocore.exceptions import ClientError

from artifactsmmo.log.logger import logger


class ProcessedMessagesTable:
    def __init__(self):
        if os.environ.get('AWS_LAMBDA_FUNCTION_NAME') is None:
            self.is_cloud = False
        else:
            self.is_cloud = True
            table_name = os.environ.get('PROCESSED_MESSAGES_TABLE_NAME')
            if table_name:
                self.table = boto3.resource('dynamodb').Table(table_name)
        self.delete_in_seconds = int(timedelta(days=1).total_seconds())

    def track_processed_message(self, message_id: str) -> bool:
        if self.is_cloud:
            now_ts = int(time.time())
            delete_at_ts = now_ts + self.delete_in_seconds

            try:
                self.table.put_item(
                    Item={'message_id': message_id, 'delete_at_ts': delete_at_ts},
                    ConditionExpression='attribute_not_exists(message_id)',
                )
                logger.info(f'Added message_id={message_id} to list of processed messages at={now_ts}, delete_at={delete_at_ts}')
                return True
            except ClientError as e:
                if e.response['Error']['Code'] == 'ConditionalCheckFailedException':
                    logger.warning(f'Received message_id={message_id} which has already been processed.')
                    return False
        return True
