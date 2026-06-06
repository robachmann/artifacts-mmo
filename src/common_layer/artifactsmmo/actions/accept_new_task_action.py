from artifactsmmo.actions.action_result import ActionResult
from artifactsmmo.actions.action_strategy import ActionStrategy
from artifactsmmo.extensions import CharacterSchemaExtension
from artifactsmmo.log.logger import logger
from artifactsmmo.service.execution_context import ExecutionContext
from artifactsmmo.service.tasks import Task


class AcceptNewTaskAction(ActionStrategy):
    def action(self) -> str:
        return 'accept-new-task'

    @staticmethod
    def describe_task(task: Task) -> str:
        return ''

    def process(self, character: CharacterSchemaExtension, task: Task, quest_id: str = None, context: ExecutionContext = None) -> ActionResult:
        action_result: ActionResult = ActionResult()
        solve_task = bool(task.extra.get('solve_task', True))
        allow_cancellation = bool(task.extra.get('allow_cancellation', False))
        priority = task.extra.get('priority', 'time')

        status_code, result, error = self.actions_client.accept_task(character)
        match status_code:
            case 200:
                logger.info(
                    f'Successfully accepted a new task: type={result.task.type}, code={result.task.code}, '
                    f'total={result.task.total}, solve_task={solve_task}'
                )

                if solve_task:
                    task_id = task.task_id if task.task_id else Task.generate_task_id()
                    action_result.append(
                        Task.solve_task(
                            task_id=task_id,
                            task_type=str(result.task.type),
                            allow_cancellation=allow_cancellation,
                            priority=priority,
                        )
                    )

            case 499:  # The character is in cooldown.
                msg = error.get('message', '')
                character_cooldown = msg if msg else 'The character is in cooldown.'
                logger.info(f'{character_cooldown} Fetching current character again.')
                reloaded_character = self.service.get_character_details(character.name)
                action_result.update_character(reloaded_character)
                action_result.repeat()

            case 598:
                logger.info('Tasks Master not found on this map.')
                reloaded_character = self.service.get_character_details(character.name)
                action_result.update_character(reloaded_character)
                action_result.append(Task.move(content_type='tasks_master', content_code='monsters'))
                action_result.repeat()

            case _:
                logger.error(f'Unexpected response: {error}')
                action_result.abort(f'{task.action}: {error}')

        if result and result.character:
            action_result.update_character(result.character)
        return action_result
