import csv
from typing import List

from local_environment import LocalEnvironment

from artifactsmmo.log.logger import logger


class ReportFunction(LocalEnvironment):
    def handler(self):
        all_weapons = list(self.service.get_items_by_type('weapon'))
        all_weapons_without_tools = [w for w in all_weapons if w.subtype != 'tool']
        all_weapon_keys: List[str] = []
        data: List[dict] = []
        for monster in self.service.get_all_monsters():
            monster_str = f'{monster.code} ({monster.level})'
            row = {'name': monster_str}
            for weapon in all_weapons_without_tools:
                weapon_str = f'{weapon.code} ({weapon.level})'
                if weapon_str not in all_weapon_keys:
                    all_weapon_keys.append(weapon_str)
                row[weapon_str] = f'{weapon.get_avg_attack(monster):.1f}'
            data.append(row)

        csv_file = 'weapon_affinity.csv'
        with open(csv_file, mode='w', newline='') as file:
            # noinspection PyTypeChecker
            writer = csv.DictWriter(file, fieldnames=['name', *all_weapon_keys])
            writer.writeheader()
            writer.writerows(data)
        logger.info(f'Wrote to {csv_file}')


report_function = ReportFunction()


if __name__ == '__main__':
    report_function.handler()
