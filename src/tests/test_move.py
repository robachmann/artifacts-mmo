from collections import Counter
import unittest

from local_environment import LocalEnvironment

from artifactsmmo.service.tasks import Task


class TestLevelSkillTask(unittest.TestCase):
    def setUp(self):
        self.local_env = LocalEnvironment()
        self.spawn_map = self.local_env.service.get_map(0, 0)

    def test_move_same_cluster(self):
        character = self.local_env.service.get_character_details(self.local_env.character_1_name)
        character.x = self.spawn_map.x
        character.y = self.spawn_map.y
        character.layer = self.spawn_map.layer
        character.map_id = self.spawn_map.map_id
        task = Task.move(content_type='bank')
        result = self.local_env.task_processor.process_task(task, character)
        self.assertEqual(1, len(result.new_tasks))

    def test_move_teleport(self):
        character = self.local_env.service.get_character_details(self.local_env.character_1_name)
        character_map = self.local_env.service.get_map(-2, 6)
        character.x = character_map.x
        character.y = character_map.y
        character.layer = character_map.layer
        character.map_id = character_map.map_id
        character.inventory_map = Counter({'recall_potion': 1})
        task = Task.move(content_type='bank')
        result = self.local_env.task_processor.process_task(task, character)
        self.assertEqual(1, len(result.new_tasks))

    def test_move_different_cluster_free(self):
        character = self.local_env.service.get_character_details(self.local_env.character_1_name)
        character_map = self.spawn_map
        character.x = character_map.x
        character.y = character_map.y
        character.layer = character_map.layer
        character.map_id = character_map.map_id
        character.inventory_map = Counter({'recall_potion': 1})
        task = Task.move(content_type='monster', content_code='bat')
        result = self.local_env.task_processor.process_task(task, character)
        self.assertEqual(3, len(result.new_tasks))

    def test_move_different_cluster_paid(self):
        character = self.local_env.service.get_character_details(self.local_env.character_1_name)
        character_map = self.spawn_map
        character.x = character_map.x
        character.y = character_map.y
        character.layer = character_map.layer
        character.map_id = character_map.map_id
        character.inventory_map = Counter({'recall_potion': 1})
        task = Task.move(content_type='resource', content_code='palm_tree')
        result = self.local_env.task_processor.process_task(task, character)
        self.assertEqual(3, len(result.new_tasks))

    def test_move_multiple_clusters(self):
        character = self.local_env.service.get_character_details(self.local_env.character_1_name)
        character_map = self.spawn_map
        character.x = character_map.x
        character.y = character_map.y
        character.layer = character_map.layer
        character.map_id = character_map.map_id
        character.inventory_map = Counter({'recall_potion': 1})
        task = Task.move(content_type='monster', content_code='sandwhisper_empress')
        result = self.local_env.task_processor.process_task(task, character)
        self.assertEqual(3, len(result.new_tasks))

    def test_move_back(self):
        character = self.local_env.service.get_character_details(self.local_env.character_1_name)
        character_map = self.local_env.service.get_maps(content_type='monster', content_code='lich')[0]
        character.x = character_map.x
        character.y = character_map.y
        character.layer = character_map.layer
        character.map_id = character_map.map_id
        character.inventory_map = Counter()
        task = Task.move_success()
        result = self.local_env.task_processor.process_task(task, character)
        self.assertEqual(3, len(result.new_tasks))
