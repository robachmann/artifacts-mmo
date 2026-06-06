from artifactsmmo.actions.action_result import ActionResult
from artifactsmmo.actions.action_strategy import ActionStrategy
from artifactsmmo.extensions import CharacterSchemaExtension
from artifactsmmo.log.logger import logger
from artifactsmmo.service.execution_context import ExecutionContext
from artifactsmmo.service.tasks import Task


class ReloadCharacterAction(ActionStrategy):
    def action(self) -> str:
        return 'reload-character'

    def process(self, character: CharacterSchemaExtension, task: Task, quest_id: str = None, context: ExecutionContext = None) -> ActionResult:
        action_result = ActionResult()

        reloaded_character = self.service.get_character_details(character.name)
        action_result.update_character(reloaded_character)

        if character.cooldown_expiration != reloaded_character.cooldown_expiration:
            logger.info(
                f'Reloaded character and updated cooldown expiration from {character.cooldown_expiration} '
                f'to {reloaded_character.cooldown_expiration}.'
            )

        return action_result
