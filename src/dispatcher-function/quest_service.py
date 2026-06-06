from abc import ABC
from typing import Callable, Dict, List

from artifactsmmo.extensions import CharacterSchemaExtension
from artifactsmmo.log.logger import logger
from artifactsmmo.service.helpers import character_1_name, character_2_name, character_3_name, character_4_name, character_5_name
from artifactsmmo.service.service import Service
from artifactsmmo.service.tasks import Task


class QuestService(ABC):
    def __init__(self, service: Service):
        self.service = service
        self._handlers: Dict[str, Callable[[CharacterSchemaExtension], List[Task]]] = {
            character_1_name(): self._character_1,
            character_2_name(): self._character_2,
            character_3_name(): self._character_3,
            character_4_name(): self._character_4,
            character_5_name(): self._character_5,
        }

    def get_task_list(self, character: CharacterSchemaExtension) -> List[Task]:
        handler = self._handlers.get(character.name)
        if handler:
            return handler(character)
        else:
            logger.error(f'Unknown character: {character.name}')
            return []

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
