from datetime import datetime, UTC
from typing import List

from artifactsmmo.actions.action_processor import ActionProcessor
from artifactsmmo.actions.action_result import ActionResult
from artifactsmmo.dynamodb.task_progress_table import TaskProgressTable
from artifactsmmo.extensions import CharacterSchemaExtension
from artifactsmmo.log.logger import logger
from artifactsmmo.service.execution_context import ExecutionContext
from artifactsmmo.service.helpers import ProcessTaskResult
from artifactsmmo.service.service import Service
from artifactsmmo.service.tasks import Task
from artifactsmmo.service.until import Status
from artifactsmmo.telegram.client import TelegramClient
from artifactsmmo.templates.template_processor import TemplateProcessor
from artifactsmmo.templates.template_result import TemplateResult
from artifactsmmo.topic.log_aggregator_topic import LogAggregatorPublisher


class TaskProcessor:
    def __init__(
        self,
        actions: ActionProcessor,
        template_processor: TemplateProcessor,
        telegram_client: TelegramClient,
        task_progress_table: TaskProgressTable,
        service: Service,
    ):
        self.action_processor: ActionProcessor = actions
        self.template_processor: TemplateProcessor = template_processor
        self.telegram: TelegramClient = telegram_client
        self.task_progress_table = task_progress_table
        self.log_aggregator_topic: LogAggregatorPublisher = LogAggregatorPublisher()
        self.service: Service = service

    def process_task(
        self,
        current_task: Task,
        character: CharacterSchemaExtension,
        quest_id: str = None,
        context: ExecutionContext = None,
    ) -> ProcessTaskResult:
        action = current_task.action
        kind = current_task.kind
        extra = current_task.extra
        new_tasks: List[Task] = []
        expiration = datetime.now(UTC)
        until = current_task.until
        quest_result = None
        quest_status = None
        clear_until = False
        hibernate = False

        if hasattr(logger, 'append_keys'):
            logger.append_keys(kind=kind, action=action)
            if current_task.task_id:
                logger.append_keys(task_id=current_task.task_id)
        else:
            logger.warning('Logger does not support appending keys.')

        if until:
            logger.info(f'Process action={action}, extra={extra}, until={until.to_str()}, ttl={current_task.ttl}')
        else:
            logger.info(f'Process action={action}, extra={extra}, ttl={current_task.ttl}')

        match kind:
            case 'action':
                action_result: ActionResult = self.action_processor.process(current_task, character, quest_id, context)
                self.update_task_until(current_task, action_result, character.name, quest_id)

                if action_result.abort_quest:
                    new_tasks.append(Task.move_failure())
                    if action_result.abort_reason:
                        new_tasks.append(Task.send_message('⚠️ ' + action_result.abort_reason))
                    quest_result = 'failure'
                else:
                    if action_result.new_tasks:
                        new_tasks.extend(action_result.new_tasks)

                    if action_result.repeat_task:
                        new_tasks.append(
                            Task(
                                action=action,
                                kind=kind,
                                extra=extra,
                                task_id=current_task.task_id,
                                until=current_task.until,
                            )
                        )

                if action_result.character:
                    character = action_result.character

                if action_result.cooldown_expiration:
                    expiration = action_result.cooldown_expiration

            case 'template':
                template_result: TemplateResult = self.template_processor.process(current_task, character, quest_id, context)
                new_tasks.extend(template_result.new_tasks)

                if template_result.repeat_task:
                    new_tasks.append(
                        Task(
                            action=action,
                            kind=kind,
                            extra=extra,
                            task_id=current_task.task_id,
                            until=template_result.repeat_task_until,
                        )
                    )
                    logger.info(f'Added template again: action={action}, extra={extra}, until={template_result.repeat_task_until}')

                if template_result.status:
                    quest_status = template_result.status

                if template_result.should_clear_until:
                    clear_until = True

                if template_result.hibernate_quest:
                    hibernate = True

            case _:
                logger.error(f'Unknown kind={kind}, action={action}')

        if hasattr(logger, 'append_keys'):
            logger.remove_keys(['kind', 'action', 'task_id'])
        return ProcessTaskResult(new_tasks, expiration, character, quest_result, quest_status, clear_until, hibernate)

    def update_task_until(self, task: Task, action_result: ActionResult, character_name: str, quest_id: str = None):
        if task.until:
            if task.until.drop_item and action_result.drops:
                increment = action_result.drops.get(task.until.drop_item, 0)  # TODO: Consider using a list of drops
                if increment > 0:
                    if quest_id:
                        drop_id = f'{task.task_id}.{task.until.drop_item}'
                        task.until.progress = self.task_progress_table.update(
                            quest_id, drop_id, task.until.drop_count, character_name, increment
                        )
                    else:
                        task.until.progress += increment

                    logger.info(
                        f'Updated progress={task.until.progress}/{task.until.drop_count} for drop_item={task.task_id}.{task.until.drop_item}'
                    )
            if task.until.date_time and datetime.now(UTC) > task.until.date_time:
                new_status = Status.Done
                task.ttl = 0
            elif task.until.drop_count is not None and task.until.progress >= task.until.drop_count:
                new_status = Status.Done
                task.ttl = 0
            elif (
                task.until.skill_name
                and task.until.skill_level
                and action_result.character
                and action_result.character.skills
                and (
                    action_result.character.skills.get(task.until.skill_name).level >= task.until.skill_level
                    if task.until.skill_name in action_result.character.skills
                    else action_result.character.level >= task.until.skill_level
                )
            ):
                logger.info(f'skill={task.until.skill_name} target_level={task.until.skill_level} reached.')
                new_status = Status.Done
                task.ttl = 0
            elif task.until.achievement_code and self.__achievement_solved(task, action_result):
                logger.info(f'achievement={task.until.achievement_code} solved.')
                new_status = Status.Done
                task.ttl = 0
            elif action_result.skip_task:
                new_status = Status.Done
                if task.ttl > 1:
                    task.ttl = 1
                    logger.info('Task set to skip; setting task.ttl to 1')
            elif action_result.abort_quest:
                new_status = Status.Cancelled
            elif action_result.new_tasks:
                new_status = Status.Interrupted
            else:
                new_status = Status.Ongoing

            if new_status is not None and new_status != task.until.status:
                task.until.status = new_status
                logger.info(f"Updated current task's ('{task.action}') status to '{task.until.status}'")

    def __achievement_solved(self, task: Task, action_result: ActionResult) -> bool:
        if action_result.character:
            achievement = self.service.get_account_achievement(action_result.character.account, task.until.achievement_code)
            if achievement.completed_at:
                return True
            else:
                return False
        else:
            return False
