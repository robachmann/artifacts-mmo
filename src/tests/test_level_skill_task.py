import unittest

from artifactsmmo.game_constants import MAX_LEVEL
from artifactsmmo.models import Skill, ActionType
from artifactsmmo.service.tasks import Task
from local_environment import LocalEnvironment


class TestLevelSkillTask(unittest.TestCase):
    def setUp(self):
        self.local_env = LocalEnvironment()

    def test_handler_runs_successfully(self):
        character = self.local_env.service.get_character_details(self.local_env.character_4_name)

        for level in range(1, MAX_LEVEL):
            for skill in character.skills:
                character.skills[skill].level = level
                task = Task.level_skill(skill=skill, level_approach=ActionType.CRAFTING)
                result = self.local_env.task_processor.process_task(task, character)
                self.assertEqual(1, len(result.new_tasks))
                if skill != Skill.FISHING:
                    self.assertEqual('level-crafting-skill', result.new_tasks[0].action, f'skill={skill}, target_level={level + 1}')
                else:
                    self.assertEqual('level-gathering-skill', result.new_tasks[0].action, f'skill={skill}, target_level={level + 1}')

                task = Task.level_skill(skill=skill, level_approach=ActionType.GATHERING)
                result = self.local_env.task_processor.process_task(task, character)
                self.assertEqual(1, len(result.new_tasks))
                if skill in (Skill.MINING, Skill.WOODCUTTING, Skill.FISHING, Skill.ALCHEMY):
                    self.assertEqual('level-gathering-skill', result.new_tasks[0].action, f'skill={skill}, target_level={level + 1}')
                else:
                    self.assertEqual('level-crafting-skill', result.new_tasks[0].action, f'skill={skill}, target_level={level + 1}')
