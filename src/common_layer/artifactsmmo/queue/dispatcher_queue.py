from dataclasses import asdict, dataclass
from enum import StrEnum
import json
import os
from typing import Any, List

import boto3

from artifactsmmo.log.logger import logger
from artifactsmmo.service.helpers import ShoppingBasket


class MessageType(StrEnum):
    INVOKE = 'invoke'
    RESET = 'reset'
    RESTART = 'restart'
    SOLVE = 'solve'
    RELEASE = 'release'
    JOIN = 'join'
    RESET_QUEST_JOINERS = 'reset-quest-joiners'
    BUY = 'buy'
    DELIVER = 'deliver'
    PATCH = 'patch'


@dataclass(slots=True)
class SolveTasksPayload:
    character_name: str
    count: int


@dataclass(slots=True)
class PatchTasksPayload:
    character: str
    parameters: list[str]


@dataclass(slots=True)
class BuyPayload:
    quantity: int
    item: str
    order_id: str


class DispatcherQueue:
    def __init__(self):
        self.queue_url = os.environ.get('DISPATCHER_QUEUE_URL')
        self.sqs = boto3.client('sqs') if self.queue_url else None

    def _send(self, message_type: MessageType, body: Any):
        if not self.sqs:
            return

        if hasattr(body, '__dataclass_fields__'):
            body = asdict(body)

        message_body = json.dumps(body)

        self.sqs.send_message(
            QueueUrl=self.queue_url,
            MessageBody=message_body,
            MessageAttributes={'message_type': {'StringValue': message_type, 'DataType': 'String'}},
        )

        logger.info(f'Sent dispatcher message, type={message_type}, body={body}')

    def invoke(self, character_list: List[str] | None = None):
        self._send(MessageType.INVOKE, character_list or [])

    def reset(self, parameters: List[str] | None = None):
        self._send(MessageType.RESET, parameters or [])

    def restart(self, parameters: List[str] | None = None):
        self._send(MessageType.RESTART, parameters or [])

    def release(self, parameters: List[str] | None = None):
        self._send(MessageType.RELEASE, parameters or [])

    def join(self, parameters: List[str] | None = None):
        self._send(MessageType.JOIN, parameters or [])

    def reset_quest_joiners(self):
        self._send(MessageType.RESET_QUEST_JOINERS, [])

    def deliver_food_tasks(self, character_name: str):
        self._send(MessageType.DELIVER, character_name)

    def solve_tasks(self, character_name: str, count: int):
        if not character_name or count <= 0:
            return

        payload = SolveTasksPayload(
            character_name=character_name,
            count=count,
        )

        self._send(MessageType.SOLVE, payload)

    def buy(self, basket: ShoppingBasket):
        payload = BuyPayload(
            quantity=basket.quantity,
            item=basket.item,
            order_id=basket.order_id,
        )

        self._send(MessageType.BUY, payload)

    def patch_tasks(self, character_name: str, parameters: List[str]):
        payload = PatchTasksPayload(
            character=character_name,
            parameters=parameters,
        )

        self._send(MessageType.PATCH, payload)
