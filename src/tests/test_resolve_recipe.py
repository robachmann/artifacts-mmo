import unittest

from local_environment import LocalEnvironment


class TestLevelSkillTask(unittest.TestCase):
    def setUp(self):
        self.local_env = LocalEnvironment()

    def test_royal_skeleton_armor(self):
        bank_items_map = {
            'gold_bar': 16,
            'skeleton_armor': 2,
            'red_cloth': 6,
            'demoniac_dust': 6,
        }

        result = self.local_env.service.get_craftable_recipe_count('royal_skeleton_armor', bank_items_map)
        self.assertEqual(2, result)

    def test_royal_skeleton_armor_2(self):
        bank_items_map = {
            'gold_bar': 16,
            'skeleton_armor': 1,
            'red_cloth': 6,
            'demoniac_dust': 6,
            'skeleton_bone': 6,
            'wolf_bone': 3,
            'pig_skin': 2,
            'steel_bar': 4,
        }

        result = self.local_env.service.get_craftable_recipe_count('royal_skeleton_armor', bank_items_map)
        self.assertEqual(2, result)

    def test_royal_skeleton_armor_3(self):
        bank_items_map = {
            'gold_bar': 16,
            'skeleton_armor': 1,
            'red_cloth': 6,
            'demoniac_dust': 6,
            'skeleton_bone': 6,
            'wolf_bone': 3,
            'pig_skin': 2,
            'steel_bar': 2,
            'iron_ore': 6,
            'coal': 14,
        }

        result = self.local_env.service.get_craftable_recipe_count('royal_skeleton_armor', bank_items_map)
        self.assertEqual(2, result)
