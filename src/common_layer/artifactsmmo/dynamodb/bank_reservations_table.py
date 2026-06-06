from dataclasses import dataclass
from datetime import datetime, UTC
import os
from typing import Dict, List

import boto3
from botocore.exceptions import ClientError

from artifactsmmo.log.logger import logger


@dataclass
class BankReservation:
    task_id: str
    item_code: str
    quantity: int
    character: str


# Shape of the single DynamoDB item:
# {
#   "reservations": "all",                  # partition key
#   "data": {
#     "<task_id>": {
#       "<item_code>": {
#         "quantity": 5,
#         "character": "hero",
#         "added_at": "2026-..."
#       },
#       ...
#     },
#     ...
#   }
# }


class BankReservationsTable:
    PARTITION_KEY = 'reservations'
    PARTITION_VALUE = 'all'

    def __init__(self):
        table_name = os.environ.get('BANK_RESERVATIONS_TABLE_NAME')
        self.is_cloud = bool(table_name)

        if self.is_cloud:
            self.table = boto3.resource('dynamodb').Table(table_name)
            self._ensure_root_item_exists()

    def _ensure_root_item_exists(self):
        """Create the root item with an empty data map if it doesn't exist yet."""
        try:
            self.table.put_item(
                Item={self.PARTITION_KEY: self.PARTITION_VALUE, 'data': {}},
                ConditionExpression='attribute_not_exists(#pk)',
                ExpressionAttributeNames={'#pk': self.PARTITION_KEY},
            )
            logger.info('Initialised root bank reservations item')
        except ClientError as e:
            if e.response['Error']['Code'] == 'ConditionalCheckFailedException':
                pass  # Already exists, that's fine
            else:
                raise

    def _get_all_data(self) -> Dict:
        """Fetch the single item containing all reservations (consistent read)."""
        response = self.table.get_item(
            Key={self.PARTITION_KEY: self.PARTITION_VALUE},
            ConsistentRead=True,
        )
        return response.get('Item', {}).get('data', {})

    def add_reservations(self, reservation_id: str, equipment_map: Dict[str, int], character_name: str):
        if not (self.is_cloud and reservation_id and equipment_map and character_name):
            return

        added_at = datetime.now(UTC).isoformat()
        entries = {
            item_code: {'quantity': qty, 'character': character_name, 'added_at': added_at}
            for item_code, qty in equipment_map.items()
            if item_code and qty > 0
        }

        if not entries:
            return

        attr_names = {'#data': 'data', '#task_id': reservation_id}
        attr_values = {}
        set_parts = []

        for i, (item_code, qty_entry) in enumerate(entries.items()):
            item_ref = f'#item_{i}'
            val_ref = f':entry_{i}'
            attr_names[item_ref] = item_code
            attr_values[val_ref] = qty_entry
            set_parts.append(f'#data.#task_id.{item_ref} = {val_ref}')

        try:
            # Ensure the task map exists first
            self.table.update_item(
                Key={self.PARTITION_KEY: self.PARTITION_VALUE},
                UpdateExpression='SET #data.#task_id = if_not_exists(#data.#task_id, :empty)',
                ExpressionAttributeNames={'#data': 'data', '#task_id': reservation_id},
                ExpressionAttributeValues={':empty': {}},
            )
            self.table.update_item(
                Key={self.PARTITION_KEY: self.PARTITION_VALUE},
                UpdateExpression='SET ' + ', '.join(set_parts),
                ExpressionAttributeNames=attr_names,
                ExpressionAttributeValues=attr_values,
            )
            logger.info(
                f'Added {len(entries)} bank reservations for task_id={reservation_id}, character_name={character_name}, '
                f'items={list(entries.keys())}'
            )
        except ClientError as e:
            logger.error(f'Failed to add reservations for reservation_id={reservation_id}, character_name={character_name}, error={e}')

    def add_reservation(self, task_id: str, item_code: str, quantity: int, character_name: str):
        if not (self.is_cloud and task_id and item_code and quantity is not None):
            return

        entry = {
            'quantity': quantity,
            'character': character_name,
            'added_at': datetime.now(UTC).isoformat(),
        }
        try:
            # Ensure the task map exists first
            self.table.update_item(
                Key={self.PARTITION_KEY: self.PARTITION_VALUE},
                UpdateExpression='SET #data.#task_id = if_not_exists(#data.#task_id, :empty)',
                ExpressionAttributeNames={'#data': 'data', '#task_id': task_id},
                ExpressionAttributeValues={':empty': {}},
            )
            # Now safely write the item into the existing task map
            self.table.update_item(
                Key={self.PARTITION_KEY: self.PARTITION_VALUE},
                UpdateExpression='SET #data.#task_id.#item_code = :entry',
                ExpressionAttributeNames={'#data': 'data', '#task_id': task_id, '#item_code': item_code},
                ExpressionAttributeValues={':entry': entry},
            )
            logger.info(f'Added bank reservation for task_id={task_id}, character_name={character_name}, quantity={quantity}, item={item_code}')
        except ClientError as e:
            logger.error(f'Failed to add bank reservation for task_id={task_id}, item_code={item_code}, error={e}')

    def increment_reservation(self, task_id: str, item_code: str, quantity: int, character_name: str):
        if not (self.is_cloud and task_id and item_code and quantity is not None):
            return

        try:
            # Ensure task map exists
            self.table.update_item(
                Key={self.PARTITION_KEY: self.PARTITION_VALUE},
                UpdateExpression='SET #data.#task_id = if_not_exists(#data.#task_id, :empty)',
                ExpressionAttributeNames={'#data': 'data', '#task_id': task_id},
                ExpressionAttributeValues={':empty': {}},
            )
            # Ensure item_code map exists within the task
            self.table.update_item(
                Key={self.PARTITION_KEY: self.PARTITION_VALUE},
                UpdateExpression='SET #data.#task_id.#item_code = if_not_exists(#data.#task_id.#item_code, :empty)',
                ExpressionAttributeNames={'#data': 'data', '#task_id': task_id, '#item_code': item_code},
                ExpressionAttributeValues={':empty': {}},
            )
            response = self.table.update_item(
                Key={self.PARTITION_KEY: self.PARTITION_VALUE},
                UpdateExpression=(
                    'SET #data.#task_id.#item_code.#counter = if_not_exists(#data.#task_id.#item_code.#counter, :zero) + :increment, '
                    '#data.#task_id.#item_code.#character_name = if_not_exists(#data.#task_id.#item_code.#character_name, :character), '
                    '#data.#task_id.#item_code.added_at = if_not_exists(#data.#task_id.#item_code.added_at, :added_at)'
                ),
                ExpressionAttributeNames={
                    '#data': 'data',
                    '#task_id': task_id,
                    '#item_code': item_code,
                    '#counter': 'quantity',
                    '#character_name': 'character',
                },
                ExpressionAttributeValues={
                    ':increment': quantity,
                    ':zero': 0,
                    ':character': character_name,
                    ':added_at': datetime.now(UTC).isoformat(),
                },
                ReturnValues='ALL_NEW',
            )
            if 'Attributes' in response:
                new_quantity = int(response['Attributes'].get('data', {}).get(task_id, {}).get(item_code, {}).get('quantity', 0))
                logger.info(
                    f'Updated bank reservation for task_id={task_id}, item_code={item_code}, '
                    f'quantity={quantity}, character={character_name}, new_quantity={new_quantity}'
                )
        except ClientError as e:
            logger.error(f'Failed to increment bank reservation for task_id={task_id}, item_code={item_code}, error={e}')

    def get_reservations(self) -> List[BankReservation]:
        reservations: List[BankReservation] = []
        if not self.is_cloud:
            return reservations

        data = self._get_all_data()
        for task_id, items in data.items():
            for item_code, attrs in items.items():
                quantity = int(attrs.get('quantity', 0))
                character = attrs.get('character')
                reservations.append(BankReservation(task_id, item_code, quantity, character))

        logger.debug('Found %d bank reservations', len(reservations))
        return reservations

    def get_reservations_of_task(self, task_id: str) -> List[BankReservation]:
        reservations: List[BankReservation] = []
        if not self.is_cloud:
            return reservations

        data = self._get_all_data()
        task_items = data.get(task_id, {})
        for item_code, attrs in task_items.items():
            quantity = int(attrs.get('quantity', 0))
            character = attrs.get('character')
            reservations.append(BankReservation(task_id, item_code, quantity, character))

        logger.debug('Found %d bank reservations for task_id=%s', len(reservations), task_id)
        return reservations

    def delete_reservation(self, task_id: str, item_code: str):
        if not (self.is_cloud and task_id and item_code):
            return

        try:
            self.table.update_item(
                Key={self.PARTITION_KEY: self.PARTITION_VALUE},
                UpdateExpression='REMOVE #data.#task_id.#item_code',
                ConditionExpression='attribute_exists(#data.#task_id.#item_code)',
                ExpressionAttributeNames={'#data': 'data', '#task_id': task_id, '#item_code': item_code},
            )
            logger.info(f'Cleared bank reservation for task_id={task_id}, item_code={item_code}')
        except ClientError as e:
            if e.response['Error']['Code'] == 'ConditionalCheckFailedException':
                pass  # Item didn't exist, nothing to clean up
            else:
                logger.error(f'Failed to delete bank reservation for task_id={task_id}, item_code={item_code}, error={e}')
            return  # Either way, no point attempting the task map cleanup

        try:
            self.table.update_item(
                Key={self.PARTITION_KEY: self.PARTITION_VALUE},
                UpdateExpression='REMOVE #data.#task_id',
                ConditionExpression='#data.#task_id = :empty',
                ExpressionAttributeNames={'#data': 'data', '#task_id': task_id},
                ExpressionAttributeValues={':empty': {}},
            )
            logger.debug(f'Cleaned up empty task map for task_id={task_id}')
        except ClientError as e:
            if e.response['Error']['Code'] == 'ConditionalCheckFailedException':
                pass  # Task map still has other items, that's fine
            else:
                logger.error(f'Failed to clean up task map for task_id={task_id}, error={e}')
