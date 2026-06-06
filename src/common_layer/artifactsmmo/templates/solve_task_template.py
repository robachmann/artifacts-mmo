from collections import Counter
from datetime import datetime, timedelta, UTC
from math import ceil
import random
from typing import Dict, Optional

from artifactsmmo.dynamodb.fight_simulator_table import FightSimulatorStatus
from artifactsmmo.extensions import CharacterSchemaExtension, MonsterSchemaExtension
from artifactsmmo.fights.combat_result import CombatResultDTO, CombatResults, minimize_cooldown
from artifactsmmo.game_constants import SOLVE_TASK_TIMEOUT_PER_COIN, TASK_COINS_RESERVE
from artifactsmmo.log.logger import logger
from artifactsmmo.service.execution_context import ExecutionContext
from artifactsmmo.service.helpers import BucketFiller
from artifactsmmo.service.tasks import NextMove, Task
from artifactsmmo.templates.template_result import TemplateResult
from artifactsmmo.templates.template_strategy import TemplateStrategy


class SolveTaskTemplate(TemplateStrategy):
    def template(self) -> str:
        return 'solve-task'

    @staticmethod
    def describe_task(task: Task) -> str:
        return f'of type {task.extra.get("type")}' if task.extra.get('type') else ''

    def render(self, character: CharacterSchemaExtension, task: Task, quest_id: str = None, context: ExecutionContext = None) -> TemplateResult:
        template_result: TemplateResult = TemplateResult()
        extra = task.extra
        allow_cancellation = bool(extra.get('allow_cancellation', False))
        start_solving = bool(extra.get('start_solving', True))
        task_type = extra.get('type', 'monsters')
        deposit_coins = bool(extra.get('deposit_coins', True))
        priority = extra.get('priority', 'time')

        if not task.task_id:
            task.task_id = task.generate_task_id()

        if character.task:
            if start_solving:
                remaining = character.current_task.task_remaining
                add_complete_task = False

                match character.task_type:
                    case 'monsters':
                        add_complete_task = self.handle_monsters_task(
                            template_result, character, remaining, allow_cancellation, task, task_type, priority, quest_id
                        )
                    case 'items':
                        add_complete_task = self.handle_items_task(template_result, character, remaining, task, allow_cancellation, task_type)

                if add_complete_task:
                    template_result.append(Task.move(content_type='tasks_master', content_code=character.task_type))
                    template_result.append(Task.complete_task(deposit_coins=deposit_coins))

        else:
            template_result.append(Task.move(content_type='tasks_master', content_code=task_type))
            template_result.append(Task.accept_new_task(solve_task=start_solving, allow_cancellation=allow_cancellation, priority=priority))

        return template_result

    def handle_monsters_task(
        self,
        template_result,
        character,
        total: int,
        allow_cancellation,
        task,
        task_type: str,
        priority: str,
        quest_id: Optional[str],
    ) -> bool:
        add_complete_task = False
        if total > 0:
            monster = self.service.get_monster(character.task)
            task_coins = self.get_bank_task_coins(task.task_id, character.name)
            lock_acquired = self.equipment_lock_table.acquire_lock(character.name) if self.equipment_lock_table else True
            if lock_acquired:
                if monster.level >= 55:
                    if task_coins > 0:
                        self.add_cancel_task_steps(template_result, character, task_type, allow_cancellation, task)
                else:
                    fight_simulator_id = task.extra.get('fight_simulator_id')
                    if fight_simulator_id:
                        fight_simulator_record = self.fight_simulator_table.get_record(fight_simulator_id)
                        if fight_simulator_record:
                            if fight_simulator_record.status in [FightSimulatorStatus.FINISHED, FightSimulatorStatus.FAILED]:
                                logger.info(f'Async Fight Simulator is {fight_simulator_record.status}')
                                fight_sim_result = fight_simulator_record.combat_result
                                add_complete_task = self._handle_async_sim_result(
                                    sim_result=fight_sim_result,
                                    monster=monster,
                                    character=character,
                                    template_result=template_result,
                                    total=total,
                                    allow_cancellation=allow_cancellation,
                                    task=task,
                                    task_type=task_type,
                                    priority=priority,
                                    task_coins=task_coins,
                                )
                                self.equipment_lock_table.release_lock(character.name)
                            else:
                                created_at_clean = fight_simulator_record.created_at.replace(microsecond=0)
                                age = timedelta(seconds=int((datetime.now(UTC) - fight_simulator_record.created_at).total_seconds()))
                                logger.info(
                                    f'Async Fight Simulator is not finished yet: {fight_simulator_record.status}, '
                                    f'since {created_at_clean} ({age} ago). '
                                    f'Will hibernate and wait until fight simulator invoke this function again.'
                                )
                                template_result.repeat()
                                template_result.hibernate()
                    else:
                        new_fight_simulator_id = self.async_fight_simulator_service.trigger_fight_simulator(
                            participants=[character.name],
                            character_name=character.name,
                            monster_code=monster.code,
                            sort_function='minimize_cooldown',
                            quest_id=quest_id,
                        )
                        logger.info(
                            f'Async Fight Simulator triggered with fight_simulator_id={new_fight_simulator_id}. '
                            f'Will hibernate and wait until fight simulator invoke this function again.'
                        )
                        task.extra['fight_simulator_id'] = new_fight_simulator_id
                        template_result.repeat()
                        template_result.hibernate()
            else:
                template_result.append(Task.sleep(seconds=random.randint(15, 20)))
                template_result.repeat(until=task.until)
        return add_complete_task

    def handle_items_task(self, template_result, character, total: int, task, allow_cancellation, task_type: str) -> bool:
        add_complete_task = False
        if total > 0:
            trade_count = total
            item_code = character.task
            item = self.service.get_item(item_code)
            logger.info(f'item_code={item_code}, quantity={total}, task_id={task.task_id}')

            bank_item_map = self.service.get_bank_items_map(task_id=task.task_id, character_name=character.name)
            bank_count = bank_item_map.get(item_code, 0)
            trade_items = False
            if bank_count >= total:  # and not item_code.startswith('cooked_'):
                self.service.add_bank_reservation(task.task_id, item_code, total, character.name)
                logger.info(f'Added bank reservation for task_id={task.task_id}, item_code={item_code}, quantity={total}')
                trade_items = True
            else:
                missing = max(total - bank_count, 0)
                task_coins = bank_item_map.get('tasks_coin', 0)
                if allow_cancellation and (
                    self.should_cancel_task(item_code, missing, task_coins, bank_item_map)
                    or self.should_cancel_event(item_code, bank_item_map, missing, character)
                ):
                    if task_coins > 0:
                        self.add_cancel_task_steps(template_result, character, task_type, allow_cancellation, task)
                        logger.info(f'Plan to cancel task and accept new task of type={character.task_type}')
                else:
                    if item.craft:
                        if bank_count > 0:
                            self.service.add_bank_reservation(task.task_id, item_code, bank_count, character.name)

                        logger.info(
                            f'Plan to gather and craft {missing}x item={item_code} '
                            f'(reserved {bank_count} at bank). Will deposit crafted items at tasks_master.'
                        )

                        template_result.append(Task.gather_recipe(task_id=task.task_id, item=item_code, quantity=missing, leader=character.name))

                        template_result.append(
                            Task.craft_recipe(
                                task_id=task.task_id, item=item_code, quantity=missing, target='tasks_master', leader=character.name
                            )
                        )
                        trade_count = bank_count
                    else:
                        if bank_count > 0:
                            self.service.add_bank_reservation(task.task_id, item_code, bank_count, character.name)

                        logger.info(
                            f'Plan to gather and craft {missing}x item={item_code} (reserved {total} at bank). Will deposit items at bank.'
                        )

                        template_result.append(Task.gather_recipe(task_id=task.task_id, item=item_code, quantity=missing, leader=character.name))

                        trade_count = total
                    trade_items = True

            teleport_item_codes = self.service.get_teleport_item_codes()
            if trade_items:
                if trade_count > 0:
                    bucket_filler = BucketFiller(character.inventory_capacity(teleport_item_codes))
                    for bucket in bucket_filler.generate_buckets(trade_count):
                        item_map = {item_code: bucket.quantity}
                        next_move = NextMove(content_type='tasks_master', content_code='items')
                        task = Task.ensure_inventory(item_map=item_map, task_id=task.task_id, next_move=next_move)
                        template_result.append(task)
                        template_result.append(Task.trade(item=item_code, quantity=bucket.quantity))
                add_complete_task = True
                template_result.quest_status(f'{total}x {character.task} (Task)')
        return add_complete_task

    def should_cancel_event(self, item_code, bank_item_map, missing, character) -> bool:
        item = self.service.get_item(item_code)
        if not item:
            return True
        if item.craft:
            required_skill = str(item.craft.skill)
            required_skill_level = item.craft.level
            current_skill_level = character.skills[required_skill].level
            if required_skill_level - 1 > current_skill_level:
                logger.warning(
                    f"Character's {required_skill} level is insufficient to craft the missing items, "
                    f'required_level={required_skill_level}, current_level={current_skill_level}'
                )
                return True

            resolved_recipe = self.service.resolve_item_recipe(item_code, bank_item_map, missing)
            for craft_code in resolved_recipe.missing_items.keys():
                craft_item = self.service.get_item(craft_code)
                if craft_item.craft:
                    required_skill = craft_item.craft.skill
                    required_skill_level = craft_item.craft.level
                    current_skill_level = character.skills[required_skill].level
                    if required_skill_level - 1 > current_skill_level:
                        logger.warning(
                            f"Character's {required_skill} level is insufficient to craft the missing items, "
                            f'required_level={required_skill_level}, current_level={current_skill_level}'
                        )
                        return True
                else:
                    required_skill = craft_item.subtype
                    required_skill_level = craft_item.level
                    current_skill_level = character.skills[required_skill].level
                    if current_skill_level is not None and required_skill_level - 1 > current_skill_level:
                        logger.warning(
                            f"Character's {required_skill} level is insufficient to gather the missing resource, "
                            f'required_level={required_skill_level}, current_level={current_skill_level}'
                        )
                        return True
                if missing > 0:
                    if self.service.is_event_content(craft_code) or self.service.is_event_resource_drop(craft_code):
                        logger.info(f'Item={craft_code} is event/resource drop and cannot be fulfilled right now. Cancelling event.')
                        return True
        if missing > 0:
            if self.service.is_event_content(item.code) or self.service.is_event_resource_drop(item.code):
                logger.info(f'Item={item.code} is event/resource drop and cannot be fulfilled right now. Cancelling event.')
                return True

        return False

    @staticmethod
    def should_cancel_mob(
        character: CharacterSchemaExtension,
        sim_result: CombatResultDTO,
        ttl: int,
        task_coins: int,
        monster: MonsterSchemaExtension,
        priority: str,
        task_coin_reward: int,
    ) -> bool:
        if not sim_result.characters_win:
            logger.info(f'Character cannot defeat monster={monster.code} to solve this task. Will not solve this task.')
            return True
        elif sim_result.used_utilities_sum > 0:
            logger.info(f'Character needs utilities to defeat monster={monster.code}. Will not solve this task.')
            return True

        if priority == 'time':
            if sim_result.cooldown > 5 and monster.level > 10:
                etc = timedelta(seconds=int(sim_result.cooldown) * ttl)
                logger.info(
                    f'Fighting monster={monster.code} {ttl}x to solve this task will take ~{etc}, expected task coins: {task_coin_reward}.'
                )
                if etc > timedelta(minutes=SOLVE_TASK_TIMEOUT_PER_COIN * task_coin_reward) and task_coins >= TASK_COINS_RESERVE - 2:
                    logger.info(f'Fighting monster={monster.code} to solve this task would take too long ({etc}). Will not solve this task.')
                    return True
        elif priority == 'xp':
            if sim_result.cooldown > 10 and monster.level + 10 < character.level:
                etc = timedelta(seconds=int(sim_result.cooldown) * ttl)
                logger.info(f'Fighting monster={monster.code} {ttl}x to solve this task will take ~{etc}.')
                if task_coins >= TASK_COINS_RESERVE - 2:
                    logger.info(
                        f'Fighting monster={monster.code} to solve this task would take too long ({etc}) and not yield any xp. '
                        f'Will not solve this task.'
                    )
                    return True

        return False

    def get_bank_task_coins(self, task_id, character_name) -> int:
        bank_items_map = self.service.get_bank_items_map(task_id=task_id, character_name=character_name)
        return bank_items_map.get('tasks_coin', 0)

    def should_cancel_task(self, task_code: str, missing: int, task_coins: int, bank_items_map: Dict[str, int]):
        if task_coins < TASK_COINS_RESERVE * 5:
            return False

        if task_code.startswith('cooked_'):
            return True

        if task_coins > 100 * TASK_COINS_RESERVE:
            skip_factor = 0.10
        elif task_coins > 80 * TASK_COINS_RESERVE:
            skip_factor = 0.15
        elif task_coins > 40 * TASK_COINS_RESERVE:
            skip_factor = 0.20
        elif task_coins > 20 * TASK_COINS_RESERVE:
            skip_factor = 0.25
        elif task_coins > 10 * TASK_COINS_RESERVE:
            skip_factor = 0.30
        else:
            skip_factor = 0.35

        item = self.service.get_item(task_code)
        task = self.service.get_task(task_code)

        quantity_range = task.max_quantity - task.min_quantity
        threshold = task.min_quantity + ceil(quantity_range * skip_factor)

        if item.craft:
            resolved_recipe = self.service.resolve_item_recipe(task_code, bank_items_map, missing)
            if resolved_recipe.missing_items:
                available_quantities = []
                for code in resolved_recipe.all_items:
                    qty = resolved_recipe.available_items.get(code, 0)
                    available_quantities.append(qty / resolved_recipe.all_items[code])
                min_available_quantity = min(available_quantities) if available_quantities else 0
                readily_craftable_quantity = int(min_available_quantity * missing)
                missing -= readily_craftable_quantity
                should_cancel = missing > threshold
                logger.info(
                    f'Check if task to craft {missing}x {task_code} should be cancelled: '
                    f'min_quantity={task.min_quantity}, max_quantity={task.max_quantity}, '
                    f'skip_factor={skip_factor}, threshold={threshold}, '
                    f'readily_craftable_quantity={readily_craftable_quantity}, should_cancel={should_cancel}'
                )
                return should_cancel
            else:
                return False
        else:
            should_cancel = missing > threshold
            logger.info(
                f'Check if task to gather {missing}x {task_code} should be cancelled: '
                f'min_quantity={task.min_quantity}, max_quantity={task.max_quantity}, '
                f'skip_factor={skip_factor}, threshold={threshold}, should_cancel={should_cancel}'
            )
            return should_cancel

    @staticmethod
    def add_cancel_task_steps(template_result, character: CharacterSchemaExtension, task_type, allow_cancellation, task):
        if 'tasks_coin' not in character.inventory_map:
            template_result.append(
                Task.ensure_inventory(
                    item_map={'tasks_coin': 1},
                    next_move=NextMove(content_type='tasks_master', content_code=character.task_type),
                )
            )

        template_result.extend(
            [
                Task.cancel_task(),
                Task.move(content_type='tasks_master', content_code=task_type),
                Task.accept_new_task(task_id=task.task_id, allow_cancellation=allow_cancellation),
            ]
        )

    def _handle_async_sim_result(
        self,
        sim_result: CombatResultDTO,
        monster: MonsterSchemaExtension,
        character: CharacterSchemaExtension,
        template_result: TemplateResult,
        total: int,
        allow_cancellation: bool,
        task: Task,
        task_type: str,
        priority: str,
        task_coins: int,
    ) -> bool:
        expected_task_coin_reward = 3

        task_obj = self.service.get_task(monster.code)
        for reward in task_obj.rewards.items:
            if reward.code == 'tasks_coin':
                expected_task_coin_reward = reward.quantity
                break

        if allow_cancellation and self.should_cancel_mob(character, sim_result, total, task_coins, monster, priority, expected_task_coin_reward):
            if task_coins > 0:
                self.add_cancel_task_steps(template_result, character, task_type, allow_cancellation, task)
        else:
            used_utilities = Counter()
            equip_map: Dict[str, str] = {}
            for c in sim_result.characters.values():
                used_utilities.update(c['used_utilities'])
                equip_map = c['equipment']
            reservation_id = self.service.reserve_equipment(character, equip_map, used_utilities)
            template_result.append(
                Task.fight_monster(
                    task_id=reservation_id,
                    monster=character.task,
                    ttl=total,
                    equip_map=equip_map,
                    required_hp=ceil(sim_result.required_hp),
                    expected_win_rate=float(sim_result.win_rate),
                    utilities=used_utilities,
                    reservation_id=reservation_id,
                )
            )
            logger.info(f'Plan to fight monster={character.task} and complete task with equipment={equip_map}')
            template_result.quest_status(f'{total}x {character.task} (Task)')
            return True
        return False
