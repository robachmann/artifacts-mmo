from copy import deepcopy
from datetime import datetime, UTC
from typing import List

from artifactsmmo.dynamodb.character_table import CharacterTable
from artifactsmmo.extensions import CharacterSchemaExtension
from artifactsmmo.log.logger import logger
from artifactsmmo.models import ItemType
from artifactsmmo.quests.quests import Quest
from artifactsmmo.queue.worker_queue import WorkerQueue
from artifactsmmo.service.execution_context import ExecutionContext
from artifactsmmo.service.service import Service
from artifactsmmo.service.tasks import Task


class DispatchService:
    def __init__(self, service: Service, character_table: CharacterTable, worker_queue: WorkerQueue):
        self.service = service
        self.character_table: CharacterTable = character_table
        self.worker_queue: WorkerQueue = worker_queue

    def dispatch(
        self,
        task_list: List[Task],
        quest_id: str,
        is_new_quest_id: bool,
        character: CharacterSchemaExtension,
        status: str = None,
        leader: str = None,
        created_at: datetime = None,
        skip_pre_tasks: bool = False,
        skip_post_tasks: bool = False,
        active_quest: Quest = None,
    ):
        active_quest = active_quest or self.character_table.get_quest(character.name)
        created_at = created_at or (active_quest.created_at if active_quest else datetime.now(UTC))

        tasks: List[Task] = deepcopy(task_list)
        quest = Quest(
            character_name=character.name,
            tasks=tasks,
            quest_id=quest_id,
            status=status,
            leader=leader,
            created_at=created_at,
        )
        quest.generate_description()

        should_rest = False
        if quest.tasks:
            should_rest = True
            if not self._requires_task_rewards(quest.tasks) and not any(task.action == 'solve-event' for task in tasks):
                quest.tasks.insert(0, Task.solve_task(start_solving=False))

        pre_tasks = [] if skip_pre_tasks else [Task.ensure_inventory(keep_consumables=True), Task.unequip_all(), Task.ensure_inventory()]

        quest.tasks = [
            *pre_tasks,
            *quest.tasks,
            Task.finish_quest(skip_post_tasks=skip_post_tasks, rest=should_rest),
        ]

        self.character_table.put_quest(character.name, quest, context=ExecutionContext(character.name))
        logger.debug('quest=%s', quest.to_dict())

        if not active_quest or character.at_success_position() or is_new_quest_id:
            remaining_cooldown = (character.cooldown_expiration - datetime.now(UTC)).total_seconds()
            cooldown_seconds = int(max(remaining_cooldown, 0))
            self.worker_queue.send_tasks(character, delay_seconds=cooldown_seconds, quest_id=quest.quest_id)
            logger.info(f'Dispatched quest={quest.quest_id} to character={character.name}')

    def _requires_task_rewards(self, tasks: List[Task]) -> bool:
        for task in tasks:
            if task.action == 'craft-recipe':
                item_code = task.extra.get('item')
                item = self.service.get_item(item_code)
                if item.type == ItemType.RESOURCE and item.subtype == 'task':
                    return True
                elif item.craft:
                    for craft in item.craft.items:
                        craft_item = self.service.get_item(craft.code)
                        if craft_item.type == ItemType.RESOURCE and craft_item.subtype == 'task':
                            return True
            elif task.action == 'solve-task':
                return True
        return False
