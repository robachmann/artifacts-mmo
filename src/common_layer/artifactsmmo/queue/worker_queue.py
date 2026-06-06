import json
import os
from typing import Optional

import boto3

from artifactsmmo.extensions import CharacterSchemaExtension
from artifactsmmo.log.logger import logger


class WorkerQueue:
    MAX_DELAY_SECONDS = 900

    def __init__(self):
        self.queue_url = os.environ.get('WORKER_QUEUE_URL')
        self.sqs = boto3.client('sqs') if self.queue_url else None

    def send_tasks(self, character: CharacterSchemaExtension, delay_seconds: int, quest_id: Optional[str] = None):
        if not self.sqs:
            return

        delay_seconds = self._normalize_delay(delay_seconds)
        message_body = json.dumps(character.to_dict(), default=str)
        response = self.sqs.send_message(
            QueueUrl=self.queue_url,
            MessageBody=message_body,
            DelaySeconds=delay_seconds,
            MessageAttributes={'quest_id': {'StringValue': str(quest_id), 'DataType': 'String'}},
        )

        logger.info(
            'Invoked worker queue for '
            f'character={character.name}, '
            f'delay_seconds={delay_seconds}, '
            f'cooldown_expiration={character.cooldown_expiration}, '
            f'quest_id={quest_id}, '
            f'message_id={response.get("MessageId")}'
        )

    @classmethod
    def _normalize_delay(cls, delay_seconds: int) -> int:
        if delay_seconds < 0:
            return 0
        if delay_seconds > cls.MAX_DELAY_SECONDS:
            return cls.MAX_DELAY_SECONDS
        return delay_seconds
