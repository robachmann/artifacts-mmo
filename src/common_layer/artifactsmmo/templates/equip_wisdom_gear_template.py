from collections import Counter, defaultdict
import random
from typing import Dict, List

from artifactsmmo.extensions import CharacterSchemaExtension, ItemSchemaExtension
from artifactsmmo.log.logger import logger
from artifactsmmo.service.execution_context import ExecutionContext
from artifactsmmo.service.tasks import Task
from artifactsmmo.templates.template_result import TemplateResult
from artifactsmmo.templates.template_strategy import TemplateStrategy


class EquipWisdomGearTemplate(TemplateStrategy):
    def template(self) -> str:
        return 'equip-wisdom-gear'

    def render(self, character: CharacterSchemaExtension, task: Task, quest_id: str = None, context: ExecutionContext = None) -> TemplateResult:
        template_result: TemplateResult = TemplateResult()
        task_id = task.task_id

        lock_acquired = self.equipment_lock_table.acquire_lock(character.name)
        if lock_acquired:
            bank_items_map = self.service.get_bank_items_map(task_id=task.task_id, character_name=character.name)
            available_items = set()
            on_character_map: Counter = Counter()
            available_items.update(bank_items_map.keys())
            available_items.update(character.inventory_map.keys())
            on_character_map.update(character.inventory_map)
            available_items.update(character.equipment.values())
            on_character_map.update(character.equipment.values())

            candidates_map = defaultdict(list)
            for item_code in available_items:
                if item_code:
                    item = self.service.get_item(item_code)
                    if item.wisdom_value() > 0 and character.can_equip(item):
                        candidates_map[item.type].append(item)

            equip_map: Dict[str, str] = {}
            top_available_items: Dict[str, str] = {}
            bank_reservation_map = {}
            for gear_slot, items in candidates_map.items():
                best_item = max(items, key=lambda i: (i.wisdom_value(), i.inventory_space_value()))
                top_available_items[gear_slot] = best_item.code
                if gear_slot == 'artifact':
                    equipped_artifacts_wisdom_sum = sum(
                        self.service.get_item(code).wisdom_value()
                        for key in ('artifact1', 'artifact2', 'artifact3')
                        if (code := character.equipment.get(key))
                    )
                    top_3_artifacts_wisdom_sum = sum(artifact.wisdom_value() for artifact in items[:3])

                    if top_3_artifacts_wisdom_sum > equipped_artifacts_wisdom_sum:
                        for idx, item in enumerate(items[:3], 1):
                            equip_map[f'artifact{idx}'] = item.code
                            if on_character_map.get(item.code, 0) < 1:
                                bank_reservation_map[item.code] = 1
                elif gear_slot == 'ring':
                    for item in items:
                        if (
                            self.__higher_wisdom_value(item, character.equipment.get('ring1'))
                            and on_character_map.get(item.code, 0) + bank_items_map.get(item.code, 0) >= 2
                        ):
                            equip_map['ring1'] = item.code
                            equip_map['ring2'] = item.code
                            if on_character_map.get(item.code, 0) < 2:
                                bank_reservation_map[item.code] = 2 - on_character_map.get(item.code, 0)
                            break

                else:
                    if self.__higher_wisdom_value(best_item, character.equipment.get(gear_slot)):
                        equip_map[gear_slot] = best_item.code
                        if on_character_map.get(best_item.code, 0) < 1:
                            bank_reservation_map[best_item.code] = 1

            if bank_reservation_map:
                self.service.add_bank_reservations(task_id, bank_reservation_map, character.name)
            if equip_map:
                upgrades_map = self.__get_upgrades_map(top_available_items, character.level)
                if upgrades_map:
                    logger.warning(f'Best available wisdom gear: equip_map={equip_map}, upgrades_map={upgrades_map}')

                    missing_gear = []
                    for avail, miss in upgrades_map.items():
                        missing_gear.extend(miss)

                    msg = f'{character.name} could maximize wisdom stats by equipping unavailable gear: {", ".join(missing_gear)}'
                    self.telegram_client.send_notification(msg)

                else:
                    logger.info(f'Best available wisdom gear: equip_map={equip_map}')
                template_result.append(Task.equip_items(items_map=equip_map, task_id=task_id))
            self.equipment_lock_table.release_lock(character.name)
        else:
            template_result.append(Task.sleep(seconds=random.randint(15, 20)))
            template_result.repeat(until=task.until)

        return template_result

    def __higher_wisdom_value(self, param: ItemSchemaExtension, equipped_item_code: str):
        if not equipped_item_code:
            return True
        equipped_item = self.service.get_item(equipped_item_code)
        if param.code == equipped_item_code:
            return False
        if equipped_item.is_confining_gear():
            return param.wisdom_value() >= equipped_item.wisdom_value()
        else:
            return param.wisdom_value() > equipped_item.wisdom_value()

    def __get_upgrades_map(self, equipment_map: Dict[str, str], max_level: int) -> Dict[str, List[str]]:
        wisdom_gear = self.service.get_best_wisdom_gear_by_level(max_level)
        upgrades_map: Dict[str, List[str]] = {}
        for slot, items in wisdom_gear.items():
            if not any(item.code in equipment_map.values() for item in items):
                upgrades_map[slot] = [i.code for i in items]
        return upgrades_map
