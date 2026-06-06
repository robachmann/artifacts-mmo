from collections import Counter
from copy import copy
from typing import Dict, List

from local_environment import LocalEnvironment

from artifactsmmo.extensions import CharacterSchemaExtension
from artifactsmmo.fights.equipment_assembler import EquipmentScope
from artifactsmmo.fights.simulation_result import SimulationResult
from artifactsmmo.log.logger import logger
from artifactsmmo.service.food_service import FoodService


class ReportFunction(LocalEnvironment):
    def __init__(self):
        super().__init__()
        self.food_service = FoodService(self.service)

    def handler(self):
        characters = self.service.get_all_character_details()
        skill_map = self.service.get_skill_map(characters=characters)

        character_names = [
            self.character_1_name,
            self.character_2_name,
            self.character_3_name,
            self.character_4_name,
        ]

        monster = self.service.get_monster('grimlet')

        all_characters_inventory_map = self.service.get_all_characters_inventory_map(characters, include_equipment=True)
        global_quantity_map = self.service.get_global_quantity_map(all_characters_inventory_map=all_characters_inventory_map)
        bank_items_map = copy(global_quantity_map)
        all_equipments: Dict[str, int] = Counter()
        for c in [character for character in characters if character.name in character_names]:
            character = CharacterSchemaExtension.empty(c.level)
            raw_results: List[SimulationResult] = []
            best_result = self.fight_simulator.find_best_fight_config(
                monster=monster,
                character=character,
                exclude_drops_from_monsters=[],
                exclude_items_if_unavailable=[
                    'ruby_book',
                    'topaz_book',
                    'emerald_book',
                    'corrupted_crown',
                    'corrupted_skull',
                    'malefic_crystal',
                    'diabolic_elixir',
                    'health_boost_potion',
                    'enchanted_boost_potion',
                    'enchanted_health_potion',
                ],
                exclude_items=[],
                include_items=[],
                equipment_scope=EquipmentScope.CRAFTABLE_AND_MONSTER_DROPS,
                utility_scope=EquipmentScope.CRAFTABLE_AND_MONSTER_DROPS,
                skill_map=skill_map,
                raw_results=raw_results,
                bank_items_map=bank_items_map,
            )

            self.fight_simulator.print_fight_config(best_result, character_name=character.name)
            equipment: Counter = Counter(best_result.equipment.values())
            all_equipments.update(best_result.equipment.values())
            for item_code, item_qty in equipment.items():
                if item_code in bank_items_map:
                    bank_items_map[item_code] -= item_qty

        missing_equipment = {}
        for item_code, item_qty in all_equipments.items():
            missing_qty = item_qty - global_quantity_map.get(item_code, 0)
            if missing_qty > 0:
                missing_equipment[item_code] = missing_qty

        a, b = self.service.resolve_recipes(missing_equipment)
        logger.info(f'complete equipment_map={dict(missing_equipment)}, missing_parts={a.missing_items}, immediately_craftable={b}')


report_function = ReportFunction()


if __name__ == '__main__':
    report_function.handler()
