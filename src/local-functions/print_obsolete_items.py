from collections import defaultdict
from typing import Dict, List, Set

from local_environment import LocalEnvironment

from artifactsmmo import game_constants
from artifactsmmo.log.logger import logger


class ReportFunction(LocalEnvironment):
    def handler(self):

        all_character_details = self.service.get_all_character_details()
        level = 30#max(c.level for c in all_character_details)

        global_quantity_map = self.service.get_global_quantity_map()
        gear_type_map: Dict[str, List[str]] = defaultdict(list)

        gear_types: Set[str] = {gt.rstrip('123') for gt in game_constants.GEAR_POSITIONS}
        for item_code in global_quantity_map:
            if item_code:
                item = self.service.get_item(item_code)
                if item.type in gear_types and item.subtype != 'tool' and item.level <= level:
                    gear_type_map[item.type].append(item_code)

        for gear_type, items in gear_type_map.items():
            weakest_items = self.equipment_assembler.find_clearly_weakest_items(item_codes=items)
            if weakest_items:
                logger.info(f'Gear type {gear_type}: {dict(weakest_items)}')


report_function = ReportFunction()


if __name__ == '__main__':
    report_function.handler()
