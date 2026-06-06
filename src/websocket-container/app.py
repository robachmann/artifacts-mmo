import asyncio
from dataclasses import dataclass
from datetime import datetime, UTC
import json
import os
import ssl
from typing import List

from dotenv import load_dotenv
import websockets

from artifactsmmo.log.logger import logger
from artifactsmmo.webhook.client import WebhookClient


@dataclass
class WebsocketConfig:
    token: str
    websocket_url: str
    webhook_url: str
    skip_ssl_verification: bool = False
    log_test_messages: bool = False
    subscriptions: List[str] = None


class WebsocketClient:
    def __init__(self):
        load_dotenv()
        self.config: WebsocketConfig = self.create_config()
        self.webhook_client = WebhookClient()
        self.message = {'token': self.config.token, 'subscriptions': self.config.subscriptions}

    def start_websocket(self):
        if self.config.subscriptions:
            asyncio.run(self.receive_messages())
        else:
            logger.error(
                'No subscriptions supplied, please set environment variable "SUBSCRIPTIONS" with '
                'subscription codes from this table: https://docs.artifactsmmo.com/members/websockets'
            )

    async def receive_messages(self):
        if self.config.skip_ssl_verification:
            ssl_context = ssl._create_unverified_context()
        else:
            ssl_context = ssl.create_default_context()
        async with websockets.connect(self.config.websocket_url, ssl=ssl_context) as websocket:
            await websocket.send(json.dumps(self.message))

            logger.info(f'▫️ Websocket connection established and subscribed to events of type: {self.config.subscriptions}')
            try:
                while True:
                    message_received = await websocket.recv()
                    message_received = json.loads(message_received)
                    self.handle_message(message_received)
            except websockets.ConnectionClosed as e:
                status: List[str] = []
                if e.rcvd:
                    status.append(f'rcvd.code={e.rcvd.code}')
                    status.append(f'rcvd.reason={e.rcvd.reason}')
                if e.sent:
                    status.append(f'sent.code={e.sent.code}')
                    status.append(f'sent.reason={e.sent.reason}')

                logger.warning(f'▪️ Websocket connection closed. {", ".join(status)}')

    def handle_message(self, websocket_message: dict):
        if 'type' in websocket_message:
            message_type = websocket_message['type']

            if message_type != 'test' or self.config.log_test_messages:
                logger.info(f'Received message of type: {message_type}')

            if message_type == 'test':
                self.handle_test()
            else:
                self.webhook_client.send_event(websocket_message)
        else:
            logger.error(f'Received message: {websocket_message}')

    @staticmethod
    def handle_test():
        logger.debug('Heartbeat')

        try:
            f = open('health.txt', 'w')
            timestamp = int(datetime.now(UTC).timestamp())
            f.write(str(timestamp))
            f.close()
        except Exception as e:
            logger.error(e)

    @staticmethod
    def create_config() -> WebsocketConfig:
        token = os.getenv('PLAYER_TOKEN')
        if not token:
            logger.error('PLAYER_TOKEN not set')
        websocket_url = os.getenv('WEBSOCKET_URL') or 'wss://realtime.artifactsmmo.com'
        webhook_url = os.getenv('WEBHOOK_URL')
        log_test_messages = bool(os.getenv('LOG_TEST_MESSAGES', False))
        skip_ssl_verification = bool(os.getenv('SKIP_SSL_VERIFICATION', False))
        subscriptions = os.getenv('SUBSCRIPTIONS', '')
        subscriptions_list = subscriptions.split(',') if subscriptions else []

        return WebsocketConfig(
            token=token,
            websocket_url=websocket_url,
            webhook_url=webhook_url,
            skip_ssl_verification=skip_ssl_verification,
            log_test_messages=log_test_messages,
            subscriptions=subscriptions_list,
        )


websocket_client = WebsocketClient()

if __name__ == '__main__':
    websocket_client.start_websocket()
