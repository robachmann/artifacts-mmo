import copy
from datetime import datetime, UTC
import json
import os
import traceback
from typing import Dict, List, Optional, Set, Tuple

from aws_lambda_powertools.utilities.data_classes import event_source, SQSEvent
from aws_lambda_powertools.utilities.typing import LambdaContext

from artifactsmmo.actions.action_processor import ActionProcessor
from artifactsmmo.client.actions import ActionsClient
from artifactsmmo.client.client import Client
from artifactsmmo.dynamodb.character_table import CharacterTable
from artifactsmmo.dynamodb.counters_table import CountersTable
from artifactsmmo.dynamodb.logs_table import LogsTable
from artifactsmmo.dynamodb.processed_messages_table import ProcessedMessagesTable
from artifactsmmo.dynamodb.skill_stats_table import SkillStatsTable
from artifactsmmo.dynamodb.skip_events_table import SkipEventsTable
from artifactsmmo.dynamodb.task_progress_table import TaskProgress, TaskProgressTable
from artifactsmmo.extensions import CharacterSchemaExtension
from artifactsmmo.log.logger import logger
from artifactsmmo.models import CharacterSchema, LogSchema
from artifactsmmo.quests.quests import Quest
from artifactsmmo.queue.dispatcher_queue import DispatcherQueue
from artifactsmmo.queue.worker_queue import WorkerQueue
from artifactsmmo.service.execution_context import ExecutionContext
from artifactsmmo.service.food_service import FoodService
from artifactsmmo.service.quest_process import QuestProcessResult, QuestProcessStatus
from artifactsmmo.service.report import Report
from artifactsmmo.service.service import Service
from artifactsmmo.service.task_processor import TaskProcessor
from artifactsmmo.service.tasks import Task
from artifactsmmo.service.until import Status
from artifactsmmo.telegram.client import TelegramClient
from artifactsmmo.templates.template_processor import TemplateProcessor


class Worker:
    def __init__(self):
        if os.environ.get('AWS_LAMBDA_FUNCTION_NAME') is None:
            from dotenv import load_dotenv

            load_dotenv()

        self.character_table: CharacterTable = CharacterTable()
        self.worker_queue: WorkerQueue = WorkerQueue()
        self.service: Service = Service(Client())
        self.food_service: FoodService = FoodService(self.service)
        self.task_progress_table: TaskProgressTable = TaskProgressTable()
        actions_client: ActionsClient = ActionsClient()
        telegram_client: TelegramClient = TelegramClient()
        skill_stats_table = SkillStatsTable()
        counters_table = CountersTable()
        action_processor: ActionProcessor = ActionProcessor(
            actions_client,
            self.service,
            counters_table,
            telegram_client,
            self.task_progress_table,
            skill_stats_table,
            self.food_service,
            self.character_table,
        )
        template_processor: TemplateProcessor = TemplateProcessor(self.service.client, self.service, telegram_client, self.food_service)
        self.telegram_client = telegram_client
        self.logs_table: LogsTable = LogsTable()
        self.report: Report = Report(self.service)
        self.processor: TaskProcessor = TaskProcessor(
            actions=action_processor,
            template_processor=template_processor,
            telegram_client=self.telegram_client,
            task_progress_table=self.task_progress_table,
            service=self.service,
        )
        self.dispatcher_queue = DispatcherQueue()
        self.skip_events_table = SkipEventsTable()
        self.processed_messages_table = ProcessedMessagesTable()

    def handler(self, event: SQSEvent, context: LambdaContext):
        logger.debug('Received Event.')
        try:
            self.process_event(event)
        except Exception:
            logger.error(traceback.format_exc())
        return {'statusCode': 200, 'body': json.dumps({'status': 'ok'})}

    def process_event(self, event):
        if event is None:
            logger.error('Event is None, skipping process.')
            return

        for record in event.records:
            character = CharacterSchemaExtension(CharacterSchema.from_dict(record.json_body))
            logger.append_keys(message_id=record.message_id, character_name=character.name)
            should_process = self.processed_messages_table.track_processed_message(record.message_id)
            if should_process:
                quest_id = self.__extract_quest_id(record)
                result = self.process_record(character, quest_id)
                self.process_result(result)
            logger.remove_keys(['character_name', 'message_id', 'quest_id'])

    def process_record(self, character: CharacterSchemaExtension, quest_id: str) -> QuestProcessResult:
        delay_seconds = self.get_delay_seconds(character.cooldown_expiration)
        if delay_seconds >= 1:
            delay_seconds = int(delay_seconds)
            logger.info(f'Cooldown not reached yet. Placing message in the queue again with delay_seconds={delay_seconds}')
            self.worker_queue.send_tasks(character, delay_seconds=delay_seconds, quest_id=quest_id)
            return QuestProcessResult.continue_quest()
        else:
            logger.debug(f'Cooldown reached: character_expiration={character.cooldown_expiration}')

        quest = self.character_table.get_quest(character.name)
        if not quest or quest.quest_id != quest_id:
            logger.info(f"Persisted quest object's id={quest.quest_id if quest else 'None'} does not match expected quest_id={quest_id}")
            return QuestProcessResult.ignore_quest()

        if not quest:
            logger.info('No quest object found in DB. Cancelling quest.')
            return QuestProcessResult.ignore_quest()

        logger.append_keys(quest_id=quest.quest_id)

        context = ExecutionContext(character.name)

        while character and quest:
            tasks: List[Task] = quest.tasks
            if not tasks:
                if quest.result:
                    logger.info(f'Finish quest with result={quest.result}.')
                    cancelled = quest.result == 'cancelled'
                    return QuestProcessResult.finish(character, quest, cancelled=cancelled)
                else:
                    logger.info('No tasks found. Complete quest.')
                    return QuestProcessResult.complete(character, quest)

            current_task_index, current_task_ttl = self.get_current_task_index_and_ttl(quest, character)
            if current_task_index is None:
                logger.info('No active task found. Complete quest.')
                return QuestProcessResult.complete(character, quest)

            current_task = tasks[current_task_index]

            if character.at_failure_position() and quest.status != 'Return to start':
                logger.warning(f'Character stands at failure position, current task action: {current_task.action}. Skipping all tasks.')
                return QuestProcessResult.abort(character, quest)

            process_task_result = self.processor.process_task(current_task, character, quest.quest_id, context)

            new_tasks: List[Task] = process_task_result.new_tasks
            expiration: datetime = process_task_result.expiration
            character = process_task_result.character
            quest.result = process_task_result.quest_result
            if process_task_result.quest_status:
                quest.status = process_task_result.quest_status

            if process_task_result.clear_until:
                current_task.until = None
                logger.debug('Cleared "until" of current_task')

            if new_tasks:
                new_task_list: List[Task] = tasks[: current_task_index + 1]
                new_task_list.extend(new_tasks)
                logger.info(f'Added new tasks to existing list: {self.pretty_print(new_tasks)}')

                if current_task_ttl > 1:
                    current_task_copy = copy.deepcopy(current_task)
                    current_task_copy.ttl -= 1
                    new_task_list.append(current_task_copy)
                    logger.info(f'Added same task again with task_id={current_task_copy.task_id} ttl={current_task_copy.ttl}')
                elif current_task.until and current_task.until.status == Status.Interrupted:
                    current_task_copy = copy.deepcopy(current_task)
                    current_task_copy.until.status = Status.Todo
                    new_task_list.append(current_task_copy)
                    logger.info(
                        f'Added same task again ({current_task_copy.action}) with task_id={current_task_copy.task_id} '
                        f'until.status={current_task_copy.until.status}'
                    )

                new_task_list.extend(tasks[current_task_index + 1 :])
                new_task_list[current_task_index].ttl = 0
                quest.tasks = new_task_list
                logger.debug('current_task_index=%d, new_task_list=%d', current_task_index, len(new_task_list))
            else:
                if current_task.until and current_task.until.status == Status.Ongoing:
                    quest.tasks[current_task_index].ttl = 1
                else:
                    quest.tasks[current_task_index].ttl = max(quest.tasks[current_task_index].ttl - 1, 0)

            quest.tasks = self.reduce_tasks(quest.tasks)

            finished_task_ids: Set[str] = self.get_finished_task_ids(quest.tasks)
            if finished_task_ids and not quest.leader or quest.leader == character.name:
                for finished_task_id in finished_task_ids:
                    logger.info(f'Delete bank reservations of finished task_id={finished_task_id} for character={character.name}')
                    self.service.delete_bank_reservations(task_id=finished_task_id)

            quest.compact_task_list(character.name, finished_task_ids)

            quest, continue_quest = self.character_table.put_quest(character.name, quest, context=context)
            delay_seconds = self.get_delay_seconds(expiration)
            if not continue_quest:
                logger.info('Will not continue processing quest.')
                break

            if process_task_result.hibernate:
                logger.info(
                    f'Will not send message to queue but await an external trigger to continue '
                    f'quest.quest_id={quest.quest_id}, quest_id={quest_id}'
                )
                return QuestProcessResult.hibernate_quest()

            if delay_seconds > 0:
                self.worker_queue.send_tasks(character, delay_seconds=int(delay_seconds), quest_id=quest.quest_id)
                break
            else:
                logger.debug('delay_seconds=0, continue processing quest locally.')

        return QuestProcessResult.continue_quest()

    @staticmethod
    def get_finished_task_ids(tasks: List[Task]) -> Set[str]:
        all_finished: Dict[str, bool] = {}
        for task in tasks:
            if not task.task_id:
                continue
            # Once a task_id has a non-zero ttl, mark it unfinished permanently
            if task.task_id not in all_finished:
                all_finished[task.task_id] = task.ttl == 0
            elif all_finished[task.task_id] and task.ttl != 0:
                all_finished[task.task_id] = False

        return {task_id for task_id, is_finished in all_finished.items() if is_finished}

    def process_result(self, result: QuestProcessResult):
        match result.result:
            case QuestProcessStatus.Abort:
                self.finish_quest(result.character, result.quest, cancelled=True)
            case QuestProcessStatus.Cancel:
                self.finish_quest(result.character, result.quest, cancelled=True)
            case QuestProcessStatus.Complete:
                self.finish_quest(result.character, result.quest, cancelled=False)
            case QuestProcessStatus.Ignore:
                pass
            case QuestProcessStatus.Continue:
                pass

    def finish_quest(self, character: CharacterSchemaExtension, quest: Quest = None, cancelled: bool = False):
        logger.info('Reached the end of the task list.')
        logs: List[LogSchema] = self.service.get_logs(count=1, character_name=character.name)
        self.logs_table.upload_logs(logs)
        self.service.delete_bank_reservations(character_name=character.name)
        noop_task = self.report.send_report(character=character, quest=quest, cancelled=cancelled)
        self.character_table.delete_quest(character.name)
        if noop_task:
            if quest and quest.description == 'solve-event' and quest.status:
                self.skip_events_table.add_skip_entry(character.name, quest.status)
                logger.info(f'Quest was a noop event task for status={quest.status}. Invoking dispatcher queue')
                self.dispatcher_queue.invoke([character.name])
            elif quest and quest.leader:
                self.skip_events_table.add_skip_entry(character.name, quest.leader)
                logger.info(f'Quest was a noop event task for leader={quest.leader}. Invoking dispatcher queue')
                self.dispatcher_queue.invoke([character.name])
            elif quest and not quest.leader and quest.character_name == character.name:
                quest_leader = f'quest_leader={quest.leader}' if quest else 'quest=None'
                logger.info(f'Quest was a noop event task but {quest_leader}')
        elif quest and (quest.description == 'solve-event' or (quest.description and quest.description.startswith('buy-item'))) and quest.status:
            self.dispatcher_queue.invoke([character.name])
        else:
            logger.info('Quest was not a noop event task.')

    def get_current_task_index_and_ttl(self, quest: Quest, character: CharacterSchemaExtension) -> Tuple[Optional[int], Optional[int]]:
        for i, task in enumerate(quest.tasks):
            until = task.until

            if until:
                if until.status in {Status.Done, Status.Interrupted, Status.Cancelled}:
                    continue

                if until.date_time and datetime.now(UTC) < until.date_time:
                    logger.debug('Continue task %d/%d until %s', i, len(quest.tasks) - 1, until.date_time)
                    return i, 1

                if (
                    until.skill_name
                    and until.skill_level
                    and (
                        character.skills.get(until.skill_name).level < until.skill_level
                        if until.skill_name in character.skills
                        else character.level < until.skill_level
                    )
                ):
                    return i, 1

                if until.achievement_code:
                    if self.service.get_account_achievement(character.account, until.achievement_code).completed_at:
                        task.until.status = Status.Done
                        task.ttl = 0
                        logger.info(f'Removing achievement={until.achievement_code} from task list.')
                    else:
                        return i, 1

                if until.drop_count is not None:
                    if quest.quest_id and until.progress < until.drop_count:
                        drop_id = f'{task.task_id}.{until.drop_item}'
                        task_progress: Optional[TaskProgress] = self.task_progress_table.get_progress(quest_id=quest.quest_id, drop_item=drop_id)

                        if task_progress:
                            shared_progress = task_progress.counter
                            if until.progress != shared_progress:
                                logger.debug('Updated local progress=%d/%d for drop_item=%s', shared_progress, until.drop_count, drop_id)
                                until.progress = shared_progress
                            shared_target = task_progress.target or until.drop_count
                            if until.drop_count != shared_target:
                                logger.info(f'Updated local target {until.drop_count} -> {shared_target} for drop_item={drop_id}')
                                until.drop_count = shared_target
                        else:
                            self.task_progress_table.create(quest.quest_id, drop_id, until.drop_count, quest.leader)

                    if until.progress < until.drop_count:
                        logger.debug(
                            'Continue task %d/%d. Current drop_count of item %s: %d/%d',
                            i,
                            len(quest.tasks) - 1,
                            until.drop_item,
                            until.progress,
                            until.drop_count,
                        )
                        return i, 1
                    else:
                        until.status = Status.Done
                        task.ttl = 0

            elif task.ttl > 0:
                return i, task.ttl

        return None, None

    @staticmethod
    def pretty_print(new_tasks: List[Task]) -> str:
        action_types: List[Tuple[str, List[str]]] = []

        for i in range(len(new_tasks)):
            task = new_tasks[i]
            action = task.action
            extra = task.extra if task.extra is not None else {}

            subjects = [
                extra.get('item', ''),
                extra.get('slot', ''),
                extra.get('skill', ''),
                str(extra.get('level', '')),
                extra.get('monster', ''),
                extra.get('item_code', ''),
                str(extra.get('x', '')),
                str(extra.get('y', '')),
                extra.get('content_type', ''),
                extra.get('content_code', ''),
            ]

            subject = '/'.join([s for s in subjects if s])
            qty = task.extra.get('quantity') or 1
            text = f'{task.ttl * qty}x {subject}'

            if len(action_types) > 0 and action_types[-1][0] == action:
                action_types[-1][1].append(text)
            else:
                action_types.append((action, [text]))

        log_texts: List[str] = []
        for x in action_types:
            log_texts.append(f'{x[0]}: {", ".join(x[1])}'.replace(' 1x', '').removesuffix(': '))
        return ', '.join(log_texts)

    @staticmethod
    def get_delay_seconds(expiration: datetime) -> float:
        if expiration is None:
            return 0
        else:
            expire_ms = (expiration - datetime.now(UTC)).total_seconds()
            if expire_ms > 0:
                return expire_ms
            else:
                return 0

    @staticmethod
    def reduce_tasks(tasks: List[Task]) -> List[Task]:
        now = datetime.now(UTC)
        result: List[Task] = []
        for task in tasks:
            if task.until:
                expired = task.until.date_time and task.until.date_time < now
                interrupted = task.until.status == Status.Interrupted and task.ttl == 1
                if expired or interrupted:
                    continue
            result.append(task)
        return result

    @staticmethod
    def __extract_quest_id(record) -> Optional[str]:
        quest_id_obj = record.message_attributes.get('quest_id')
        if quest_id_obj:
            return quest_id_obj['stringValue']
        return None


worker = Worker()


@event_source(data_class=SQSEvent)
def handler(event: SQSEvent, context: LambdaContext):
    worker.handler(event, context)


if __name__ == '__main__':
    worker.handler(SQSEvent(data={}), LambdaContext())
