from typing import Dict, List

from quest_leader_service import QuestLeaderService
from single_quest_service import SingleQuestService

from artifactsmmo.extensions import CharacterSchemaExtension
from artifactsmmo.service.service import Service
from artifactsmmo.service.tasks import Task


class QuestConfigService:
    def __init__(self, service: Service):
        self.quest_leader_service = QuestLeaderService(service)
        self.single_quest_service = SingleQuestService(service)

    def get_quest_leaders(self, characters: List[CharacterSchemaExtension]) -> Dict[str, List[Task]]:
        quest_leaders: Dict[str, List[Task]] = {}
        for character in characters:
            tasks = self.quest_leader_service.get_task_list(character)
            if tasks:
                quest_leaders[character.name] = tasks
        return quest_leaders

    def get_character_quest(self, character: CharacterSchemaExtension) -> List[Task]:
        return self.single_quest_service.get_task_list(character)
