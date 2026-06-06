from collections import defaultdict
from datetime import datetime, UTC
import random
import string
from typing import Dict, List, Set

from artifactsmmo.log.logger import logger
from artifactsmmo.service.tasks import Task
from artifactsmmo.service.until import Status


class Quest:
    def __init__(
        self,
        character_name: str,
        tasks: List[Task],
        description: str = None,
        created_at: datetime = None,
        quest_id: str = None,
        status: str = None,
        quest_hash: str = None,
        result: str = None,
        leader: str = None,
        updated_at_ts: float = None,
    ):
        self.quest_id = quest_id
        self.character_name = character_name
        self.tasks: List[Task] = tasks
        self.description = description
        self.created_at = created_at if created_at else datetime.now(UTC)
        self.status = status
        self.quest_hash = quest_hash
        self.result = result  # success, cancelled, failure
        self.leader = leader
        self.updated_at_ts = updated_at_ts

    @classmethod
    def from_dict(cls, json_body):
        tasks: List[Task] = []
        tasks_json = json_body.get('tasks', [])
        for task_json in tasks_json:
            tasks.append(Task.from_dict(task_json))

        created_at_str = json_body['created_at']
        created_at = None
        if created_at_str is not None:
            created_at = datetime.fromisoformat(created_at_str)

        return cls(
            character_name=json_body['character_name'],
            tasks=tasks,
            description=json_body['description'],
            created_at=created_at,
            quest_id=json_body.get('quest_id'),
            quest_hash=json_body.get('quest_hash'),
            result=json_body.get('result'),
            status=json_body.get('status'),
            updated_at_ts=json_body.get('updated_at_ts'),
        )

    def to_dict(self) -> dict:
        return {
            'quest_id': self.quest_id,
            'character_name': self.character_name,
            'description': self.description,
            'created_at': self.created_at.isoformat(),
            'tasks': [t.to_dict() for t in self.tasks],
            'status': self.status,
            'quest_hash': self.quest_hash,
            'result': self.result,
            'updated_at_ts': self.updated_at_ts,
        }

    @staticmethod
    def generate_quest_id():
        return ''.join(random.choices(string.ascii_letters, k=8))

    def generate_description(self):
        log_summary: Dict[str, int] = defaultdict(int)

        for task in self.tasks:
            if task.extra.get('quantity'):
                quantity = task.extra['quantity'] * task.ttl
            else:
                quantity = task.ttl
            item = task.extra.get('item')
            log_key = f'{task.action} {item}' if item else f'{task.action}'
            log_summary[log_key] += quantity

        try:
            keys_to_delete = []
            for log_key in log_summary.keys():
                if log_key.startswith('craft-recipe'):
                    gather_key = log_key.replace('craft-', 'gather-')
                    keys_to_delete.append(gather_key)

            for key in keys_to_delete:
                log_summary.pop(key, None)

        except Exception as e:
            logger.error(e)

        descriptions: List[str] = []
        for action, times in log_summary.items():
            if not (
                action.startswith('unequip')
                or action.startswith('equip')
                or action.startswith('deposit')
                or action.startswith('move')
                or action == 'ensure-inventory'
                or action == 'reload-character'
                or action == 'sleep'
            ):
                if times > 1:
                    descriptions.append(f'{action} ({times}x)')
                else:
                    descriptions.append(f'{action}')

        self.description = ', '.join(descriptions)

    def compact_task_list(self, character_name: str, finished_task_ids: Set[str]):
        result = []
        valid_until_statuses = {Status.Todo, Status.Ongoing}
        excluded_actions = {'sleep', 'multi-character-fight'}

        for task in self.tasks:
            # Fast path: skip immediately if finished
            if task.task_id in finished_task_ids:
                continue

            # Skip if ttl == 0 and action is excluded
            if task.ttl == 0 and task.action in excluded_actions:
                continue

            until = task.until
            leader = task.extra.get('leader')

            # Check core inclusion logic
            if task.ttl > 0:
                if until is None or until.status != Status.Interrupted:
                    result.append(task)
                    continue

            if until and until.status in valid_until_statuses:
                result.append(task)
                continue

            if leader == character_name:
                result.append(task)
                continue

        self.tasks = result

    def is_locked(self):
        return self.status and (self.status.startswith('boss-fight') or self.status.startswith('parallel-item-craft'))
