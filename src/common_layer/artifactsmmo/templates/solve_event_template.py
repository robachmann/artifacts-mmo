from typing import Dict, List, Optional

from artifactsmmo.extensions import CharacterSchemaExtension
from artifactsmmo.extensions.CharacterSchemaExtension import CharacterSkill
from artifactsmmo.extensions.resource_schema_extension import ResourceSchemaExtension
from artifactsmmo.game_constants import EVENT_BOSS_PARTICIPANTS
from artifactsmmo.log.logger import logger
from artifactsmmo.models import ActiveEventSchema
from artifactsmmo.service.execution_context import ExecutionContext
from artifactsmmo.service.helpers import get_character_list
from artifactsmmo.service.tasks import Task
from artifactsmmo.service.until import Until
from artifactsmmo.templates.template_result import TemplateResult
from artifactsmmo.templates.template_strategy import TemplateStrategy


class SolveEventTemplate(TemplateStrategy):
    def template(self) -> str:
        return 'solve-event'

    @staticmethod
    def describe_task(task: Task) -> str:
        return task.extra.get('content_code')

    def render(self, character: CharacterSchemaExtension, task: Task, quest_id: str = None, context: ExecutionContext = None) -> TemplateResult:
        template_result: TemplateResult = TemplateResult()
        extra = task.extra
        content_type = extra['content_type']
        content_code = extra['content_code']
        map_id = extra.get('map_id')
        event_parameters: Dict[str, Dict[str, int]] = extra.get('event_parameters')

        active_event: Optional[ActiveEventSchema] = self.service.get_event_by_content_if_active(content_code)
        if active_event:
            match active_event.map.interactions.content.type:
                case 'monster':
                    self.handle_monster_event(active_event, content_code, template_result)
                case 'resource':
                    self.handle_resource_event(active_event, content_code, template_result, character, task)
                case 'npc':
                    self.handle_npc_event(active_event, content_type, content_code, template_result, character, event_parameters, context)
        else:
            logger.info(f'Event with content_type={content_type}, content_code={content_code} is not active.')

        return template_result

    def handle_monster_event(self, event: ActiveEventSchema, monster_code: str, template_result: TemplateResult):
        logger.info(f'Plan to fight monster={monster_code} until {event.expiration}')
        monster = self.service.get_monster(monster_code)
        if monster.is_boss_monster:
            participants = []
            all_character_names = get_character_list()
            for idx, character_name in enumerate(all_character_names, 1):
                if idx in EVENT_BOSS_PARTICIPANTS:
                    participants.append(character_name)

            task = Task.fight_boss_monster(
                monster=monster_code,
                participants=participants,
                map_id=event.map.map_id,
                until=Until(date_time=event.expiration),
            )
        else:
            task = Task.fight_monster(monster=monster_code, map_id=event.map.map_id, until=Until(date_time=event.expiration))
        template_result.append(task)

    def handle_resource_event(
        self,
        event: ActiveEventSchema,
        resource_code: str,
        template_result: TemplateResult,
        character: CharacterSchemaExtension,
        task: Task,
    ):
        resource: ResourceSchemaExtension = self.service.get_resource(resource_code)
        if resource:
            skill: CharacterSkill = character.skills[str(resource.skill)]
            if skill.level >= resource.level:
                logger.info(f'Event can be fulfilled: Gather {resource_code}')

                gear_positions: List[str] = self.service.get_confining_gear_positions(character)
                for gear_position in gear_positions:
                    template_result.append(Task.unequip(slot=gear_position))

                lock_acquired = self.equipment_lock_table.acquire_lock(character.name)
                if lock_acquired:
                    bank_items_map = self.service.get_bank_items_map(task_id=task.task_id, character_name=character.name)
                    equip_map = self.service.get_gather_equipment(skill=resource.skill, character=character, bank_items_map=bank_items_map)

                    if len(equip_map) > 0:
                        reservation_id = self.service.reserve_equipment(character, equip_map)
                        logger.info(f'Plan to equip {equip_map} to gather {resource.code} more efficiently.')
                        template_result.append(Task.equip_items(items_map=equip_map, task_id=reservation_id))

                    self.equipment_lock_table.release_lock(character.name)

                    template_result.append(Task.move(map_id=event.map.map_id))
                    template_result.append(
                        Task.gather(
                            task_id=task.task_id,
                            skill=str(resource.skill),
                            resource=event.map.interactions.content.code,
                            until=Until(date_time=event.expiration),
                        )
                    )

                    logger.info(f'Plan to gather resource={resource_code} until {event.expiration}')
                else:
                    template_result.append(Task.sleep(seconds=10))
                    template_result.repeat(until=task.until)

            else:
                logger.info(f'Cannot gather resource={resource_code} (yet).')
        else:
            logger.info(f'Resource={resource_code} not found.')

    def handle_npc_event(
        self,
        event: ActiveEventSchema,
        content_type: str,
        npc_code: str,
        template_result: TemplateResult,
        character: CharacterSchemaExtension,
        trade_limits: Dict[str, Dict[str, int]],
        context: Optional[ExecutionContext] = None,
    ):
        if not trade_limits:
            logger.error(f'event={event.code}, event parameter "trade_limits" is empty.')
            return

        npc = self.service.get_npc(npc_code)
        global_quantity_map: Dict[str, int] = self.service.get_global_quantity_map()
        available_gold = self.service.get_bank_details().gold + character.gold
        bank_items_map = self.service.get_bank_items_map(context=context)

        buy_templates = []
        sell_templates = []

        event_end_ts = int(event.expiration.timestamp())
        for item_code, limits in trade_limits.items():
            if item_code in npc.items:
                global_quantity_item = global_quantity_map.get(item_code, 0)
                if 'max_quantity' in limits and global_quantity_item > limits['max_quantity'] + limits.get('threshold', 0):
                    bank_quantity = bank_items_map.get(item_code, 0)
                    character_quantity = character.inventory_map[item_code]
                    sell_quantity = min(global_quantity_item - limits['max_quantity'], bank_quantity + character_quantity)
                    if sell_quantity > 0:
                        task = Task.sell_to_npc(
                            item=item_code,
                            quantity=global_quantity_item - limits['max_quantity'],
                            content_type=content_type,
                            npc=npc.code,
                            map_id=event.map.map_id,
                            event_end_ts=event_end_ts,
                        )
                        sell_templates.append(task)

                elif 'min_quantity' in limits and global_quantity_item < limits['min_quantity']:
                    if available_gold > npc.items[item_code].buy_price:
                        task = Task.buy_from_npc(
                            item=item_code,
                            quantity=limits['min_quantity'] + limits.get('threshold', 0) - global_quantity_item,
                            npc=npc.code,
                            map_id=event.map.map_id,
                            event_end_ts=event_end_ts,
                        )
                        buy_templates.append(task)

        template_result.extend(sell_templates)
        template_result.extend(buy_templates)
