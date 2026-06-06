from collections import Counter, defaultdict
from itertools import repeat
import json
from typing import Dict, List

from local_environment import LocalEnvironment

from artifactsmmo.extensions.account_achievement_schema_extension import AccountAchievementSchemaExtension
from artifactsmmo.log.logger import logger


class ReportFunction(LocalEnvironment):
    def handler(self):

        exact_map = {
            'dreadful_battleaxe': 1,
            'mithril_helm': 1,
            'mithril_shield': 3,
            'prospecting_amulet': 1,
            'mithril_platelegs': 2,
            'mithril_ring': 2,
            'mithril_boots': 1,
            'protection_rune': 1,
            'life_crystal': 1,
            'malefic_crystal': 1,
            # 'corrupted_skull': 1,
            'bloodblade': 1,
            'obsidian_helmet': 1,
            # 'mithril_shield': 1,
            'malefic_armor': 2,
            'greater_ruby_amulet': 1,
            'cultist_pants': 1,
            'malefic_ring': 2,
            'healing_aura_rune': 2,
            # 'corrupted_skull': 1,
            'novice_guide': 1,
            'perfect_pearl': 1,
            'mithril_sword': 1,
            'jester_hat': 1,
            # 'goblin_guard_shield': 1,
            # 'malefic_armor': 1,
            'greater_sapphire_amulet': 1,
            # 'mithril_platelegs': 1,
            'lizard_boots': 1,
            'forest_ring': 2,
            # 'healing_aura_rune': 1,
        }

        max_list_map = defaultdict(list)
        for item_code, item_qty in exact_map.items():
            max_list_map[item_qty].append(item_code)

        for item_qty, item_list in max_list_map.items():
            result = f'/resolve -{item_qty} {" ".join(item_list)}'
            # for item_code, item_qty in exact_map.items():
            #    result += ' '.join(repeat(item_code, item_qty))
            #    result += ' '

            logger.info(result)


report_function = ReportFunction()


if __name__ == '__main__':
    report_function.handler()
