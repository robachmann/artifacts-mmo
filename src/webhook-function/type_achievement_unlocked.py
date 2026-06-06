from datetime import datetime, timedelta, UTC
from typing import Tuple, Type

from type_base import T, TypeBase

from artifactsmmo.models import AchievementSchema


class AchievementUnlockedHandler(TypeBase[AchievementSchema]):
    def _get_schema(self) -> Type[AchievementSchema]:
        return AchievementSchema

    def _get_message_timestamp(self, content: T) -> datetime:
        return datetime.now(UTC)

    def _handle_content(self, content: AchievementSchema) -> Tuple[str, bool]:
        msg = f'🥇 Unlocked achievement: {content.name} ({content.description}) for {content.points} points.'

        remaining_achievements = [a for a in self.service.get_account_achievements() if not a.completed_at]
        if not remaining_achievements:
            server_status = self.service.get_server_status()
            elapsed = datetime.now(UTC) - server_status.season.start_date
            msg += (
                f' \n\nCongratulations, you have completed all achievements! It took you {timedelta(seconds=int(elapsed.total_seconds()))} '
                f'since the start of season {server_status.season.number}.'
            )

        return msg, False
