from typing import Dict, List, Set

from local_environment import LocalEnvironment

from artifactsmmo.extensions import CharacterSchemaExtension, ItemSchemaExtension, MonsterSchemaExtension
from artifactsmmo.log.logger import logger


class ReportFunction(LocalEnvironment):
    def handler(self):
        characters = {c.name: c for c in self.service.get_all_character_details()}
        leader = self.character_1_name
        participants = [self.character_2_name, self.character_3_name]
        fight_characters: List[CharacterSchemaExtension] = [characters[leader]]
        for participant in participants:
            fight_characters.append(characters[participant])

        monster = self.service.get_monster('king_slime')
        idx = 0
        for equipment1 in self.generate_equipment(monster):
            for equipment2 in self.generate_equipment(monster):
                for equipment3 in self.generate_equipment(monster):
                    equipments = [equipment1, equipment2, equipment3]
                    #
                    # equipments = [
                    #     {
                    #         #'level': 46,
                    #         'weapon_slot': 'bloodblade',
                    #         'helmet_slot': 'corrupted_crown',  # 100.000%
                    #         # 'helmet_slot': 'cursed_hat',          #  94.120%
                    #         # 'helmet_slot': 'hork_helmet',         #  93.930%
                    #         # 'helmet_slot': 'cultist_hat',         #  18.240%
                    #         #'helmet_slot': 'jester_hat',           #  16.410%
                    #         #'helmet_slot': 'mithril_helm',         #   9.350%
                    #         #'helmet_slot': 'white_knight_helmet',  #   6.620%
                    #         #'helmet_slot': 'strangold_helmet',     #   5.370%
                    #         'body_armor_slot': 'malefic_armor',
                    #         'leg_armor_slot': 'enchanter_pants',
                    #         'boots_slot': 'mithril_boots',
                    #         # 'shield_slot': 'mithril_shield',  # 96.600%
                    #         'shield_slot': 'fire_shield',  #  99.900%
                    #         'ring1_slot': 'mithril_ring',
                    #         'ring2_slot': 'mithril_ring',
                    #         'amulet_slot': 'greater_ruby_amulet',
                    #         'artifact1_slot': 'novice_guide',
                    #         'artifact2_slot': 'malefic_crystal',
                    #         'artifact3_slot': 'life_crystal',
                    #         'rune_slot': 'healing_rune',  # 96.580%
                    #         # 'rune_slot': 'protection_rune',  #   94.160%
                    #         # 'rune_slot': 'burn_rune', # 93.990%
                    #         'utility1_slot': '',
                    #         'utility1_slot_quantity': 1,
                    #         'utility2_slot': '',
                    #         'utility2_slot_quantity': 1,
                    #     },
                    #     {
                    #         #'level': 45,
                    #         'weapon_slot': 'mithril_sword',
                    #         'helmet_slot': 'jester_hat',
                    #         'body_armor_slot': 'mithril_platebody',
                    #         'leg_armor_slot': 'mithril_platelegs',
                    #         'boots_slot': 'lizard_boots',
                    #         'shield_slot': 'mithril_shield',
                    #         'rune_slot': 'healing_aura_rune',
                    #         'ring1_slot': 'mithril_ring',
                    #         'ring2_slot': 'mithril_ring',
                    #         'amulet_slot': 'greater_sapphire_amulet',
                    #         'artifact1_slot': 'perfect_pearl',
                    #         'artifact2_slot': 'novice_guide',
                    #         'artifact3_slot': 'lost_world_map',
                    #         #    'utility1_slot': 'health_splash_potion',
                    #         'utility1_slot_quantity': 1,
                    #         'utility2_slot': '',
                    #         'utility2_slot_quantity': 1,
                    #     },
                    #     {
                    #         #'level': 43,
                    #         'weapon_slot': 'mithril_sword',
                    #         'helmet_slot': 'jester_hat',
                    #         'body_armor_slot': 'mithril_platebody',
                    #         'leg_armor_slot': 'mithril_platelegs',
                    #         'boots_slot': 'lizard_boots',
                    #         'shield_slot': 'mithril_shield',
                    #         'rune_slot': 'healing_aura_rune',
                    #         'ring1_slot': 'mithril_ring',
                    #         'ring2_slot': 'mithril_ring',
                    #         # 'amulet_slot': 'greater_sapphire_amulet',
                    #         # 'amulet_slot': 'sapphire_amulet',
                    #         'amulet_slot': 'prospecting_amulet',
                    #         'artifact1_slot': 'perfect_pearl',
                    #         'artifact2_slot': 'novice_guide',
                    #         'artifact3_slot': 'lost_world_map',
                    #         'utility1_slot': '',
                    #         'utility1_slot_quantity': 1,
                    #         'utility2_slot': '',
                    #         'utility2_slot_quantity': 1,
                    #     },
                    # ]
                    #
                    utilities_map: Dict[str, Set[ItemSchemaExtension]] = {}
                    for character, equipment in zip(fight_characters, equipments):
                        utilities_map[character.name] = set()
                        for slot in ['utility1_slot', 'utility2_slot']:
                            item_code = equipment.get(slot)
                            if item_code:
                                item = self.service.get_item(item_code)
                                utilities_map[character.name].add(item)

                        if 'level' in equipment:
                            character.level = equipment['level']

                    result = self.fight_simulator.test_exact_boss_config(
                        characters=fight_characters,
                        monster=monster,
                        character_equipment_map=equipments,
                        utilities_map=utilities_map,
                        print_log=False,
                        rounds=1,
                    )
                    idx += 1
                    if result.character_wins:
                        logger.info(idx + ' ' + result.to_string())
                    else:
                        logger.info(f'{idx} Unsuccessful.')

    def generate_equipment(self, monster: MonsterSchemaExtension):
        for weapon in self.service.get_items_by_type('weapon', monster.level):
            for helmet in self.service.get_items_by_type('helmet', monster.level):
                for body_armor in self.service.get_items_by_type('body_armor', monster.level):
                    for leg_armor in self.service.get_items_by_type('leg_armor', monster.level):
                        for boots in self.service.get_items_by_type('boots', monster.level):
                            for shield in self.service.get_items_by_type('shield', monster.level):
                                for ring in self.service.get_items_by_type('ring', monster.level):
                                    for amulet in self.service.get_items_by_type('amulet', monster.level):
                                        for rune in self.service.get_items_by_type('rune', max(20, monster.level)):
                                            if weapon.subtype == 'tool':
                                                continue
                                            yield {
                                                'weapon_slot': weapon.code,
                                                'helmet_slot': helmet.code,
                                                'body_armor_slot': body_armor.code,
                                                'leg_armor_slot': leg_armor.code,
                                                'boots_slot': boots.code,
                                                'shield_slot': shield.code,
                                                'ring1_slot': ring.code,
                                                'ring2_slot': ring.code,
                                                'amulet_slot': amulet.code,
                                                'artifact1_slot': 'novice_guide',
                                                'artifact2_slot': '',
                                                'artifact3_slot': '',
                                                'rune_slot': rune.code,
                                                #   'utility1_slot': '',
                                                #   'utility1_slot_quantity': 1,
                                                #   'utility2_slot': '',
                                                #   'utility2_slot_quantity': 1,
                                            }


report_function = ReportFunction()

if __name__ == '__main__':
    report_function.handler()
