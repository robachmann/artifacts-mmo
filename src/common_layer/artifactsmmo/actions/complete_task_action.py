from datetime import datetime, timedelta, UTC

from telegram.constants import ParseMode

from artifactsmmo.actions.action_result import ActionResult
from artifactsmmo.actions.action_strategy import ActionStrategy
from artifactsmmo.extensions import CharacterSchemaExtension
from artifactsmmo.extensions.account_achievement_schema_extension import AccountAchievementSchemaExtension
from artifactsmmo.log.logger import logger
from artifactsmmo.service.execution_context import ExecutionContext
from artifactsmmo.service.helpers import escape_string
from artifactsmmo.service.tasks import NextMove, Task


class CompleteTaskAction(ActionStrategy):
    def action(self) -> str:
        return 'complete-task'

    @staticmethod
    def describe_task(task: Task) -> str:
        return ''

    def process(self, character: CharacterSchemaExtension, task: Task, quest_id: str = None, context: ExecutionContext = None) -> ActionResult:
        action_result: ActionResult = ActionResult()
        deposit_coins = bool(task.extra.get('deposit_coins', True))

        task_str = f'({character.task_total}x {character.task})'
        status_code, result, error = self.actions_client.complete_task(character)

        match status_code:
            case 200:
                log_str = ', '.join(f'{i.quantity}x {i.code}' for i in result.rewards.items)
                logger.info(f'Successfully completed a task {task_str} and received: {result.rewards.gold}g, {log_str}')
                if deposit_coins:
                    action_result.append(Task.ensure_inventory(task_id=task.task_id))

                achievement: AccountAchievementSchemaExtension = self.service.get_highest_task_achievement(character.account)
                if not achievement.completed_at or datetime.now(UTC) - achievement.completed_at < timedelta(minutes=5):
                    achievement_str = escape_string(f' [{achievement.progress}/{achievement.total}]')
                else:
                    achievement_str = ''

                reward_str = ', '.join(f'{i.quantity}x {escape_string(i.code)}' for i in result.rewards.items)
                self.telegram_client.send_notification(
                    f'⚜️ *{escape_string(character.name)}* completed a task {escape_string(task_str)} and '
                    f'received {result.rewards.gold}g, {reward_str}{achievement_str}\\.',
                    parse_mode=ParseMode.MARKDOWN_V2,
                )

                self.counters_table.increment('complete', 'tasks')
                for reward in result.rewards.items:
                    self.counters_table.increment(reward.code, 'rewards.complete.tasks', reward.quantity)

            case 488:  # The character has not completed the task.
                reloaded_character = self.service.get_character_details(character.name)
                action_result.update_character(reloaded_character)

                char_task = character.current_task
                character_current_task = (
                    f'character_current_task: task={char_task.task}, task_type={char_task.task_type}, '
                    f'task_progress={char_task.task_progress}, task_remaining={char_task.task_remaining}, '
                    f'task_total={char_task.task_total}'
                )

                reloaded_task = reloaded_character.current_task
                reloaded_character_task = (
                    f'reloaded_character_task: task={reloaded_task.task}, task_type={reloaded_task.task_type}, '
                    f'task_progress={reloaded_task.task_progress}, task_remaining={reloaded_task.task_remaining}, '
                    f'task_total={reloaded_task.task_total}'
                )
                logger.error(f'The character has not completed the task. {character_current_task}, {reloaded_character_task}')

            case 497:
                logger.info("The character's inventory is full.")
                reloaded_character = self.service.get_character_details(character.name)
                action_result.update_character(reloaded_character)
                action_result.append(Task.ensure_inventory(next_move=NextMove(content_type='tasks_master', content_code='monsters')))
                action_result.repeat()

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
