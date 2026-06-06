from datetime import datetime, timedelta, UTC
from itertools import groupby
from typing import Dict, List, Optional

from telegram.constants import ParseMode
import xxhash

from artifactsmmo.actions.action_processor import ActionProcessor
from artifactsmmo.client.actions import ActionsClient
from artifactsmmo.client.client import Client
from artifactsmmo.dynamodb.character_table import CharacterTable
from artifactsmmo.dynamodb.follower_table import FollowerSubscription, FollowerTable
from artifactsmmo.dynamodb.task_progress_table import TaskProgressTable
from artifactsmmo.game_constants import ACTION_EMOJI_MAP
from artifactsmmo.log.logger import logger
from artifactsmmo.models import LogSchema, LogType
from artifactsmmo.service.food_service import FoodService
from artifactsmmo.service.helpers import escape_string
from artifactsmmo.service.service import Service
from artifactsmmo.service.tasks import Task
from artifactsmmo.telegram.client import TelegramClient
from artifactsmmo.templates.template_processor import TemplateProcessor


class FollowerService:
    def __init__(self):
        self.telegram_client = TelegramClient()
        self.follower_table = FollowerTable()
        self.character_table = CharacterTable()
        self.client: Client = Client()
        self.service: Service = Service(self.client)
        self.food_service: FoodService = FoodService(self.service)

        self.action_processor = ActionProcessor(
            ActionsClient(),
            self.service,
            None,
            self.telegram_client,
            TaskProgressTable(),
            None,
            self.food_service,
            self.character_table,
        )
        self.template_processor = TemplateProcessor(self.client, self.service, self.telegram_client, self.food_service)

    def add_follower_subscription(self, character_name: str, minutes: int = 5, subscription_type: str = 'follow'):
        self.follower_table.add_subscription(character_name, minutes, subscription_type=subscription_type)

    def get_all_follower_subscriptions(self) -> Dict[str, List[FollowerSubscription]]:
        all_subscriptions = sorted(
            self.follower_table.get_all_subscriptions(),
            key=lambda s: s.character_name,
        )
        grouped_subs = {key: list(group) for key, group in groupby(all_subscriptions, key=lambda subscription: subscription.character_name)}
        return grouped_subs

    def notify_updates(self, follower_subscriptions: List[FollowerSubscription], inserted_logs: List[LogSchema]):
        for follower_subscription in follower_subscriptions:
            if follower_subscription.type == 'monitor':
                self.notify_monitor_updates(follower_subscription, inserted_logs)
            else:
                self.notify_log_updates(follower_subscription, inserted_logs)

    def notify_log_updates(self, follower_subscription: FollowerSubscription, inserted_logs: List[LogSchema]):
        previous_message = follower_subscription.message
        message_lines = []
        for log in inserted_logs:
            if log.type == LogType.FIGHT and log.content.get('fight', {}).get('result', '') != 'win':
                icon_key = 'fight-lost'
            else:
                icon_key = log.type
            icon = f'{ACTION_EMOJI_MAP[icon_key]} ' if icon_key in ACTION_EMOJI_MAP else ''

            if log.type in log.content:
                if log.type == LogType.FIGHT:
                    fight_obj = log.content.get(log.type, {})
                    characters = fight_obj.get('characters', [])
                    for character in characters:
                        character_name = character.get('character_name')
                        if character_name and character_name == log.character:
                            xp_gained = int(character.get('xp', 0))
                            break
                else:
                    xp_gained = int(log.content.get(log.type, {}).get('xp_gained', 0))
            else:
                xp_gained = int(log.content.get('xp_gained', 0))

            if xp_gained > 0:
                xp_part = f' | {xp_gained}xp'
            else:
                xp_part = ''

            message_lines.append(
                f'*{escape_string(self.telegram_client.format_time_at_user_timezone(log.created_at, millis=True))}*'
                + escape_string(f': {icon}{log.description} ⏱️ {timedelta(seconds=log.cooldown) if log.cooldown else "0:00:00"} {xp_part}')
            )

        new_message = '\n'.join(message_lines)
        if not previous_message or len(previous_message + '\n' + new_message) > 3000:
            message = new_message
            previous_message_id = ''
        else:
            message = previous_message + '\n' + new_message
            previous_message_id = follower_subscription.message_id

        if message:
            if previous_message_id:
                self.telegram_client.update_notification(message_id=previous_message_id, message=message, parse_mode=ParseMode.MARKDOWN_V2)
            else:
                message_id = self.telegram_client.send_notification(message, parse_mode=ParseMode.MARKDOWN_V2)
                follower_subscription.message_id = message_id
            follower_subscription.message = message
            self.follower_table.update_subscription(follower_subscription)
        else:
            logger.warning('Empty message for a log updates')

    def notify_monitor_updates(self, follower_subscription: FollowerSubscription, inserted_logs: List[LogSchema]):
        message_lines = []
        active_quest = self.character_table.get_quest(follower_subscription.character_name)
        if active_quest:
            skip_done = True
            skip_next = False
            now = datetime.now(UTC).replace(microsecond=0)
            current_task_id: Optional[str] = None

            log = max(inserted_logs, key=lambda log: log.cooldown_expiration)
            title = f'*{escape_string(follower_subscription.character_name)}* {escape_string(f" ⏱️ {timedelta(seconds=log.cooldown) if log.cooldown else "0:00:00"}")}'

            message_lines.append(title)
            for task in active_quest.tasks:
                task_description = self.__describe_task(task)

                until_str = ''
                if task.until:
                    if task.until.date_time:
                        etc: timedelta = task.until.date_time.replace(microsecond=0) - now
                        time = self.telegram_client.format_time_at_user_timezone(task.until.date_time)
                        until_str = f' ⏱️ {etc} @ {time}'
                    until_str += f' [{task.until.status}]'

                task_id_str = escape_string(f' [{task.task_id}]') if task.task_id else ''
                escaped_description = escape_string(f' {task_description}') if task_description else ''
                escaped_description += escape_string(until_str)
                if (not skip_done or task.ttl > 0) and (not skip_next or not current_task_id or task.task_id == current_task_id):
                    if not current_task_id and task.task_id:
                        current_task_id = task.task_id
                    message_lines.append(f'└ {"☑️ " if task.ttl == 0 else ""}*{escape_string(task.action)}*{task_id_str}{escaped_description}')

        message = '\n'.join(message_lines)
        previous_message_id = follower_subscription.message_id
        if message:
            if previous_message_id:
                message_hash = xxhash.xxh64(message).hexdigest()
                if message_hash != follower_subscription.message:
                    self.telegram_client.update_notification(message_id=previous_message_id, message=message, parse_mode=ParseMode.MARKDOWN_V2)
                    follower_subscription.message = message_hash
            else:
                message_id = self.telegram_client.send_notification(message, parse_mode=ParseMode.MARKDOWN_V2)
                self.telegram_client.pin_message(message_id)
                follower_subscription.message_id = message_id
            self.follower_table.update_subscription(follower_subscription)
        else:
            logger.warning('Empty message for a monitor update')

    def __describe_task(self, task: Task):
        if task.kind == 'action':
            action_task_description = self.action_processor.describe_task(task)
            return f'{task.ttl}x {action_task_description}' if task.ttl > 1 else action_task_description
        elif task.kind == 'template':
            return self.template_processor.describe_task(task)
        else:
            return 'No description available'
