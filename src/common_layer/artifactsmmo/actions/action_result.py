from collections import defaultdict
from datetime import datetime, timedelta, UTC
import re
from typing import Dict, List, Optional

from artifactsmmo.extensions import CharacterSchemaExtension
from artifactsmmo.log.logger import logger
from artifactsmmo.models import CharacterSchema, CooldownSchema
from artifactsmmo.service.tasks import Task


class ActionResult:
    def __init__(self):
        self.cooldown_expiration = datetime.now(UTC)
        self.repeat_task = False
        self.skip_task = False
        self.abort_quest = False
        self.abort_reason = None
        self.new_tasks: List[Task] = []
        self.character: Optional[CharacterSchemaExtension] = None
        self.drops: Dict[str, int] = defaultdict(int)

    def append(self, task: Task):
        self.new_tasks.append(task)

    def extend(self, tasks: List[Task]):
        for task in tasks:
            self.append(task)

    def abort(self, reason: str = None):
        self.abort_quest = True
        if reason:
            self.abort_reason = reason

    def skip(self):
        self.skip_task = True

    def repeat(self):
        self.repeat_task = True

    def update_character(self, character: CharacterSchema = None):
        if character:
            self.character = CharacterSchemaExtension(character)
            self.cooldown_expiration = character.cooldown_expiration

    def update_expiration(self, cooldown: CooldownSchema = None, seconds: int = None, error: dict = None):
        if cooldown and cooldown.expiration:
            self.cooldown_expiration = cooldown.expiration
        elif error:
            if isinstance(error, str):
                logger.error(f'Cannot extract error message from: {error}. Setting cooldown expiration to 1min.')
                self.cooldown_expiration = datetime.now(UTC) + timedelta(minutes=1)
            else:
                error_message = error.get('message')
                if error_message:
                    number = re.findall(r'\d+\.\d+', error_message)
                    cooldown_time = float(number[0]) if number else None
                    if cooldown_time is not None:
                        self.cooldown_expiration = datetime.now(UTC) + timedelta(seconds=cooldown_time)
        elif seconds is not None:
            self.cooldown_expiration = datetime.now(UTC) + timedelta(seconds=seconds)
