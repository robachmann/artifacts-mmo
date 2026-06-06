import csv
from typing import List

from artifactsmmo.log.logger import logger
from local_environment import LocalEnvironment


class ReportFunction(LocalEnvironment):
    def handler(self):
        item_type = ''
        if item_type:
            item_list = self.service.get_items_by_type(item_type)
        else:
            item_list = list(self.service.get_all_items())

        data: List[dict] = []
        for item in item_list:
            d = item.to_flat_dict()
            d.pop('craft', None)
            d.pop('description', None)
            d.pop('effects', None)
            data.append(d)

        all_keys = {key for entry in data for key in entry}

        fieldnames = sorted(all_keys)
        csv_file = 'items.csv'
        with open(csv_file, mode='w', newline='') as file:
            # noinspection PyTypeChecker
            writer = csv.DictWriter(file, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(data)

        logger.info(f'Data successfully written to {csv_file}')


report_function = ReportFunction()


if __name__ == '__main__':
    report_function.handler()
