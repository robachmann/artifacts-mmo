from typing import Dict, List, Optional

from artifactsmmo.client.client import Client
from artifactsmmo.dynamodb.character_table import CharacterTable
from artifactsmmo.dynamodb.equipment_lock_table import EquipmentLockTable
from artifactsmmo.dynamodb.skill_stats_table import SkillStatsTable
from artifactsmmo.dynamodb.task_progress_table import TaskProgressTable
from artifactsmmo.extensions import CharacterSchemaExtension, ItemSchemaExtension, MonsterSchemaExtension
from artifactsmmo.extensions.resource_schema_extension import ResourceSchemaExtension
from artifactsmmo.game_constants import DEFAULT_SLEEP_TTL
from artifactsmmo.log.logger import logger
from artifactsmmo.models import CraftSkill
from artifactsmmo.queue.dispatcher_queue import DispatcherQueue
from artifactsmmo.queue.worker_queue import WorkerQueue
from artifactsmmo.service.dispatch_service import DispatchService
from artifactsmmo.service.execution_context import ExecutionContext
from artifactsmmo.service.fight_simulator import FightSimulator
from artifactsmmo.service.food_service import FoodService
from artifactsmmo.service.helpers import ResolvedItemRecipe
from artifactsmmo.service.item_origin_service import NpcOffer
from artifactsmmo.service.service import Service
from artifactsmmo.service.tasks import Task
from artifactsmmo.service.until import Until
from artifactsmmo.telegram.client import TelegramClient
from artifactsmmo.templates.template_result import TemplateResult
from artifactsmmo.templates.template_strategy import TemplateStrategy


class GatherRecipeTemplate(TemplateStrategy):
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
        self.task_progress_table = TaskProgressTable()

    def template(self) -> str:
        return 'gather-recipe'

    @staticmethod
    def describe_task(task: Task) -> str:
        if task.extra.get('global_max'):
            return f'up to {task.extra.get("global_max")}x {task.extra.get("item")}'
        else:
            return f'{task.extra.get("quantity")}x {task.extra.get("item")}'

    def render(self, character: CharacterSchemaExtension, task: Task, quest_id: str = None, context: ExecutionContext = None) -> TemplateResult:
        template_result: TemplateResult = TemplateResult()
        extra = task.extra
        item_code = extra.get('item')
        deprecated_quantity = int(extra.get('quantity', 1))
        force_gather = bool(extra.get('force_gather', False))
        global_max = extra.get('global_max')
        leader = extra.get('leader')
        request_support = bool(extra.get('request_support', False))
        reserve_target_product = bool(extra.get('reserve_target_product', True))
        add_sleep_task = bool(extra.get('add_sleep_task'))
        missing_quantity = extra.get('missing_quantity')
        total_quantity = extra.get('total_quantity')
        keep_equipment = bool(extra.get('keep_equipment', False))

        quantity = missing_quantity
        bank_items_map = self.service.get_bank_items_map(task_id=task.task_id, character_name=character.name)
        if global_max is not None:
            global_quantity = self.service.get_global_quantity(item_code)
            additional_quantity = max(min((global_max - global_quantity), quantity), 0)
            if additional_quantity != quantity:
                logger.info(
                    f'Gathering for item={item_code}, global_quantity={global_quantity}, '
                    f'quantity={quantity}, global_max={global_max}, additional_quantity={additional_quantity}'
                )
                quantity = additional_quantity
        else:
            item = self.service.get_item(item_code)
            if not item.craft or item.craft.skill not in (CraftSkill.GEARCRAFTING, CraftSkill.WEAPONCRAFTING, CraftSkill.JEWELRYCRAFTING):
                available_quantity = bank_items_map.get(item_code, 0)
                if total_quantity - available_quantity < quantity:
                    new_quantity = max(total_quantity - available_quantity, 0)

                    bank_reservations = self.service.get_bank_reservations()
                    reserved_quantity = 0
                    for bank_reservation in bank_reservations:
                        if bank_reservation.item_code == item_code and bank_reservation.task_id == task.task_id:
                            reserved_quantity = bank_reservation.quantity
                            break
                    new_reserved_quantity = reserved_quantity
                    if reserved_quantity < total_quantity or reserved_quantity < available_quantity:
                        new_reserved_quantity = min(available_quantity, total_quantity)

                        if reserved_quantity != new_reserved_quantity:
                            pass
                            # TODO: Update reservation

                    logger.info(
                        f'Checking quantity of item={item_code}, requested total_quantity={total_quantity}, '
                        f'available_quantity={available_quantity}, new_quantity={new_quantity}, reserved_quantity={reserved_quantity}.'
                    )
                    self.telegram_client.send_notification(
                        f'{character.name} should gather {quantity}x {item_code} '
                        f'but this would exceed the desired {total_quantity}x total with the available {available_quantity}x. '
                        f'Character should only have to gather {new_quantity}. Reserved quantity: {reserved_quantity}, '
                        f'new reserved quantity (not yet!): {new_reserved_quantity}.'
                    )

                    # TODO: Update variable 'quantity'

        if quantity > 0 and item_code:
            logger.info(
                f'task_id={task.task_id}, quantity_available={bank_items_map.get(item_code, 0)}, total_quantity_required={total_quantity}'
            )

            resolved_recipe: ResolvedItemRecipe = self.service.resolve_item_recipe(item_code, bank_items_map, quantity, force_gather)

            for missing_item_code, missing_quantity in resolved_recipe.missing_items.items():
                item: ItemSchemaExtension = self.service.get_item(missing_item_code)
                match item.subtype:
                    case 'mob':
                        fight_task = self.handle_monster(item, missing_quantity, task.task_id)
                        if fight_task:
                            if not character.current_task.task:
                                template_result.append(Task.solve_task(start_solving=False))
                            template_result.append(fight_task)
                        else:
                            logger.warning(f'Could not find monster that drops item={item.code}')
                    case 'task':
                        total_quantity: int = resolved_recipe.all_items[item.code]
                        reward_task = self.handle_reward(item, total_quantity, task.task_id, leader)
                        if reward_task:
                            template_result.append(reward_task)
                        else:
                            logger.warning(f'Could not find task that drops item={item.code}')
                    case _:
                        gather_tasks = self.handle_resource(character, item, missing_quantity, task.task_id)
                        if gather_tasks:
                            template_result.extend(gather_tasks)
                        else:
                            fight_task = self.handle_monster(item, missing_quantity, task.task_id)
                            if fight_task:
                                template_result.append(fight_task)

                if quest_id and (leader is None or leader == character.name):
                    drop_id = f'{task.task_id}.{missing_item_code}'
                    self.task_progress_table.create(quest_id, drop_id, missing_quantity, character.name)

            logger.info(
                f'missing_items={resolved_recipe.missing_items}, '
                f'available_items={resolved_recipe.available_items}, '
                f'all_items={resolved_recipe.all_items}'
            )

            if not leader or leader == character.name:
                for reserve_code, reserve_quantity in resolved_recipe.available_items.items():
                    if reserve_target_product or reserve_code != item_code:
                        self.service.add_bank_reservation(
                            task_id=task.task_id,
                            item_code=reserve_code,
                            quantity=reserve_quantity,
                            character_name=character.name,
                        )
                    else:
                        logger.info(f'Skipping reservation of item={item_code}, reserve_target_product={reserve_target_product}')

            template_result.quest_status(f'{quantity}x {item_code}')

            if template_result.new_tasks or character.inventory_map:
                template_result.append(Task.ensure_inventory(task_id=task.task_id, keep_consumables=True))
                if not keep_equipment:
                    template_result.append(Task.unequip_all(task_id=task.task_id))
                template_result.append(Task.ensure_inventory(task_id=task.task_id))
                if task.task_id and leader == character.name:
                    if add_sleep_task:
                        template_result.append(
                            Task.sleep(task_id=task.task_id, leader=leader, items_map=dict(resolved_recipe.all_items), ttl=DEFAULT_SLEEP_TTL)
                        )
                        logger.info(
                            f'Created sleep-action for leader={leader} to check for items_map={dict(resolved_recipe.all_items)} prior crafting.'
                        )

                    logger.info(
                        f'Should character request support to gather for quantity={quantity} of item={item_code} with quest_id={quest_id}, '
                        f'request_support={request_support}, missing_items={dict(resolved_recipe.missing_items)}'
                    )

                    if quest_id and request_support:
                        self.dispatcher_queue.join(['all'])

        if template_result.new_tasks:
            template_result.append(Task.finish_task())

        return template_result

    @staticmethod
    def handle_reward(item: ItemSchemaExtension, total_quantity: int, task_id: str, leader: str = None) -> Task:
        logger.info(f'Plan to solve tasks for {total_quantity}x {item.code}.')
        return Task.gather_reward(item=item.code, task_id=task_id, quantity=total_quantity, leader=leader, task_type='monsters')

    def handle_resource(self, character: CharacterSchemaExtension, item: ItemSchemaExtension, quantity: int, task_id: str) -> List[Task]:
        tasks: List[Task] = []
        resource_candidates = self.service.get_resources_by_drop(item.code)
        if resource_candidates:
            resources = self.sort_resources_by_drop_rate(resource_candidates, item.code)
            missing_skill_level = False
            for resource in resources:
                if not resource.is_event_drop or any(e.map.interactions.content.code == resource.code for e in self.service.get_active_events()):
                    current_skill_level = character.skills[str(resource.skill)].level
                    required_skill_level = resource.level
                    if current_skill_level >= required_skill_level:
                        logger.info(f'Plan to gather {quantity}x {item.code} from location={resource.code}.')
                        tasks.append(
                            Task.gather_resource(resource=resource.code, task_id=task_id, until=Until(drop_item=item.code, drop_count=quantity))
                        )
                        break
                    else:
                        missing_skill_level = True

            if not tasks:
                if missing_skill_level:
                    resource = min(resources, key=lambda resource: resource.level)
                    tasks.append(Task.level_skill(str(resource.skill), resource.level))
                    tasks.append(
                        Task.gather_resource(resource=resource.code, task_id=task_id, until=Until(drop_item=item.code, drop_count=quantity))
                    )
                    logger.info(
                        f'Character cannot gather resource={resource.code} yet. Added task to level-skill up to '
                        f'level={resource.level} before starting gather task.'
                    )
                else:
                    logger.warning(f'Cannot gather resource={item.code} right now.')
        else:
            logger.info(f'Could not find resource that drops item={item.code}')
        return tasks

    def sort_resources_by_drop_rate(self, resources: List[ResourceSchemaExtension], drop_code: str):
        return sorted(
            resources,
            key=lambda resource: (
                next(
                    (drop.rate for drop in resource.drops if not self.service.is_event_content(resource.code) and drop.code == drop_code),
                    float('inf'),
                ),
                -resource.level,
            ),
        )

    def handle_monster(self, item: ItemSchemaExtension, quantity: int, task_id: str) -> Optional[Task]:
        monsters = self.service.get_monsters_by_drop(item.code)
        if monsters:
            monsters = self.sort_monsters_by_drop_rate(monsters, item.code)
            for monster in monsters:
                if not monster.is_event_monster or any(
                    e.map.interactions.content.code == monster.code for e in self.service.get_active_events()
                ):
                    logger.info(f'Plan to fight for {quantity}x {item.code} against monster={monster.code}.')
                    return Task.fight_monster(task_id=task_id, monster=monster.code, until=Until(drop_item=item.code, drop_count=quantity))
        return None

    def handle_rune(self, rune, missing_quantity, task_id) -> Optional[Task]:
        npcs = self.service.get_npcs_by_item_code(rune.code)
        for npc in npcs:
            if npc and npc.items.get(rune.code).buy_price is not None:
                return Task.buy_from_npc(rune.code, npc.code, quantity=missing_quantity, task_id=task_id)
        return None

    @staticmethod
    def handle_npc(item_code: str, npc_map: Dict[str, NpcOffer], missing_quantity, task_id) -> Optional[Task]:
        for npc_code, npc_offer in npc_map.items():
            if npc_offer.price and npc_offer.currency:
                return Task.buy_from_npc(item_code, npc_code, quantity=missing_quantity, task_id=task_id)
        return None

    def sort_monsters_by_drop_rate(self, monsters: List[MonsterSchemaExtension], drop_code: str):
        return sorted(
            monsters,
            key=lambda monster: next(
                (drop.rate for drop in monster.drops if not self.service.is_event_content(monster.code) and drop.code == drop_code),
                float('inf'),
            ),
        )
