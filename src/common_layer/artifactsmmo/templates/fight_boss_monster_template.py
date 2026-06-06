from collections import Counter
from copy import copy
from datetime import datetime, timedelta, UTC
import math
import random
from typing import Dict, List, Optional, Set

from telegram.constants import ParseMode

from artifactsmmo.dynamodb.fight_simulator_table import FightSimulatorStatus
from artifactsmmo.extensions import CharacterSchemaExtension, ItemSchemaExtension, MonsterSchemaExtension
from artifactsmmo.fights.combat_result import CombatResultDTO
from artifactsmmo.log.logger import logger
from artifactsmmo.quests.quests import Quest
from artifactsmmo.service.execution_context import ExecutionContext
from artifactsmmo.service.helpers import escape_string
from artifactsmmo.service.tasks import NextMove, Task
from artifactsmmo.service.until import Until
from artifactsmmo.templates.template_result import TemplateResult
from artifactsmmo.templates.template_strategy import TemplateStrategy


class FightBossMonsterTemplate(TemplateStrategy):
    def template(self) -> str:
        return 'fight-boss-monster'

    @staticmethod
    def describe_task(task: Task) -> str:
        if task.until and task.until.drop_item:
            return f'{task.extra.get("monster")} for {task.until.drop_item} ({task.until.progress}/{task.until.drop_count})'
        return f'{task.extra.get("monster")}{f" {task.extra.get('ttl', 1)} times" if task.extra.get("ttl", 1) > 1 else ""}'

    def render(self, character: CharacterSchemaExtension, task: Task, quest_id: str = None, context: ExecutionContext = None) -> TemplateResult:
        template_result: TemplateResult = TemplateResult()

        monster_code = task.extra.get('monster', '')
        participants = task.extra.get('participants', [])
        equipments = task.extra.get('equipments', {})  # same format as the simulator
        force_utilities: bool = bool(task.extra.get('force_utilities', False))

        monster = self.service.get_monster(monster_code)
        characters_map = {c.name: c for c in self.service.get_all_character_details()}
        characters = [characters_map[character.name]]
        for participant in participants:
            characters.append(characters_map[participant])

        if equipments:
            fight_sim_result = self._process_supplied_equipments(characters, monster, equipments)
            self._handle_fight_sim_result(
                template_result=template_result,
                result=fight_sim_result,
                quest_id=quest_id,
                character=character,
                participants=participants,
                monster_code=monster_code,
                task=task,
                context=context,
            )
            template_result.clear_until()
            return template_result
        else:
            lock_acquired = self.equipment_lock_table.acquire_lock(character.name)
            if lock_acquired:
                fight_simulator_id = task.extra.get('fight_simulator_id')
                if fight_simulator_id:
                    fight_simulator_record = self.fight_simulator_table.get_record(fight_simulator_id)
                    if fight_simulator_record:
                        if fight_simulator_record.status in [FightSimulatorStatus.FINISHED, FightSimulatorStatus.FAILED]:
                            self.equipment_lock_table.release_lock(character.name)
                            fight_sim_result: CombatResultDTO = fight_simulator_record.combat_result
                            self._handle_fight_sim_result(
                                template_result=template_result,
                                result=fight_sim_result,
                                quest_id=quest_id,
                                character=character,
                                participants=participants,
                                monster_code=monster_code,
                                task=task,
                                context=context,
                            )
                            template_result.clear_until()
                            return template_result
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
                            return template_result
                    else:
                        template_result.append(Task.sleep(seconds=5, reload_character=False))
                        template_result.repeat(until=task.until)
                        task.extra['fight_simulator_id'] = ''
                        template_result.clear_until()
                        return template_result
                else:
                    characters_map = {c.name: c for c in self.service.get_all_character_details()}
                    characters = [characters_map[character.name]]
                    for participant in participants:
                        characters.append(characters_map[participant])

                    new_fight_simulator_id = self.async_fight_simulator_service.trigger_fight_simulator(
                        participants=[c.name for c in characters],
                        character_name=character.name,
                        monster_code=monster_code,
                        force_utilities=force_utilities,
                        quest_id=quest_id,
                    )
                    logger.info(
                        f'Async Fight Simulator triggered with fight_simulator_id={new_fight_simulator_id}. '
                        f'Will hibernate and wait until fight simulator invoke this function again.'
                    )
                    task.extra['fight_simulator_id'] = new_fight_simulator_id
                    template_result.repeat(until=task.until)
                    template_result.hibernate()
                    return template_result
            else:
                template_result.append(Task.sleep(seconds=random.randint(15, 20)))
                template_result.repeat(until=task.until)
                template_result.clear_until()
        return template_result

    def _handle_fight_sim_result(
        self,
        template_result: TemplateResult,
        result: CombatResultDTO,
        quest_id: str,
        character: CharacterSchemaExtension,
        participants: List[str],
        monster_code: str,
        task: Task,
        context: ExecutionContext,
    ):

        reservation_id: Optional[str] = None
        quest_id = quest_id or Quest.generate_quest_id()
        monster = self.service.get_monster(monster_code)

        characters_map = {c.name: c for c in self.service.get_all_character_details()}
        characters = [characters_map[character.name]]
        for participant in participants:
            characters.append(characters_map[participant])

        task_extra_ttl = task.extra.get('ttl')
        map_id = task.extra.get('map_id')

        message = escape_string(
            f'Leader {character.name} and participants {participants} will fight against {monster.name} '
            f'with an expected win rate of {result.win_rate}%'
        )

        bank_items_map = self.service.get_bank_items_map(context=context)

        self.telegram_client.send_notification(message, parse_mode=ParseMode.MARKDOWN_V2)
        if result.characters_win:
            current_map = self.service.get_map_by_id(character.map_id)

            if not map_id:
                monster_location = self.service.get_closest_location(
                    content_type='monster',
                    content_code=monster.code,
                    current_map=current_map,
                )
                map_id = monster_location.map_id
            next_move = NextMove(map_id=map_id)

            status = f'boss-fight {monster_code}'
            template_result.quest_status(status)

            required_hp_map: Counter[int] = Counter()
            required_hp_median_list: List[float] = []
            for r in result.characters.values():
                required_hp_map.update(r['remaining_hp_list'])
                required_hp_median_list.append(r['required_hp_median'])
            required_hp_median_max = math.ceil(max(required_hp_median_list))
            required_hp_map_list = list(required_hp_map.keys())

            fight_times = self.service.estimate_fight_times(task, task_extra_ttl, monster, character)

            utiliy_claim_map: Counter[str] = Counter()
            for character_name, character_result in result.characters.items():
                utiliy_claim_map.update(character_result['used_utilities'].keys())

            for character_name, character_result in result.characters.items():
                is_leader = character_name == character.name
                current_character = characters_map[character_name]

                utility_map: Dict[str, int] = {}
                for utility_code, utility_qty in character_result['used_utilities'].items():
                    available_quantity = bank_items_map.get(utility_code, 0) // utiliy_claim_map[utility_code]
                    util_qty = min(100, utility_qty * fight_times, available_quantity)
                    utility_map[utility_code] = util_qty

                reservation_id = self.service.reserve_equipment(
                    character=current_character,
                    equipment=character_result['equipment'],
                    utilities=utility_map,
                    reservation_id=reservation_id,
                )
                expected_inventory_max_items = self._calculate_inventory_modifier(current_character, character_result['equipment'])

                food_map = self._get_food_for_character(
                    character=current_character,
                    expected_inventory_max_items=expected_inventory_max_items,
                    required_hp_median_max=required_hp_median_max,
                    required_hp_map_list=required_hp_map_list,
                    fight_times=fight_times,
                    monster=monster,
                    task=task,
                    context=context,
                    is_leader=is_leader,
                )

                tasks = self._prepare_character_tasks(
                    equipment=character_result['equipment'],
                    utilities=utility_map,
                    food_map=food_map,
                    next_move=next_move,
                    map_id=map_id,
                    monster=monster,
                    leader_name=character.name,
                    participants=participants,
                    task_extra_ttl=task_extra_ttl,
                    until=task.until,
                    reservation_id=reservation_id,
                    expected_win_rate=result.win_rate,
                )

                if is_leader:
                    template_result.extend(tasks)
                else:
                    active_quest = self.character_table.get_quest(character.name)
                    self.dispatch_service.dispatch(
                        task_list=tasks,
                        quest_id=quest_id,
                        is_new_quest_id=True,
                        character=current_character,
                        status=status,
                        leader=character.name,
                        created_at=None,
                        skip_pre_tasks=True,
                        skip_post_tasks=False,
                        active_quest=active_quest,
                    )
        else:
            logger.warning(f'Characters={[c.name for c in characters]} cannot win fight against monster={monster_code}')

    def _calculate_inventory_modifier(self, character: CharacterSchemaExtension, new_equipment: Dict[str, str]) -> int:
        current_modifier = sum(
            inv_space
            for item_c in character.equipped_items
            if (inv_space := self.service.get_item(item_c).item_effects.get('inventory_space', 0)) < 0
        )

        new_modifier = sum(self.service.get_item(item_c).item_effects.get('inventory_space', 0) for item_c in new_equipment.values())

        return character.inventory_max_items - current_modifier + new_modifier

    @staticmethod
    def _prepare_character_tasks(
        equipment: Dict[str, str],
        utilities: Dict[str, int],
        food_map: Optional[Dict[str, int]],
        next_move: NextMove,
        map_id: int,
        monster: MonsterSchemaExtension,
        leader_name: str,
        participants: List[str],
        task_extra_ttl: int,
        until: Until,
        reservation_id: str,
        expected_win_rate: float,
    ) -> List[Task]:
        tasks = [Task.equip_items(items_map=equipment, task_id=reservation_id)]
        if utilities:
            for idx, (item_code, quantity) in enumerate(utilities.items(), 1):
                task = Task.equip_utility(item_code, f'utility{idx}', quantity, False, reservation_id)
                tasks.append(task)

        if food_map:
            tasks.append(
                Task.ensure_inventory(
                    item_map=food_map,
                    next_move=next_move,
                    task_id=reservation_id,
                )
            )
        else:
            tasks.append(Task.move(map_id=map_id))

        tasks.append(
            Task.multi_character_fight(
                monster=monster.code,
                leader=leader_name,
                participants=participants,
                map_id=map_id,
                ttl=task_extra_ttl,
                until=copy(until) if until else None,
                expected_win_rate=expected_win_rate,
                utilities=utilities,
            )
        )

        return tasks

    def _get_food_for_character(
        self,
        character: CharacterSchemaExtension,
        expected_inventory_max_items: Optional[int],
        required_hp_median_max: int,
        required_hp_map_list: List[int],
        fight_times: int,
        monster: MonsterSchemaExtension,
        task: Task,
        context: ExecutionContext,
        is_leader: bool,
    ) -> Optional[Dict[str, int]]:
        """Get the best food map for a character and update context."""
        if is_leader:
            food_map = self.food_service.get_best_food_to_withdraw(
                character=character,
                required_hp=min(character.max_hp, required_hp_median_max),
                lost_hps_per_fight=required_hp_map_list,
                fight_times=fight_times,
                is_event_monster=monster.is_event_monster,
                is_boss_monster=monster.is_boss_monster,
                task_id=task.task_id,
                context=context,
            )
        else:
            food_map = self.food_service.get_best_food_to_withdraw(
                character=character,
                character_max_items=expected_inventory_max_items,
                required_hp=min(character.max_hp, required_hp_median_max),
                lost_hps_per_fight=required_hp_map_list,
                fight_times=fight_times,
                is_event_monster=monster.is_event_monster,
                is_boss_monster=monster.is_boss_monster,
                task_id=task.task_id,
                context=context,
            )

        if food_map:
            # Only log for participants (not leader) - matching original behavior
            if not is_leader:
                food_counter = Counter(food_map)
                logger.info(
                    f'Plan to let {character.name} withdraw {food_counter.total()}x food, '
                    f"character's total inventory size: {expected_inventory_max_items}"
                )
            # Update bank inventory
            for item_code, item_qty in food_map.items():
                context.bank_items_maps[str(task.task_id)]['False'][item_code] -= item_qty

        return food_map

    def _process_supplied_equipments(
        self,
        characters: List[CharacterSchemaExtension],
        monster: MonsterSchemaExtension,
        equipments: List[Dict[str, str]],
    ) -> CombatResultDTO:
        utilities_map: Dict[str, Set[ItemSchemaExtension]] = {}
        for fight_character, equipment in zip(characters, equipments):
            utilities_map[fight_character.name] = set()
            for slot in ['utility1_slot', 'utility2_slot']:
                item_code = equipment.get(slot)
                if item_code:
                    item = self.service.get_item(item_code)
                    utilities_map[fight_character.name].add(item)

            for remove_key in ['level', 'utility1_slot_quantity', 'utility2_slot_quantity']:
                if remove_key in equipment:
                    del equipment[remove_key]

        result = self.fight_simulator.test_exact_boss_config(
            characters=characters,
            monster=monster,
            character_equipment_map=equipments,
            utilities_map=utilities_map,
            rounds=1_000,
        )
        return CombatResultDTO.from_combat_results(result)
