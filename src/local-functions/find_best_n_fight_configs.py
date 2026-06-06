from typing import List

from local_environment import LocalEnvironment

from artifactsmmo.extensions import CharacterSchemaExtension
from artifactsmmo.fights.equipment_assembler import EquipmentScope
from artifactsmmo.log.logger import logger
from artifactsmmo.service.food_service import FoodService


class ReportFunction(LocalEnvironment):
    def __init__(self):
        super().__init__()
        self.food_service = FoodService(self.service)

    def handler(self):
        monster = self.service.get_monster('corrupted_owlbear')
        characters = {c.name: c for c in self.service.get_all_character_details()}

        character_names = [self.character_1_name, self.character_2_name, self.character_3_name]
        fight_characters: List[CharacterSchemaExtension] = []
        for participant in character_names:
            fight_characters.append(characters[participant])

        skill_map = self.service.get_skill_map(characters=list(characters.values()))

        bank_items_map = self.service.get_bank_items_map()

        top_n_configs = self.fight_simulator.find_top_n_fight_configs(
            monster=monster,
            characters=fight_characters,
            bank_items_map=bank_items_map,
            equipment_scope=EquipmentScope.CRAFTABLE_AND_MONSTER_DROPS,
            utility_scope=EquipmentScope.NONE,
            exclude_items_if_unavailable=[],
            exclude_items=[],
            include_items=[],
            exclude_drops_from_monsters=[monster.code, 'rosenblood'],
            skill_map=skill_map,
            include_runes=True,
            force_utilities=False,
            sort_function=None,
        )
        fight_configs = list(top_n_configs)
        for config in fight_configs:
            self.fight_simulator.print_fight_config(config, {})


report_function = ReportFunction()


if __name__ == '__main__':
    report_function.handler()
