import unittest
from typing import Dict
from collections import Counter

from artifactsmmo.service.execution_context import ExecutionContext
from local_environment import LocalEnvironment

from artifactsmmo.extensions import CharacterSchemaExtension

from artifactsmmo.service.food_service import FoodService
from artifactsmmo.service.helpers import character_1_name


class TestCases(unittest.TestCase):
    def setUp(self):
        self.local_env = LocalEnvironment()
        self.food_service = FoodService(self.local_env.service)

    def test_consumables_0(self):
        character: CharacterSchemaExtension = self.local_env.service.get_character_details(character_1_name())
        character.inventory_map = Counter(
            {
                'cooked_gudgeon': 7,  # heals 75 hp
                'apple': 1,  # heals 50 hp
                'cooked_salmon': 1,  # heals 400 hp
            }
        )
        character.hp = 100
        character.max_hp = 600
        required_hp = character.hp + 450
        result: Dict[str, int] = self.food_service.get_best_food_to_consume(character, required_hp)

        self.assertTrue(result['cooked_gudgeon'] == 1)
        self.assertTrue(result['cooked_salmon'] == 1)
        self.assertTrue(sum(result.values()) == 2)

    def test_consumables_1(self):
        character: CharacterSchemaExtension = self.local_env.service.get_character_details(character_1_name())
        character.inventory_map = Counter(
            {
                'cooked_gudgeon': 7,  # heals 75 hp
                'cooked_salmon': 1,  # heals 400 hp
            }
        )
        character.hp = 1
        character.max_hp = 600
        required_hp = 1
        result: Dict[str, int] = self.food_service.get_best_food_to_consume(character, required_hp)

        self.assertTrue(result['cooked_gudgeon'] == 1)
        self.assertTrue(sum(result.values()) == 1)

    def test_consumables_2(self):
        character: CharacterSchemaExtension = self.local_env.service.get_character_details(character_1_name())
        character.inventory_map = Counter(
            {
                'cooked_gudgeon': 1,  # heals 75 hp
                'apple': 1,  # heals 50 hp
                'cooked_salmon': 2,  # heals 400 hp
            }
        )
        character.hp = 100
        character.max_hp = 600
        required_hp = character.hp + 450
        result: Dict[str, int] = self.food_service.get_best_food_to_consume(character, required_hp)

        self.assertTrue(result['cooked_salmon'] == 1)
        self.assertTrue(result['cooked_gudgeon'] == 1)
        self.assertTrue(sum(result.values()) == 2)

    def test_consumables_3(self):
        character: CharacterSchemaExtension = self.local_env.service.get_character_details(character_1_name())
        character.inventory_map = Counter(
            {
                'cooked_gudgeon': 29,
                'cooked_chicken': 17,
                'cooked_beef': 8,
                'fried_eggs': 14,
                'cooked_shrimp': 19,
                'cheese': 2,
                'cooked_wolf_meat': 6,
                'mushroom_soup': 7,
                'cooked_trout': 25,
            }
        )
        character.hp = 100
        character.max_hp = 1200
        required_hp = character.hp + 761
        result: Dict[str, int] = self.food_service.get_best_food_to_consume(character, required_hp)

        self.assertTrue(result['cooked_wolf_meat'] == 4)
        self.assertTrue(sum(result.values()) == 4)

    def test_consumables_4(self):
        character: CharacterSchemaExtension = self.local_env.service.get_character_details(character_1_name())
        character.inventory_map = Counter(
            {
                'cooked_gudgeon': 1,
            }
        )
        character.hp = 100
        character.max_hp = 110
        required_hp = character.hp + 10
        result: Dict[str, int] = self.food_service.get_best_food_to_consume(character, required_hp)

        self.assertTrue(len(result) == 0)

    def test_consumables_5(self):
        character: CharacterSchemaExtension = self.local_env.service.get_character_details(character_1_name())
        character.inventory_map = Counter(
            {
                'cooked_salmon': 53,
                'cooked_chicken': 35,
                'apple_pie': 35,
                'cooked_wolf_meat': 18,
                'cooked_trout': 13,
                'cooked_beef': 6,
                'efreet_cloth': 2,
            }
        )
        character.hp = 244
        required_hp = 1252
        character.max_hp = 1320
        result: Dict[str, int] = self.food_service.get_best_food_to_consume(character, required_hp)

        self.assertDictEqual({'apple_pie': 3}, result)

    def test_consumables_6(self):
        character: CharacterSchemaExtension = self.local_env.service.get_character_details(character_1_name())
        character.hp = 228
        required_hp = 1252
        character.max_hp = 1320
        character.inventory_map = Counter(
            {
                'cooked_salmon': 53,
                'apple_pie': 38,
                'cooked_chicken': 35,
                'cooked_wolf_meat': 18,
                'cooked_trout': 13,
                'cooked_beef': 6,
                'efreet_cloth': 1,
            }
        )
        result: Dict[str, int] = self.food_service.get_best_food_to_consume(character, required_hp)

        self.assertDictEqual({'apple_pie': 3}, result)

    def test_consumables_7(self):
        character: CharacterSchemaExtension = self.local_env.service.get_character_details(character_1_name())
        character.hp = 282
        required_hp = 1252  # missing 970
        character.max_hp = 1320
        character.inventory_map = Counter(
            {
                'cooked_salmon': 55,  # 400
                'apple_pie': 38,  # 350
                'cooked_chicken': 35,  # 80
                'cooked_wolf_meat': 18,  # 200
                'cooked_trout': 14,  # 225
                'cooked_beef': 6,  # 150
            }
        )
        result: Dict[str, int] = self.food_service.get_best_food_to_consume(character, required_hp)

        self.assertDictEqual({'cooked_trout': 1, 'cooked_salmon': 2}, result)

    def test_consumables_8(self):
        character: CharacterSchemaExtension = self.local_env.service.get_character_details(character_1_name())
        character.hp = 1413
        required_hp = 1374
        character.max_hp = 1470
        character.inventory_map = Counter(
            {
                'cooked_salmon': 87,  # 400
                'apple_pie': 29,  # 350
                'cooked_chicken': 22,  # 80
                'cooked_wolf_meat': 14,  # 200
                'cooked_trout': 11,  # 225
                'cooked_beef': 6,  # 150
                'cooked_hellhound_meat': 2,  # 600
            }
        )
        result: Dict[str, int] = self.food_service.get_best_food_to_consume(character, required_hp)

        self.assertDictEqual({}, result)

    def test_consumables_9(self):
        character: CharacterSchemaExtension = self.local_env.service.get_character_details(character_1_name())
        character.hp = 1126
        required_hp = 1252
        character.max_hp = 1320
        character.inventory_map = Counter(
            {
                'cooked_salmon': 55,  # 400
                'apple_pie': 38,  # 350
                'cooked_chicken': 35,  # 80
                'cooked_wolf_meat': 18,  # 200
                'cooked_trout': 14,  # 225
                'cooked_beef': 7,  # 150
            }
        )
        result: Dict[str, int] = self.food_service.get_best_food_to_consume(character, required_hp)

        self.assertDictEqual({'cooked_beef': 1}, result)

    def test_consumables_10(self):
        character: CharacterSchemaExtension = self.local_env.service.get_character_details(character_1_name())
        character.hp = 326
        required_hp = 1075  # missing: 749
        character.max_hp = 1320
        character.inventory_map = Counter(
            {
                'cooked_salmon': 57,  # 400
                'apple_pie': 38,  # 350
                'cooked_chicken': 35,  # 80
                'cooked_wolf_meat': 18,  # 200
                'cooked_trout': 14,  # 225
                'cooked_beef': 7,  # 150
            }
        )
        result: Dict[str, int] = self.food_service.get_best_food_to_consume(character, required_hp)

        self.assertDictEqual({'cooked_salmon': 2}, result)

    def test_consumables_11(self):
        character: CharacterSchemaExtension = self.local_env.service.get_character_details(character_1_name())
        character.hp = 281
        required_hp = 1375  # missing: 1094
        character.max_hp = 1470
        character.inventory_map = Counter(
            {
                'cooked_chicken': 34,  # 80
                'cooked_salmon': 33,  # 400
                'apple_pie': 18,  # 350
                'cooked_wolf_meat': 14,  # 200
                'cooked_trout': 13,  # 225
                'cooked_beef': 6,  # 150
                'efreet_cloth': 4,
            }
        )
        result: Dict[str, int] = self.food_service.get_best_food_to_consume(character, required_hp)

        self.assertDictEqual({'apple_pie': 2, 'cooked_salmon': 1}, result)

    def test_consumables_12(self):
        character: CharacterSchemaExtension = self.local_env.service.get_character_details(character_1_name())
        required_hp = 1375  # missing: 1094
        character.max_hp = 1470

        remaining_hp_counter = Counter([281, 281])

        result: Dict[str, int] = self.food_service.get_best_food_to_gather(
            remaining_hp_counter=remaining_hp_counter,
            required_hp=required_hp,
            max_hp=character.max_hp,
            character_level=character.level,
        )

        self.assertDictEqual({'cooked_bass': 2, 'corrupted_fruit': 2}, result)

    def test_consumables_13(self):
        character: CharacterSchemaExtension = self.local_env.service.get_character_details(character_1_name())
        character.hp = 281
        required_hp = 1375  # missing: 1094
        character.max_hp = 1470

        context = ExecutionContext()
        context.set_bank_items_map(
            {
                'apple_pie': 30,  # 350
                'cooked_salmon': 50,  # 400
                'cooked_wolf_meat': 30,  # 200
                'cooked_beef': 20,  # 150
                'cooked_trout': 40,  # 225
                'cooked_chicken': 50,  # 80
                'efreet_cloth': 4,
            }
        )
        fight_times = 50
        result: Dict[str, int] = self.food_service.get_best_food_to_withdraw(
            character=character, required_hp=required_hp, lost_hps_per_fight=[542], fight_times=fight_times, context=context
        )

        self.assertDictEqual(
            {
                'apple_pie': 30,
                'cooked_beef': 20,
                'cooked_chicken': 3,
                'cooked_salmon': 17,
                'cooked_trout': 8,
                'cooked_wolf_meat': 27,
            },
            result,
        )
