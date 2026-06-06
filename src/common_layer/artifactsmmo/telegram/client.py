from datetime import datetime
import json
import os
from typing import Optional
from zoneinfo import ZoneInfo

import requests

from artifactsmmo.log.logger import logger


class TelegramClient:
    def __init__(self):
        telegram_bot_token = os.environ.get('TELEGRAM_BOT_TOKEN')
        if telegram_bot_token is None:
            logger.warning('TELEGRAM_BOT_TOKEN is empty.')
        telegram_api = 'https://api.telegram.org'
        self.telegram_uri = f'{telegram_api}/bot{telegram_bot_token}/sendMessage'
        self.telegram_base_uri = f'{telegram_api}/bot{telegram_bot_token}'
        self.telegram_chat_id = os.environ.get('TELEGRAM_CHAT_ID')
        self.user_timezone = os.environ.get('TELEGRAM_USER_TIMEZONE', 'Europe/Zurich')
        self.session = requests.Session()
        self.session.headers.update({'Content-Type': 'application/json'})

    def send_notification(self, message: str, parse_mode: str = None, silent: bool = False) -> Optional[str]:
        data = {
            'chat_id': self.telegram_chat_id,
            'text': message,
            'disable_notification': False,
        }
        if parse_mode:
            data['parse_mode'] = parse_mode
        data['disable_notification'] = silent
        data_str = json.dumps(data)
        headers = {'Content-Type': 'application/json'}
        try:
            response = self.session.post(self.telegram_uri, data=data_str, headers=headers, timeout=10)
            if response.status_code != 200:
                logger.warning(f'Sent message to Telegram: {response.status_code}, {response.text}')
                return None
            else:
                logger.info(f'Sent message to Telegram: {response.status_code}')
                response_json = response.json()
                return response_json.get('result', {}).get('message_id')
        except Exception as e:
            logger.error(e)
            return None

    def update_notification(self, message_id: str, message: str, parse_mode: str = None, silent: bool = False) -> Optional[str]:
        data = {
            'message_id': message_id,
            'chat_id': self.telegram_chat_id,
            'text': message,
            'disable_notification': False,
        }
        if parse_mode:
            data['parse_mode'] = parse_mode
        data['disable_notification'] = silent
        data_str = json.dumps(data, default=str)
        headers = {'Content-Type': 'application/json'}
        response = self.session.post(f'{self.telegram_base_uri}/editMessageText', data=data_str, headers=headers, timeout=10)
        if response.status_code != 200:
            logger.warning(f'Sent message to Telegram: {response.status_code}, {response.text}')
            return None
        else:
            logger.info(f'Sent message to Telegram: {response.status_code}')
            response_json = response.json()
            return response_json.get('result', {}).get('message_id')

    def format_time_at_user_timezone(self, dt: datetime, millis: bool = False):
        dt_at_timezone = dt.astimezone(ZoneInfo(self.user_timezone))
        if millis:
            return dt_at_timezone.strftime('%H:%M:%S.%f')[:-3]
        else:
            return dt_at_timezone.strftime('%H:%M:%S')

    def unpin_all_messages(self):
        data = {'chat_id': self.telegram_chat_id}
        headers = {'Content-Type': 'application/json'}
        response = self.session.post(
            f'{self.telegram_base_uri}/unpinAllChatMessages', data=json.dumps(data, default=str), headers=headers, timeout=10
        )
        if response.status_code != 200:
            logger.warning(f'Sent message to Telegram: {response.status_code}, {response.text}')
        else:
            logger.info(f'Sent message to Telegram: {response.status_code}')

    def pin_message(self, message_id: str):
        data = {
            'chat_id': self.telegram_chat_id,
            'message_id': message_id,
            'disable_notification': True,
        }
        headers = {'Content-Type': 'application/json'}
        response = self.session.post(f'{self.telegram_base_uri}/pinChatMessage', data=json.dumps(data, default=str), headers=headers, timeout=10)
        if response.status_code != 200:
            logger.warning(f'Sent message to Telegram: {response.status_code}, {response.text}')
        else:
            logger.info(f'Sent message to Telegram: {response.status_code}')
