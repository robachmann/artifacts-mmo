from artifactsmmo import game_constants
from artifactsmmo.client.client import Client
from artifactsmmo.dynamodb.character_table import CharacterTable
from artifactsmmo.dynamodb.equipment_lock_table import EquipmentLockTable
from artifactsmmo.dynamodb.skill_stats_table import SkillStatsTable
from artifactsmmo.extensions import CharacterSchemaExtension, ItemSchemaExtension
from artifactsmmo.models import ItemSlot
from artifactsmmo.queue.dispatcher_queue import DispatcherQueue
from artifactsmmo.queue.worker_queue import WorkerQueue
from artifactsmmo.service.dispatch_service import DispatchService
from artifactsmmo.service.execution_context import ExecutionContext
from artifactsmmo.service.fight_simulator import FightSimulator
from artifactsmmo.service.food_service import FoodService
from artifactsmmo.service.service import Service
from artifactsmmo.service.tasks import Task
from artifactsmmo.telegram.client import TelegramClient
from artifactsmmo.templates.template_result import TemplateResult
from artifactsmmo.templates.template_strategy import TemplateStrategy


class UnequipAllTemplate(TemplateStrategy):
    def __init__(
        self,
        client: Client,
        service: Service,
        equipment_lock_table: EquipmentLockTable,
        telegram_client: TelegramClient,
        character_table: CharacterTable,
        skill_stats_table: SkillStatsTable,
        dispatch_service: DispatchService,
        dispatcher_queue: DispatcherQueue,
        worker_queue: WorkerQueue,
        food_service: FoodService,
        fight_simulator: FightSimulator,
    ):
        super().__init__(
            client,
            service,
            equipment_lock_table,
            telegram_client,
            character_table,
            skill_stats_table,
            dispatch_service,
            dispatcher_queue,
            worker_queue,
            food_service,
            fight_simulator,
        )
        self.gear_positions = set(game_constants.GEAR_POSITIONS + [ItemSlot.UTILITY1, ItemSlot.UTILITY2])
        self.gear_positions.discard('bag')

    def template(self) -> str:
        return 'unequip-all'

    def render(self, character: CharacterSchemaExtension, task: Task, quest_id: str = None, context: ExecutionContext = None) -> TemplateResult:
        template_result: TemplateResult = TemplateResult()

        max_items = character.inventory_max_items
        remaining_space = max_items - sum(item.quantity for item in character.inventory)
        all_character_details = self.service.get_all_character_details()

        for gear_position in self.gear_positions:
            item_code = getattr(character, f'{gear_position}_slot')
            if item_code:
                item = self.service.get_item(item_code)
                global_quantity = self.service.get_global_quantity(item_code)
                thresholds = {
                    'weapon': 1,
                    'boots': 1,
                    'helmet': 1,
                    'shield': 1,
                    'leg_armor': 1,
                    'body_armor': 1,
                    'amulet': 1,
                    'artifact': 1,
                    'rune': 1,
                    'bag': 1,
                    'ring': 2,
                }
                threshold = thresholds.get(item.type)
                eligible_character_count = sum(c.level >= item.level for c in all_character_details)
                if not threshold or global_quantity < (threshold * eligible_character_count) or item.is_confining_gear():
                    quantity = getattr(character, f'{gear_position}_slot_quantity', 1)
                    max_unequippable = min(remaining_space, quantity)
                    if max_unequippable > 0:
                        template_result.append(Task.unequip(slot=gear_position, quantity=max_unequippable))
                        remaining_space -= max_unequippable

                    if remaining_space == 0:
                        template_result.append(Task.ensure_inventory(task_id=task.task_id))
                        remaining_space = max_items

                    remainder_quantity = quantity - max_unequippable
                    if remainder_quantity > 0:
                        template_result.append(Task.unequip(slot=gear_position, quantity=remainder_quantity))
                        remaining_space -= remainder_quantity

        return template_result
