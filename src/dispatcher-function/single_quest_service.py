from typing import List

from quest_service import QuestService

from artifactsmmo.extensions import CharacterSchemaExtension
from artifactsmmo.service.tasks import Task


class SingleQuestService(QuestService):
    def _character_1(self, character: CharacterSchemaExtension) -> List[Task]:
        return []

    def _character_2(self, character: CharacterSchemaExtension) -> List[Task]:
        return []

    def _character_3(self, character: CharacterSchemaExtension) -> List[Task]:
        return []

    def _character_4(self, character: CharacterSchemaExtension) -> List[Task]:
        return []

    def _character_5(self, character: CharacterSchemaExtension) -> List[Task]:
        return []
