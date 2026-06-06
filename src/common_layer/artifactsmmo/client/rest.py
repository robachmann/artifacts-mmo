from datetime import datetime, UTC
import os
from time import sleep

import requests
from requests.adapters import HTTPAdapter
from tenacity import retry, stop_after_attempt, stop_after_delay, wait_random

from artifactsmmo.log.logger import logger
from artifactsmmo.singleton import SingletonMeta


class RetryableResponseException(Exception):
    pass


class RestClient(metaclass=SingletonMeta):
    def __init__(self, retry_attempts=3, retry_wait=2):
        token = os.environ.get('PLAYER_TOKEN')
        self.base_url = os.environ.get('BASE_URL', 'https://api.artifactsmmo.com')
        self.session = requests.Session()
        adapter = HTTPAdapter(max_retries=retry_attempts)
        self.session.mount('https://', adapter)
        self.session.headers.update({'Content-Type': 'application/json', 'Accept': 'application/json', 'Authorization': f'Bearer {token}'})
        self.retry_attempts = retry_attempts
        self.retry_wait = retry_wait
        self.error_statuses = (486, 500, 502, 503, 504, 520)

    @retry(
        stop=(stop_after_attempt(10) | stop_after_delay(60)),
        wait=wait_random(2, 5),
    )
    def _request_with_retries(self, method, endpoint, **kwargs):
        url = f'{self.base_url}/{endpoint.lstrip("/")}'
        response = self.session.request(method, url, timeout=15, **kwargs)
        if response.status_code in self.error_statuses:
            response.raise_for_status()
        return response

    def get(self, endpoint, **kwargs):
        return self._request_with_retries('GET', endpoint, **kwargs)

    def post(self, endpoint, data=None, json=None, delay_until: datetime = None, **kwargs):
        if delay_until:
            sleep_seconds = (delay_until - datetime.now(UTC)).total_seconds()
            if sleep_seconds > 0:
                logger.debug('sleep_seconds=%s to match delay_until=%s', sleep_seconds, delay_until)
                sleep(sleep_seconds)

        return self._request_with_retries('POST', endpoint, data=data, json=json, **kwargs)
