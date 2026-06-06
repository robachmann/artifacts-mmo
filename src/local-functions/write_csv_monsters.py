import csv
from typing import List

from local_environment import LocalEnvironment

from artifactsmmo.log.logger import logger


class ReportFunction(LocalEnvironment):
    def handler(self):
        monsters = self.service.get_all_monsters()

        data: List[dict] = []
        for monster in monsters:
            d = monster.to_flat_dict()
            # d.pop('craft', None)
            # d.pop('description', None)
            d.pop('effects', None)
            d.pop('min_gold', None)
            d.pop('drops', None)
            data.append(d)

        # all_keys = {key for entry in data for key in entry}

        # fieldnames = all_keys

        fieldnames = [
            'level',
            'code',
            'name',
            'type',
            'max_gold',
            'is_event_monster',
            'hp',
            'initiative',
            'critical_strike',
            'attack_air',
            'attack_earth',
            'attack_fire',
            'attack_water',
            'res_air',
            'res_earth',
            'res_fire',
            'res_water',
            #'offensive_elements',
            'effect.barrier',
            'effect.berserker_rage',
            'effect.burn',
            'effect.corrupted',
            'effect.frenzy',
            'effect.healing',
            'effect.lifesteal',
            'effect.poison',
            'effect.reconstitution',
            'effect.void_drain',
            #'min_gold',
            #'drops',
        ]

        csv_file = 'monsters.csv'
        with open(csv_file, mode='w', newline='') as file:
            # noinspection PyTypeChecker
            writer = csv.DictWriter(file, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(data)

        logger.info(f'Data successfully written to {csv_file}')


report_function = ReportFunction()


if __name__ == '__main__':
    report_function.handler()
