import json
from collections import defaultdict

from local_environment import LocalEnvironment
from artifactsmmo.log.logger import logger


class ReportFunction(LocalEnvironment):
    def handler(self):
        events = self.service.get_all_events()
        event_map = defaultdict(list)
        for event in events:
            event_map[event.content.type].append(event.content.code)
        logger.info(f'All events: {json.dumps(event_map, indent=4)}')



report_function = ReportFunction()


if __name__ == '__main__':
    report_function.handler()
