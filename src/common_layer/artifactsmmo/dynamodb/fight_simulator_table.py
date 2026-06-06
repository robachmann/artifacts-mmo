from dataclasses import asdict, dataclass
from datetime import datetime, timedelta, UTC
from enum import StrEnum
import os
import random
import string
from typing import List, Optional

import boto3 as boto3

from artifactsmmo.fights.combat_result import CombatResultDTO, CombatResults
from artifactsmmo.log.logger import logger


class FightSimulatorStatus(StrEnum):
    NEW = 'NEW'
    RUNNING = 'RUNNING'
    FINISHED = 'FINISHED'
    FAILED = 'FAILED'


@dataclass
class FightSimulatorRecord:
    fight_simulator_id: str
    status: FightSimulatorStatus
    participants: List[str]
    character_name: str
    monster_code: str
    exclude_items: List[str]
    force_utilities: bool
    sort_function: str
    quest_id: str
    created_at: datetime
    combat_result: Optional[CombatResultDTO] = None


class FightSimulatorTable:
    def __init__(self):
        table_name = os.environ.get('FIGHT_SIMULATOR_TABLE_NAME')
        self.is_cloud = bool(table_name)

        if self.is_cloud:
            self.table = boto3.resource('dynamodb').Table(table_name)

    def insert(
        self,
        participants: List[str],
        character_name: str,
        monster_code: str,
        exclude_items: Optional[List[str]] = None,
        force_utilities: bool = False,
        sort_function: Optional[str] = None,
        quest_id: Optional[int] = None,
    ) -> str:
        fight_simulator_id = ''.join(random.choices(string.ascii_letters, k=5))
        created_at = datetime.now(UTC)
        delete_at = created_at + timedelta(days=7)
        item = {
            'fight_simulator_id': fight_simulator_id,
            'status': FightSimulatorStatus.NEW,
            'participants': participants,
            'character_name': character_name,
            'monster_code': monster_code,
            'exclude_items': exclude_items or [],
            'force_utilities': force_utilities,
            'sort_function': sort_function or '',
            'quest_id': quest_id or '',
            'created_at': created_at.isoformat(),
            'last_updated_at_ts': int(created_at.timestamp()),
            'delete_at_ts': int(delete_at.timestamp()),
        }
        self.table.put_item(Item=item)
        return fight_simulator_id

    def update_status(self, record: FightSimulatorRecord, new_status: FightSimulatorStatus):
        if not self.is_cloud:
            return

        self.table.update_item(
            Key={'fight_simulator_id': record.fight_simulator_id},
            UpdateExpression='SET #status = :status, last_updated_at_ts = :last_updated_at_ts',
            ExpressionAttributeNames={'#status': 'status'},
            ExpressionAttributeValues={':status': new_status, ':last_updated_at_ts': int(datetime.now(UTC).timestamp())},
        )
        record.status = new_status

    def submit_result(self, record: FightSimulatorRecord, sim_result: CombatResults):
        if not self.is_cloud:
            return

        now_ts = int(datetime.now(UTC).timestamp())
        dto = CombatResultDTO.from_combat_results(sim_result)
        duration_str = str(timedelta(seconds=int(now_ts - record.created_at.timestamp())))

        self.table.update_item(
            Key={'fight_simulator_id': record.fight_simulator_id},
            UpdateExpression='SET #status = :status, last_updated_at_ts = :ts, combat_result = :result, #duration = :d',
            ExpressionAttributeNames={'#status': 'status', '#duration': 'duration'},
            ExpressionAttributeValues={':status': FightSimulatorStatus.FINISHED, ':ts': now_ts, ':result': asdict(dto), ':d': duration_str},
        )
        logger.info(f'Submitted fight result of fight_simulator_id={record.fight_simulator_id}')

    def get_record(self, fight_simulator_id) -> Optional[FightSimulatorRecord]:
        if self.is_cloud:
            response = self.table.get_item(Key={'fight_simulator_id': fight_simulator_id})
            if 'Item' in response:
                return self.db_to_obj(response['Item'])

    @staticmethod
    def db_to_obj(response_item: dict) -> FightSimulatorRecord:
        combat_result_raw = response_item.get('combat_result')

        return FightSimulatorRecord(
            fight_simulator_id=response_item['fight_simulator_id'],
            status=response_item['status'],
            participants=response_item['participants'],
            character_name=response_item['character_name'],
            monster_code=response_item['monster_code'],
            quest_id=response_item['quest_id'],
            force_utilities=response_item.get('force_utilities', False),
            exclude_items=response_item.get('exclude_items', []),
            sort_function=response_item.get('sort_function', ''),
            created_at=datetime.fromisoformat(response_item.get('created_at', None)),
            combat_result=(CombatResultDTO.from_dict(combat_result_raw) if combat_result_raw else None),
        )
