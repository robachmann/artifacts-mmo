from artifactsmmo.actions.action_result import ActionResult
from artifactsmmo.actions.action_strategy import ActionStrategy
from artifactsmmo.extensions import CharacterSchemaExtension
from artifactsmmo.log.logger import logger
from artifactsmmo.service.execution_context import ExecutionContext
from artifactsmmo.service.tasks import Task


class RestAction(ActionStrategy):
    def action(self) -> str:
        return 'rest'

    def process(self, character: CharacterSchemaExtension, task: Task, quest_id: str = None, context: ExecutionContext = None) -> ActionResult:
        action_result: ActionResult = ActionResult()

        if character.hp < character.max_hp:
            status_code, result, error = self.actions_client.rest(character)

            match status_code:
                case 200:
                    logger.info(f'The character has rested {result.cooldown.total_seconds}s and restored {result.hp_restored}hp')
                    self.counters_table.increment('restored_hp', 'rests', result.hp_restored)

                case 499:  # The character is in cooldown.
                    msg = error.get('message', '')
                    character_cooldown = msg if msg else 'The character is in cooldown.'
                    logger.info(f'{character_cooldown} Fetching current character again.')
                    reloaded_character = self.service.get_character_details(character.name)
                    action_result.update_character(reloaded_character)
                    action_result.repeat()

                case _:
                    logger.error(f'Unexpected response: {error}')
                    action_result.abort(f'{task.action}: {error}')

            if result and result.character:
                action_result.update_character(result.character)
        else:
            logger.info(f'Character HP is already full: {character.hp}/{character.max_hp}')

        return action_result
