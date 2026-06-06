from collections import Counter
from datetime import datetime, timedelta, UTC
import random
from typing import Dict, List, Optional, Tuple

from artifactsmmo.dynamodb.fight_simulator_table import FightSimulatorStatus
from artifactsmmo.extensions import CharacterSchemaExtension, MonsterSchemaExtension
from artifactsmmo.fights.combat_result import CombatResultDTO
from artifactsmmo.game_constants import WIN_RATE_THRESHOLD
from artifactsmmo.log.logger import logger
from artifactsmmo.service.execution_context import ExecutionContext
from artifactsmmo.service.helpers import format_until, is_item_available
from artifactsmmo.service.tasks import NextMove, Task
from artifactsmmo.service.until import Until
from artifactsmmo.templates.template_result import TemplateResult
from artifactsmmo.templates.template_strategy import TemplateStrategy


class FightMonsterTemplate(TemplateStrategy):
    def template(self) -> str:
        return 'fight-monster'

    @staticmethod
    def describe_task(task: Task) -> str:
        if task.until and task.until.drop_item:
            return f'{task.extra.get("monster")} for {task.until.drop_item} ({task.until.progress}/{task.until.drop_count})'
        return f'{task.extra.get("monster")}{f" {task.extra.get('ttl', 1)} times" if task.extra.get("ttl", 1) > 1 else ""}'

    def render(self, character: CharacterSchemaExtension, task: Task, quest_id: str = None, context: ExecutionContext = None) -> TemplateResult:
        template_result: TemplateResult = TemplateResult()
        extra = task.extra
        monster_code = extra.get('monster')
        ttl = int(extra.get('ttl', 1))
        equip_map: Dict[str, str] = extra.get('equip_map') or {}
        utilities_map: Dict[str, int] = extra.get('utilities')
        exclude_items = extra.get('exclude_items')
        reservation_id = extra.get('reservation_id')
        required_hp = extra.get('required_hp')
        expected_win_rate = extra.get('expected_win_rate')
        map_id = extra.get('map_id')

        exclude_items = exclude_items or []
        utilities_map = utilities_map or {}
        consumable_map: Dict[str, int] = {}

        if not monster_code and task.until and task.until.achievement_code:
            achievement = self.service.get_account_achievement(character.account, task.until.achievement_code)
            if achievement:
                if not achievement.completed_at:
                    for objective in achievement.objectives:
                        if objective.progress < objective.total:
                            monster = self.service.get_monster(objective.target)
                            if monster:
                                monster_code = monster.code
                                break
                else:
                    logger.info(f'Supplied achievement_code={task.until.achievement_code} is already completed.')
            else:
                logger.error(f'Supplied achievement_code={task.until.achievement_code} is unknown.')

        if monster_code:
            monster = self.service.get_monster(monster_code)
            if equip_map and required_hp is None:
                required_hp, expected_win_rate = self.__calculate_required_hp_win_rate(character, monster, equip_map, list(utilities_map.keys()))
                logger.info(
                    f'provided equip_map={equip_map} but no required_hp; calculated required_hp={required_hp}, '
                    f'expected_win_rate={expected_win_rate}, can_win={expected_win_rate >= WIN_RATE_THRESHOLD}'
                )
                if expected_win_rate < WIN_RATE_THRESHOLD:
                    equip_map = {}
                    required_hp = None

            bank_items_map = self.service.get_bank_items_map(task_id=reservation_id, character_name=character.name)
            if not equip_map or required_hp is None:
                logger.info(
                    f'Parameter equip_map={equip_map}, required_hp={required_hp}, calculating necessary variables '
                    f'against monster={monster_code}.'
                )
                async_pending, sim_result, optional_consumable_map, optional_reservation_id = self.handle_incomplete_fight_stats(
                    character=character,
                    monster=monster,
                    exclude_items=exclude_items,
                    task=task,
                    ttl=ttl,
                    template_result=template_result,
                    context=context,
                    quest_id=quest_id,
                )

                if async_pending:
                    template_result.clear_until()
                    return template_result

                if sim_result and sim_result.characters_win:
                    c = list(sim_result.characters.values())[0]
                    equip_map = c['equipment']
                    utilities_map = c['used_utilities']

                    if monster.is_venomous and sim_result.cooldown > 12 and len(utilities_map.keys()) < 2:
                        contains_antipoison_utility = False
                        for utility_code in utilities_map:
                            utility = self.service.get_item(utility_code)
                            if 'antipoison' in utility.item_effects:
                                contains_antipoison_utility = True
                                break

                        if not contains_antipoison_utility:
                            for utility in self.service.get_items_by_type('utility', character.level):
                                if (
                                    'antipoison' in utility.item_effects
                                    and utility.code not in exclude_items
                                    and bank_items_map.get(utility.code, 0) > 10
                                ):
                                    utilities_map[utility.code] = 1
                                    logger.info(f'Adding antipoison utility {utility.code} to reduce lost HP.')
                                    break

                    expected_win_rate = sim_result.win_rate
                    required_hp = sim_result.max_required_hp
                    # required_hp, expected_win_rate = self.__calculate_required_hp_win_rate(
                    #    character, monster, equip_map, list(utilities_map.keys())
                    # )

                    # if previous_expected_win_rate != expected_win_rate:
                    #     message = (
                    #         f'Updated win rate from {previous_expected_win_rate} % to {expected_win_rate:.2f} % for '
                    #         f'{character.name} against {monster_code}. '
                    #         f'This should not happen since the introduction of the new async fight-simulator function.'
                    #     )
                    #     logger.warning(message)
                    #     self.telegram_client.send_notification(message)

                    if optional_consumable_map:
                        consumable_map = optional_consumable_map

                    if optional_reservation_id:
                        reservation_id = optional_reservation_id

            if equip_map and self.__equipment_available(character, equip_map, bank_items_map):
                for utility in ['utility1', 'utility2']:
                    if utility in equip_map:
                        logger.error(f'Deleted {ttl}x {equip_map[utility]} from equip_map.')
                        del equip_map[utility]

                fight_until = self.init_until(task.until)
                if fight_until and fight_until.achievement_code:
                    template_result.status = 'Solving achievement ' + fight_until.achievement_code

                template_result.append(Task.equip_items(items_map=equip_map, task_id=reservation_id))
                fight_times = self.service.estimate_fight_times(task, task.ttl, monster, character)
                for idx, (item_code, quantity) in enumerate(utilities_map.items(), 1):
                    available_quantity = bank_items_map.get(item_code, 0)
                    util_qty = min(100, quantity * fight_times, available_quantity)

                    if util_qty > 0:
                        task = Task.equip_utility(item_code, f'utility{idx}', util_qty, False, reservation_id)
                        template_result.append(task)

                logger.info(
                    f'Fight monster={monster_code} using equipment={equip_map}, utilities={utilities_map}, '
                    f'ttl={ttl}, fight_times={fight_times}, task.until={format_until(fight_until)}'
                )

                if map_id:
                    next_move = NextMove(map_id=map_id)
                else:
                    next_move = NextMove(content_type='monster', content_code=monster_code)
                template_result.append(Task.ensure_inventory(item_map=consumable_map, task_id=reservation_id, next_move=next_move))

                template_result.append(
                    Task.fight(
                        ttl=ttl,
                        until=fight_until,
                        monster=monster_code,
                        utilities=utilities_map,
                        task_id=task.task_id,
                        required_hp=required_hp,
                        expected_win_rate=expected_win_rate,
                    )
                )
            elif not template_result.new_tasks:
                if equip_map:
                    logger.warning(
                        f'Character={character.name} cannot win fight against monster={monster_code}, unavailable items in equip_map={equip_map}'
                    )
                else:
                    logger.warning(f'Character={character.name} cannot win fight against monster={monster_code}')
        else:
            logger.error(f'Missing parameter monster_code={monster_code}.')
        template_result.clear_until()
        return template_result

    @staticmethod
    def init_until(until: Until) -> Optional[Until]:
        if until:
            return Until(
                date_time=until.date_time,
                drop_item=until.drop_item,
                drop_count=until.drop_count,
                achievement_code=until.achievement_code,
            )
        else:
            return None

    def handle_incomplete_fight_stats(
        self,
        character: CharacterSchemaExtension,
        monster: MonsterSchemaExtension,
        exclude_items: List[str],
        task: Task,
        ttl: int,
        template_result: TemplateResult,
        context: ExecutionContext,
        quest_id: Optional[str],
    ) -> Tuple[bool, Optional[CombatResultDTO], Dict[str, int], Optional[str]]:
        lock_acquired = self.equipment_lock_table.acquire_lock(character.name)
        if lock_acquired:
            fight_simulator_id = task.extra.get('fight_simulator_id')
            if fight_simulator_id:
                fight_simulator_record = self.fight_simulator_table.get_record(fight_simulator_id)
                if fight_simulator_record:
                    if fight_simulator_record.status in [FightSimulatorStatus.FINISHED, FightSimulatorStatus.FAILED]:
                        self.equipment_lock_table.release_lock(character.name)
                        fight_sim_result = fight_simulator_record.combat_result
                        sim_result, consumable_map, reservation_id = self._handle_async_sim_result(
                            fight_sim_result, task, ttl, monster, character, task.task_id, context
                        )
                        return False, sim_result, consumable_map, reservation_id
                    else:
                        created_at_clean = fight_simulator_record.created_at.replace(microsecond=0)
                        age = timedelta(seconds=int((datetime.now(UTC) - fight_simulator_record.created_at).total_seconds()))
                        logger.info(
                            f'Async Fight Simulator is not finished yet: {fight_simulator_record.status}, '
                            f'since {created_at_clean} ({age} ago). '
                            f'Will hibernate and wait until fight simulator invoke this function again.'
                        )
                        template_result.repeat(until=task.until)
                        template_result.hibernate()
                        return True, None, {}, None
                else:
                    template_result.append(Task.sleep(seconds=5, reload_character=False))
                    template_result.repeat(until=task.until)
                    task.extra['fight_simulator_id'] = ''
                    return True, None, {}, None
            else:
                new_fight_simulator_id = self.async_fight_simulator_service.trigger_fight_simulator(
                    participants=[character.name],
                    character_name=character.name,
                    monster_code=monster.code,
                    exclude_items=exclude_items,
                    quest_id=quest_id,
                )
                logger.info(
                    f'Async Fight Simulator triggered with fight_simulator_id={new_fight_simulator_id}. '
                    f'Will hibernate and wait until fight simulator invoke this function again.'
                )
                task.extra['fight_simulator_id'] = new_fight_simulator_id
                template_result.repeat(until=task.until)
                template_result.hibernate()
                return True, None, {}, None
        else:
            template_result.append(Task.sleep(seconds=random.randint(15, 20), reload_character=False))
            template_result.repeat(until=task.until)
            return True, None, {}, None

    def __calculate_required_hp_win_rate(
        self,
        character: CharacterSchemaExtension,
        monster: MonsterSchemaExtension,
        equipment_map: Dict[str, str],
        utilities: List[str],
    ):
        result = self.fight_simulator.test_exact_config(
            character=character,
            monster=monster,
            equipment_map=equipment_map,
            utilities_list=utilities,
            rounds=10_000,
        )

        if result:
            logger.info(
                f'CombatResult (Test) for character={character.name} ({character.level}), 👾 monster={monster.code} ({monster.level}), '
                f'{result.to_string()}'
            )

        return result.rounded_result.max_required_hp, result.raw_result.win_rate

    # @staticmethod
    def __equipment_available(self, character: CharacterSchemaExtension, equip_map: Dict[str, str], bank_items_map: Dict[str, int]) -> bool:
        required_equipment = Counter(equip_map.values())
        for item_code, item_qty in required_equipment.items():
            item_available = is_item_available(
                currently_equipped=character.has_item(item_code, item_qty),
                bank_count=bank_items_map.get(item_code, 0),
                item_index=item_qty,
            )

            if not item_available:
                reservations = []
                for r in self.service.get_bank_reservations():
                    if r.item_code == item_code:
                        reservations.append(f'task_id={r.task_id}, item_code={r.item_code}, qty={r.quantity}, char={r.character}')

                bank_items_map_all = self.service.get_bank_items_map(ignore_reservations=True)
                logger.error(
                    f'missing item={item_code} ({item_qty}x) in equipment map {equip_map}, '
                    f'character equipped count: {character.equipped_items.get(item_code, 0)}, '
                    f'character inventory count: {character.inventory_map.get(item_code, 0)}, '
                    f'bank count: {bank_items_map.get(item_code, 0)}, '
                    f'bank count (ignoring reservations): {bank_items_map_all.get(item_code, 0)}, '
                    f'reservations={reservations}, '
                    f'character_equipped_items={character.equipped_items}, character_inventory_map={character.inventory_map}'
                )

                return False
        return True

    def _handle_async_sim_result(
        self,
        sim_result: CombatResultDTO,
        task: Task,
        ttl: int,
        monster: MonsterSchemaExtension,
        character: CharacterSchemaExtension,
        reservation_id: Optional[str],
        context: ExecutionContext,
    ) -> Tuple[Optional[CombatResultDTO], Dict[str, int], Optional[str]]:
        consumable_map = {}
        if sim_result and sim_result.characters_win:
            fight_times = self.service.estimate_fight_times(task, ttl, monster, character)

            remaining_hp_list = []
            for c in sim_result.characters.values():
                remaining_hp_list.extend(c['remaining_hp_list'])

            consumable_map = self.food_service.get_best_food_to_withdraw(
                character=character,
                required_hp=int(sim_result.required_hp),
                lost_hps_per_fight=remaining_hp_list,
                fight_times=fight_times,
                is_event_monster=monster.is_event_monster,
                is_boss_monster=monster.is_boss_monster,
                task_id=reservation_id,
                context=context,
            )
            for c in sim_result.characters.values():
                utilities_map = c['used_utilities']
                equipment = c['equipment']

                reservation_id = self.service.reserve_equipment(
                    character=character,
                    equipment=equipment,
                    utilities=utilities_map,
                    consumables=consumable_map,
                    reservation_id=reservation_id,
                )

        return sim_result, consumable_map, reservation_id
