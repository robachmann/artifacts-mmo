import json
import os

import requests

from artifactsmmo.log.logger import logger


class WebhookClient:
    def __init__(self):
        self.webhook_url = os.environ.get('WEBHOOK_URL')
        self.session = requests.Session()
        self.session.headers.update({'Content-Type': 'application/json'})

    def send_event(self, message: dict):
        if self.webhook_url:
            data_str = json.dumps(message)
            response = self.session.post(self.webhook_url, data=data_str, timeout=10)
            if response.status_code != 200:
                logger.warning(f'Sent message to Webhook: {response.status_code}, {response.text}')
            else:
                logger.info(f'Sent message to Webhook: {response.status_code}')
