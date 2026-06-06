from dataclasses import dataclass
from datetime import datetime, UTC
from decimal import Decimal
import os
from typing import List

import boto3 as boto3


@dataclass
class ItemWithdrawalDate:
    item_code: str
    last_withdrawn_at: datetime


class WithdrawTable:
    def __init__(self):
        table_name = os.environ.get('WITHDRAW_TABLE_NAME')
        self.is_cloud = bool(table_name)

        if self.is_cloud:
            self.table = boto3.resource('dynamodb').Table(table_name)

    def update(self, item_code: str):
        if self.is_cloud and item_code:
            now = Decimal(str(int(datetime.now(UTC).timestamp())))
            self.table.update_item(
                Key={'item': item_code},
                UpdateExpression='SET last_withdrawn_at = :now',
                ExpressionAttributeValues={':now': now},
            )

    def get_all_stats(self) -> List[ItemWithdrawalDate]:
        if self.is_cloud:
            response = self.table.scan()
            if 'Items' in response:
                return [self.db_to_obj(item) for item in response['Items']]
        return []

    @staticmethod
    def db_to_obj(response_item: dict) -> ItemWithdrawalDate:
        item_code = response_item['item']
        last_withdrawn_at_ts = float(response_item.get('last_withdrawn_at', 0))
        last_withdrawn_at = datetime.fromtimestamp(last_withdrawn_at_ts, UTC)
        return ItemWithdrawalDate(item_code, last_withdrawn_at)
