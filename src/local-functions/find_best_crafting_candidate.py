from typing import List

from artifactsmmo.log.logger import logger
from artifactsmmo.models import CraftSkill
from artifactsmmo.service.helpers import (
    RecyclableItem,
)
from local_environment import LocalEnvironment


class ReportFunction(LocalEnvironment):
    def handler(self):
        skill_filter = [CraftSkill.WEAPONCRAFTING]

        quickest_recyclable_items: List[RecyclableItem] = self.service.get_quickest_recyclable_items(
            item_count=200,
            min_level=28,
            max_level=38,
            skill_filter=skill_filter,
            include_task_drops=True,
            include_event_drops=True,
        )

        for i in quickest_recyclable_items:
            logger.info(f'{i.item_code}: {i.total_drop_rate}')


report_function = ReportFunction()


if __name__ == '__main__':
    report_function.handler()
