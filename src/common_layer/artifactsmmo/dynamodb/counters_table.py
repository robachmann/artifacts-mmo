from datetime import datetime, UTC
import os

import boto3 as boto3


class CountersTable:
    def __init__(self):
        if os.environ.get('AWS_LAMBDA_FUNCTION_NAME') is None:
            self.is_cloud = False
        else:
            self.is_cloud = True
            self.dynamodb = boto3.client('dynamodb')
            self.table_name = os.environ.get('COUNTERS_TABLE_NAME')

    def increment(self, code: str, type: str, quantity: int = 1, duration: int = 0):
        if self.is_cloud:
            now_str = datetime.now(UTC).replace(microsecond=0).isoformat()
            self.dynamodb.update_item(
                TableName=self.table_name,
                Key={'code': {'S': code}, 'type': {'S': type}},
                UpdateExpression='ADD #counter :increment, #durationinc :durationinc SET first_at = if_not_exists(first_at, :first_at), last_at = :last_at',
                ExpressionAttributeNames={'#counter': 'quantity', '#durationinc': 'duration'},
                ExpressionAttributeValues={
                    ':increment': {'N': str(quantity)},
                    ':durationinc': {'N': str(duration)},
                    ':first_at': {'S': now_str},
                    ':last_at': {'S': now_str},
                },
            )

    def get_all_drops(self):
        response = self.dynamodb.scan(TableName=self.table_name)

        result_list = []
        for db_item in response.get('Items', []):
            if db_item.get('type', {}).get('S').startswith('drops.'):
                result_list.append(db_item)
        return result_list

    def get_counter(self, code: str, type: str):
        if self.is_cloud:
            response = self.dynamodb.query(
                TableName=self.table_name,
                KeyConditionExpression='#codekey = :codekey AND #typekey = :typekey',
                ExpressionAttributeNames={'#codekey': 'code', '#typekey': 'type'},
                ExpressionAttributeValues={
                    ':codekey': {'S': str(code)},
                    ':typekey': {'S': str(type)},
                },
            )

            for item in response.get('Items', []):
                return item
