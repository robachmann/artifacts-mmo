from datetime import datetime, UTC
from types import NoneType
from typing import Dict, Tuple, Type

from type_base import T, TypeBase

from artifactsmmo.log.logger import logger
from artifactsmmo.models import AchievementType


class AnnouncementHandler(TypeBase[NoneType]):
    def _get_schema(self) -> Type[NoneType]:
        return NoneType

    def _get_message_timestamp(self, content: T) -> datetime:
        return datetime.now(UTC)

    def _handle_content(self, content: Dict) -> Tuple[str, bool]:
        announcement_message = content['message']
        message = f'📣 {announcement_message}' if 'message' in content else ''

        account, sep, rest = message.partition(' is the first player to unlock the achievement: ')
        if sep:
            account = account.lstrip('📣 ')
            achievement_name = rest.rstrip('!')
            achievements = self.service.get_account_achievements(account)
            for achievement in achievements:
                if achievement.name == achievement_name:
                    if achievement.type == AchievementType.COMBAT_KILL:
                        characters = self.service.get_all_character_details(account)
                        notification = '\n'.join(c.to_str() for c in characters)
                        logger.info(f'Characters of account {account} at the time of achieving {achievement.code}: {notification}')
                        self.telegram_client.send_notification(notification)
                    break

        return message, False
