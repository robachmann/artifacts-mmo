import unittest

from artifactsmmo.models import CraftSkill
from artifactsmmo.service.execution_context import ExecutionContext
from artifactsmmo.service.tasks import Task
from local_environment import LocalEnvironment


class TestLevelSkillTask(unittest.TestCase):
    def setUp(self):
        self.local_env = LocalEnvironment()

    def test_level_jewelrycrafting_skill(self):
        skill = CraftSkill.JEWELRYCRAFTING
        character = self.local_env.service.get_character_details(self.local_env.character_1_name)
        target_level = 41
        task = Task.level_crafting_skill(skill, target_level=target_level)
        character.skills[skill].level = 35
        character.skills[skill].xp = 0
        context = ExecutionContext.local()

        result = self.local_env.task_processor.process_task(task, character, context)
        self.assertEqual(5, len(result.new_tasks))

        self.assertEqual('gather-recipe', result.new_tasks[0].action)
        self.assertEqual('gold_ring', result.new_tasks[0].extra['item'])
        self.assertEqual(156, int(result.new_tasks[0].extra['quantity']))

        self.assertEqual('craft-recipe', result.new_tasks[1].action)
        self.assertEqual('gold_ring', result.new_tasks[1].extra['item'])
        self.assertEqual(156, int(result.new_tasks[1].extra['quantity']))
        self.assertEqual('recycle', result.new_tasks[1].extra['target'])

        self.assertEqual('gather-recipe', result.new_tasks[2].action)
        self.assertEqual('gold_ring', result.new_tasks[2].extra['item'])
        self.assertEqual(39, int(result.new_tasks[2].extra['quantity']))

        self.assertEqual('craft-recipe', result.new_tasks[3].action)
        self.assertEqual('gold_ring', result.new_tasks[3].extra['item'])
        self.assertEqual(39, int(result.new_tasks[3].extra['quantity']))
        self.assertEqual('recycle', result.new_tasks[3].extra['target'])

        self.assertEqual('level-crafting-skill', result.new_tasks[4].action)
        self.assertEqual(target_level, result.new_tasks[4].extra['level'])

    def test_level_weaponcrafting_skill(self):
        skill = CraftSkill.WEAPONCRAFTING
        character = self.local_env.service.get_character_details(self.local_env.character_1_name)
        target_level = 5
        task = Task.level_crafting_skill(skill, target_level=target_level)
        character.skills[skill].level = 4
        character.skills[skill].xp = character.skills[skill].max_xp - 1
        context = ExecutionContext.local()

        result = self.local_env.task_processor.process_task(task, character, context)
        self.assertEqual(3, len(result.new_tasks))

        self.assertEqual('gather-recipe', result.new_tasks[0].action)
        self.assertEqual('copper_dagger', result.new_tasks[0].extra['item'])
        self.assertEqual(1, int(result.new_tasks[0].extra['quantity']))

        self.assertEqual('craft-recipe', result.new_tasks[1].action)
        self.assertEqual('copper_dagger', result.new_tasks[1].extra['item'])
        self.assertEqual(1, int(result.new_tasks[1].extra['quantity']))
        self.assertEqual('recycle', result.new_tasks[1].extra['target'])

        self.assertEqual('level-crafting-skill', result.new_tasks[2].action)
        self.assertEqual(target_level, result.new_tasks[2].extra['level'])

    def test_level_cooking_skill(self):
        skill = CraftSkill.COOKING
        character = self.local_env.service.get_character_details(self.local_env.character_3_name)
        target_level = 20
        task = Task.level_crafting_skill(skill, target_level=target_level)
        character.skills[skill].level = 1
        character.skills[skill].xp = 0
        context = ExecutionContext.local()

        result = self.local_env.task_processor.process_task(task, character, context)
        self.assertEqual(3, len(result.new_tasks))

        self.assertEqual('gather-recipe', result.new_tasks[0].action)
        self.assertEqual('cooked_gudgeon', result.new_tasks[0].extra['item'])

        self.assertEqual('craft-recipe', result.new_tasks[1].action)
        self.assertEqual('cooked_gudgeon', result.new_tasks[1].extra['item'])
        self.assertEqual(1009, int(result.new_tasks[1].extra['quantity']))
        self.assertEqual('bank', result.new_tasks[1].extra['target'])

        self.assertEqual('level-crafting-skill', result.new_tasks[2].action)
        self.assertEqual(target_level, result.new_tasks[2].extra['level'])

    def test_level_woodcutting_skill(self):
        skill = CraftSkill.WOODCUTTING
        character = self.local_env.service.get_character_details(self.local_env.character_5_name)
        target_level = 35
        task = Task.level_crafting_skill(skill, target_level=target_level)
        character.skills[skill].level = 18
        character.skills[skill].xp = 0
        context = ExecutionContext.local()

        result = self.local_env.task_processor.process_task(task, character, context)
        self.assertEqual(3, len(result.new_tasks))

        self.assertEqual('gather-recipe', result.new_tasks[0].action)
        self.assertEqual('spruce_plank', result.new_tasks[0].extra['item'])

        self.assertEqual('craft-recipe', result.new_tasks[1].action)
        self.assertEqual('spruce_plank', result.new_tasks[1].extra['item'])
        self.assertEqual(550, int(result.new_tasks[1].extra['quantity']))
        self.assertEqual('bank', result.new_tasks[1].extra['target'])

        self.assertEqual('level-crafting-skill', result.new_tasks[2].action)
        self.assertEqual(target_level, result.new_tasks[2].extra['level'])

    def test_level_woodcutting_skill_2(self):
        skill = CraftSkill.WOODCUTTING
        character = self.local_env.service.get_character_details(self.local_env.character_5_name)
        target_level = 35
        task = Task.level_crafting_skill(skill, target_level=target_level, stock_only=True)
        character.skills[skill].level = 24
        character.skills[skill].xp = 0
        context = ExecutionContext.local()

        result = self.local_env.task_processor.process_task(task, character, context)
        self.assertEqual(3, len(result.new_tasks))

        self.assertEqual('gather-recipe', result.new_tasks[0].action)
        self.assertEqual('spruce_plank', result.new_tasks[0].extra['item'])

        self.assertEqual('craft-recipe', result.new_tasks[1].action)
        self.assertEqual('spruce_plank', result.new_tasks[1].extra['item'])
        self.assertEqual(550, int(result.new_tasks[1].extra['quantity']))
        self.assertEqual('bank', result.new_tasks[1].extra['target'])

        self.assertEqual('level-crafting-skill', result.new_tasks[2].action)
        self.assertEqual(target_level, result.new_tasks[2].extra['level'])
