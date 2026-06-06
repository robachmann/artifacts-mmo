import json

from local_environment import LocalEnvironment
from artifactsmmo.log.logger import logger


class ReportFunction(LocalEnvironment):
    def handler(self):
        global_map = self.service.get_global_quantity_map()
        all_npcs = self.service.get_all_npcs()

        sellable_items = {}
        npc_offers = {}
        for npc in all_npcs:
            for item_code, offer in npc.items.items():
                if offer.sell_price:
                    origin = self.service.get_item_origin(item_code)
                    if not origin:
                        logger.error('Fix this case.')
                    else:
                        if origin.resources:
                            drop_rate = min(d.drop_rate for d in origin.resources.values())
                        elif origin.monsters:
                            drop_rate = min(d.drop_rate for d in origin.monsters.values())
                        else:
                            item = self.service.get_item(item_code)
                            if item.craft:
                                total_drop_rate = 0
                                for craft in item.craft.items:
                                    craft_origin = self.service.get_item_origin(craft.code)
                                    if craft_origin:
                                        if craft_origin.resources:
                                            total_drop_rate += craft.quantity * min(d.drop_rate for d in craft_origin.resources.values())
                                        elif craft_origin.monsters:
                                            total_drop_rate += craft.quantity * min(d.drop_rate for d in craft_origin.monsters.values())
                                        else:
                                            logger.error('Fix this case.')
                                drop_rate = total_drop_rate
                            else:
                                drop_rate = 1000
                        drop_chance = 1 / drop_rate
                        npc_offers[item_code] = round(offer.sell_price * drop_chance, 2)
                    if item_code in global_map:
                        sellable_items[item_code] = offer.sell_price * global_map[item_code]

        sellable_items['total'] = sum(sellable_items.values())
        sorted_dict = dict(sorted(sellable_items.items(), key=lambda item: item[1], reverse=True))
        logger.info(f'Currently sellable items: {json.dumps(sorted_dict, indent=2)}')

        sorted_offers = dict(sorted(npc_offers.items(), key=lambda item: item[1], reverse=True))
        logger.info(f'Most profitable items: {json.dumps(sorted_offers, indent=2)}')


report_function = ReportFunction()


if __name__ == '__main__':
    report_function.handler()
