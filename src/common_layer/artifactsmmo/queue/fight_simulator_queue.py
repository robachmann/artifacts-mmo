import json
import os
from typing import Optional

import boto3

from artifactsmmo.log.logger import logger


class FightSimulatorQueue:
    def __init__(self):
        self.queue_url = os.environ.get('FIGHT_SIMULATOR_QUEUE_URL')
        self.sqs = boto3.client('sqs') if self.queue_url else None

    def invoke_fight_simulator(self, fight_simulator_id: str):
        if not self.sqs:
            return

        message_body = json.dumps(dict(fight_simulator_id=fight_simulator_id))
        response = self.sqs.send_message(QueueUrl=self.queue_url, MessageBody=message_body)

        logger.info(f'Invoked fight simulator with fight_simulator_id={fight_simulator_id}, message_id={response.get("MessageId")}')
