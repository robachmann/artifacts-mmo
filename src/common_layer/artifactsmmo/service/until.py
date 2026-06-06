from datetime import datetime, timedelta, UTC
import enum
from typing import Dict


class Status(enum.StrEnum):
    Todo = 'todo'
    Ongoing = 'ongoing'
    Interrupted = 'interrupted'
    Cancelled = 'cancelled'
    Done = 'done'


class Until:
    def __init__(
        self,
        drop_count: int = None,
        drop_item: str = None,
        date_time: datetime = None,
        timespan: timedelta = None,
        status: Status = None,
        progress: int = None,
        skill_name: str = None,
        skill_level: int = None,
        achievement_code: str = None,
    ):
        self.drop_count: int = drop_count
        self.drop_item: str = drop_item
        if not date_time and timespan:
            date_time = datetime.now(UTC) + timespan
        self.date_time: datetime = date_time
        self.status: Status = status if status else Status.Todo
        self.progress: int = progress if progress else 0
        self.skill_name: str = skill_name
        self.skill_level: int = skill_level
        self.achievement_code: str = achievement_code

    @classmethod
    def from_dict(cls, json_dict: dict):
        dt_str = json_dict.get('date_time')
        dt = None
        if dt_str is not None:
            dt = datetime.fromisoformat(dt_str)

        return cls(
            drop_count=json_dict['drop_count'] if 'drop_count' in json_dict else None,
            drop_item=json_dict['drop_item'] if 'drop_item' in json_dict else None,
            date_time=dt,
            status=Status(json_dict['status']),
            progress=json_dict['progress'],
            skill_name=json_dict.get('skill_name'),
            skill_level=json_dict.get('skill_level'),
            achievement_code=json_dict.get('achievement_code'),
        )

    def to_dict(self) -> dict:
        return_dict: Dict[str, Status | int | str] = {'status': self.status, 'progress': self.progress}

        if self.drop_count is not None:
            return_dict['drop_count'] = self.drop_count
        if self.drop_item is not None:
            return_dict['drop_item'] = self.drop_item
        if self.date_time is not None:
            return_dict['date_time'] = self.date_time.isoformat()
        if self.skill_name is not None:
            return_dict['skill_name'] = self.skill_name
        if self.skill_level is not None:
            return_dict['skill_level'] = self.skill_level
        if self.achievement_code is not None:
            return_dict['achievement_code'] = self.achievement_code

        return return_dict

    def to_str(self):
        return (
            f"{{'status': '{self.status.value}', 'drop_item': '{self.drop_item}',  "
            f"'drop_count': '{self.drop_count}', 'progress': '{self.progress}', "
            f"'skill_name': '{self.skill_name}', 'skill_level': '{self.skill_level}', "
            f"'achievement_code': '{self.achievement_code}', 'date_time': '{self.date_time}'}}"
        )

    def to_pretty_str(self):
        if self.drop_item and self.drop_count:
            return f'{self.drop_item} ({self.progress}/{self.drop_count})'
        elif self.date_time:
            return self.date_time
        elif self.skill_name and self.skill_level:
            return f'{self.skill_name}: {self.skill_level}'
        elif self.achievement_code:
            return self.achievement_code
        else:
            return ''
