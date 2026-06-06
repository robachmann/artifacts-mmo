import unittest

from artifactsmmo.models import GatheringSkill
from artifactsmmo.service.tasks import Task
from local_environment import LocalEnvironment


class TestLevelSkillTask(unittest.TestCase):
    def setUp(self):
        self.local_env = LocalEnvironment()

    def test_level_fishing_skill(self):
        skill = GatheringSkill.FISHING
        character = self.local_env.service.get_character_details(self.local_env.character_4_name)

        task = Task.level_gathering_skill(skill, target_level=45)
        character.skills[skill].level = 1

        result = self.local_env.task_processor.process_task(task, character)
        self.assertEqual(5, len(result.new_tasks))

        self.assertEqual('gather-resource', result.new_tasks[0].action)
        self.assertEqual('gudgeon_fishing_spot', result.new_tasks[0].extra['resource'])
        self.assertEqual(1, int(result.new_tasks[0].extra['quantity']))
        self.assertEqual(skill, result.new_tasks[0].until.skill_name)
        self.assertEqual(10, int(result.new_tasks[0].until.skill_level))

        self.assertEqual('gather-resource', result.new_tasks[1].action)
        self.assertEqual('shrimp_fishing_spot', result.new_tasks[1].extra['resource'])
        self.assertEqual(1, int(result.new_tasks[1].extra['quantity']))
        self.assertEqual(skill, result.new_tasks[1].until.skill_name)
        self.assertEqual(20, int(result.new_tasks[1].until.skill_level))

        self.assertEqual('gather-resource', result.new_tasks[2].action)
        self.assertEqual('trout_fishing_spot', result.new_tasks[2].extra['resource'])
        self.assertEqual(1, int(result.new_tasks[2].extra['quantity']))
        self.assertEqual(skill, result.new_tasks[2].until.skill_name)
        self.assertEqual(30, int(result.new_tasks[2].until.skill_level))

        self.assertEqual('gather-resource', result.new_tasks[3].action)
        self.assertEqual('bass_fishing_spot', result.new_tasks[3].extra['resource'])
        self.assertEqual(1, int(result.new_tasks[3].extra['quantity']))
        self.assertEqual('fishing', result.new_tasks[3].until.skill_name)
        self.assertEqual(40, int(result.new_tasks[3].until.skill_level))

        self.assertEqual('gather-resource', result.new_tasks[4].action)
        self.assertEqual('salmon_fishing_spot', result.new_tasks[4].extra['resource'])
        self.assertEqual(1, int(result.new_tasks[4].extra['quantity']))
        self.assertEqual(skill, result.new_tasks[4].until.skill_name)
        self.assertEqual(45, int(result.new_tasks[4].until.skill_level))

    def test_level_woodcutting_skill(self):
        skill = GatheringSkill.WOODCUTTING
        character = self.local_env.service.get_character_details(self.local_env.character_4_name)

        task = Task.level_gathering_skill(skill, target_level=45)
        character.skills[skill].level = 1

        result = self.local_env.task_processor.process_task(task, character)
        self.assertEqual(5, len(result.new_tasks))

        self.assertEqual('gather-resource', result.new_tasks[0].action)
        self.assertEqual('ash_tree', result.new_tasks[0].extra['resource'])
        self.assertEqual(1, int(result.new_tasks[0].extra['quantity']))
        self.assertEqual(skill, result.new_tasks[0].until.skill_name)
        self.assertEqual(10, int(result.new_tasks[0].until.skill_level))

        self.assertEqual('gather-resource', result.new_tasks[1].action)
        self.assertEqual('spruce_tree', result.new_tasks[1].extra['resource'])
        self.assertEqual(1, int(result.new_tasks[1].extra['quantity']))
        self.assertEqual(skill, result.new_tasks[1].until.skill_name)
        self.assertEqual(20, int(result.new_tasks[1].until.skill_level))

        self.assertEqual('gather-resource', result.new_tasks[2].action)
        self.assertEqual('birch_tree', result.new_tasks[2].extra['resource'])
        self.assertEqual(1, int(result.new_tasks[2].extra['quantity']))
        self.assertEqual(skill, result.new_tasks[2].until.skill_name)
        self.assertEqual(30, int(result.new_tasks[2].until.skill_level))

        self.assertEqual('gather-resource', result.new_tasks[3].action)
        self.assertEqual('dead_tree', result.new_tasks[3].extra['resource'])
        self.assertEqual(1, int(result.new_tasks[3].extra['quantity']))
        self.assertEqual(skill, result.new_tasks[3].until.skill_name)
        self.assertEqual(40, int(result.new_tasks[3].until.skill_level))

        self.assertEqual('gather-resource', result.new_tasks[4].action)
        self.assertEqual('maple_tree', result.new_tasks[4].extra['resource'])
        self.assertEqual(1, int(result.new_tasks[4].extra['quantity']))
        self.assertEqual(skill, result.new_tasks[4].until.skill_name)
        self.assertEqual(45, int(result.new_tasks[4].until.skill_level))

    def test_level_mining_skill(self):
        skill = GatheringSkill.MINING
        character = self.local_env.service.get_character_details(self.local_env.character_4_name)

        task = Task.level_gathering_skill(skill, target_level=45)
        character.skills[skill].level = 1

        result = self.local_env.task_processor.process_task(task, character)
        self.assertEqual(5, len(result.new_tasks))

        self.assertEqual('gather-resource', result.new_tasks[0].action)
        self.assertEqual('copper_rocks', result.new_tasks[0].extra['resource'])
        self.assertEqual(1, int(result.new_tasks[0].extra['quantity']))
        self.assertEqual(skill, result.new_tasks[0].until.skill_name)
        self.assertEqual(10, int(result.new_tasks[0].until.skill_level))

        self.assertEqual('gather-resource', result.new_tasks[1].action)
        self.assertEqual('iron_rocks', result.new_tasks[1].extra['resource'])
        self.assertEqual(1, int(result.new_tasks[1].extra['quantity']))
        self.assertEqual(skill, result.new_tasks[1].until.skill_name)
        self.assertEqual(20, int(result.new_tasks[1].until.skill_level))

        self.assertEqual('gather-resource', result.new_tasks[2].action)
        self.assertEqual('coal_rocks', result.new_tasks[2].extra['resource'])
        self.assertEqual(1, int(result.new_tasks[2].extra['quantity']))
        self.assertEqual(skill, result.new_tasks[2].until.skill_name)
        self.assertEqual(30, int(result.new_tasks[2].until.skill_level))

        self.assertEqual('gather-resource', result.new_tasks[3].action)
        self.assertEqual('gold_rocks', result.new_tasks[3].extra['resource'])
        self.assertEqual(1, int(result.new_tasks[3].extra['quantity']))
        self.assertEqual(skill, result.new_tasks[3].until.skill_name)
        self.assertEqual(40, int(result.new_tasks[3].until.skill_level))

        self.assertEqual('gather-resource', result.new_tasks[4].action)
        self.assertEqual('mithril_rocks', result.new_tasks[4].extra['resource'])
        self.assertEqual(1, int(result.new_tasks[4].extra['quantity']))
        self.assertEqual(skill, result.new_tasks[4].until.skill_name)
        self.assertEqual(45, int(result.new_tasks[4].until.skill_level))

    def test_level_alchemy_skill_gap(self):
        skill = GatheringSkill.ALCHEMY
        character = self.local_env.service.get_character_details(self.local_env.character_4_name)

        task = Task.level_gathering_skill(skill, target_level=45)
        character.skills[skill].level = 1

        result = self.local_env.task_processor.process_task(task, character)
        self.assertEqual(1, len(result.new_tasks))

        self.assertEqual('gather-resource', result.new_tasks[0].action)
        self.assertEqual('sunflower_field', result.new_tasks[0].extra['resource'])
        self.assertEqual(1, int(result.new_tasks[0].extra['quantity']))
        self.assertEqual(skill, result.new_tasks[0].until.skill_name)
        self.assertEqual(11, int(result.new_tasks[0].until.skill_level))

    def test_level_alchemy_skill_gap2(self):
        skill = GatheringSkill.ALCHEMY
        character = self.local_env.service.get_character_details(self.local_env.character_4_name)

        task = Task.level_gathering_skill(skill, target_level=45)
        character.skills[skill].level = 28

        result = self.local_env.task_processor.process_task(task, character)
        self.assertEqual(1, len(result.new_tasks))

        self.assertEqual('gather-resource', result.new_tasks[0].action)
        self.assertEqual('nettle', result.new_tasks[0].extra['resource'])
        self.assertEqual(1, int(result.new_tasks[0].extra['quantity']))
        self.assertEqual(skill, result.new_tasks[0].until.skill_name)
        self.assertEqual(30, int(result.new_tasks[0].until.skill_level))

    def test_level_woodcutting_skill_2(self):
        skill = GatheringSkill.WOODCUTTING
        character = self.local_env.service.get_character_details(self.local_env.character_5_name)

        task = Task.level_gathering_skill(skill, target_level=35)
        character.skills[skill].level = 18

        result = self.local_env.task_processor.process_task(task, character)
        self.assertEqual(3, len(result.new_tasks))

        self.assertEqual('gather-resource', result.new_tasks[0].action)
        self.assertEqual('spruce_tree', result.new_tasks[0].extra['resource'])
        self.assertEqual(1, int(result.new_tasks[0].extra['quantity']))
        self.assertEqual(skill, result.new_tasks[0].until.skill_name)
        self.assertEqual(20, int(result.new_tasks[0].until.skill_level))

        self.assertEqual('gather-resource', result.new_tasks[1].action)
        self.assertEqual('birch_tree', result.new_tasks[1].extra['resource'])
        self.assertEqual(1, int(result.new_tasks[1].extra['quantity']))
        self.assertEqual(skill, result.new_tasks[1].until.skill_name)
        self.assertEqual(30, int(result.new_tasks[1].until.skill_level))

        self.assertEqual('gather-resource', result.new_tasks[2].action)
        self.assertEqual('dead_tree', result.new_tasks[2].extra['resource'])
        self.assertEqual(1, int(result.new_tasks[2].extra['quantity']))
        self.assertEqual(skill, result.new_tasks[2].until.skill_name)
        self.assertEqual(35, int(result.new_tasks[2].until.skill_level))
