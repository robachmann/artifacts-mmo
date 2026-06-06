from collections import defaultdict
from itertools import chain
from typing import Counter, Dict, List

from artifactsmmo.extensions import CharacterSchemaExtension
from artifactsmmo.log.logger import logger
from artifactsmmo.service.execution_context import ExecutionContext
from artifactsmmo.service.tasks import Task
from artifactsmmo.templates.template_result import TemplateResult
from artifactsmmo.templates.template_strategy import TemplateStrategy


class EquipItemsTemplate(TemplateStrategy):
    def template(self) -> str:
        return 'equip-items'

    @staticmethod
    def describe_task(task: Task) -> str:
        equipment = task.extra.get('items_map') or {}
        items = Counter(equipment.values())
        items_str = []
        for item_code, item_qty in items.items():
            if item_qty > 1:
                items_str.append(f'{item_qty}x {item_code}')
            else:
                items_str.append(item_code)
        return ', '.join(items_str)

    def render(self, character: CharacterSchemaExtension, task: Task, quest_id: str = None, context: ExecutionContext = None) -> TemplateResult:
        template_result: TemplateResult = TemplateResult()
        new_tasks = []
        items_map: Dict[str, str] = task.extra.get('items_map')

        equip_tasks: List[Task] = []
        required_hp = 0
        # logger.info(f'equip items: items_map={items_map}')
        if items_map:
            bank_items_map = self.service.get_bank_items_map(task_id=task.task_id, character_name=character.name)
            equipped_artifacts = {
                character.artifact1_slot: 'artifact1',
                character.artifact2_slot: 'artifact2',
                character.artifact3_slot: 'artifact3',
            }
            available_slots = ['artifact1', 'artifact2', 'artifact3']

            for artifact_slot in ('artifact1', 'artifact2', 'artifact3'):
                artifact_code_to_equip = items_map.get(artifact_slot)
                if artifact_code_to_equip and artifact_code_to_equip in equipped_artifacts:
                    available_slots.remove(equipped_artifacts[artifact_code_to_equip])
                    items_map.pop(artifact_slot)
                    logger.info(f'Artifact {artifact_code_to_equip} is already equipped at {equipped_artifacts[artifact_code_to_equip]}.')

            if len(available_slots) < 3:
                new_artifact_slots = {}
                for artifact_slot in ('artifact1', 'artifact2', 'artifact3'):
                    artifact_code_to_equip = items_map.get(artifact_slot)
                    if artifact_code_to_equip:
                        new_slot = available_slots.pop()
                        if new_slot != artifact_slot:
                            new_artifact_slots[new_slot] = artifact_code_to_equip
                            items_map.pop(artifact_slot)
                            logger.info(f'Reassigned artifact {artifact_code_to_equip} from slot {artifact_slot} to {new_slot}')

                for item_slot, new_code in new_artifact_slots.items():
                    items_map[item_slot] = new_code

            withdraw_map: Dict[str, int] = defaultdict(int)
            for slot, item_code in items_map.items():
                currently_equipped_item = character.equipment.get(slot)
                if currently_equipped_item != item_code:
                    bank_quantity = bank_items_map.get(item_code, 0) + character.inventory_map.get(item_code, 0)
                    if bank_quantity > 0:
                        withdraw_map[item_code] += 1
                        logger.info(f'Added {item_code} to withdraw_map={dict(withdraw_map)}')
                        equip_tasks.append(Task.equip(item=item_code, slot=slot))
                        if currently_equipped_item:
                            currently_equipped_item_obj = self.service.get_item(currently_equipped_item)
                            required_hp += currently_equipped_item_obj.item_effects.get('hp', 0)
                    else:
                        logger.warning(f'Bank does not hold enough quantity to withdraw item: {item_code}, bank_quantity={bank_quantity}')
                else:
                    logger.debug('Item %s is already equipped.', item_code)

            if withdraw_map:
                logger.info(f'Plan to withdraw items={dict(withdraw_map)}')

                food_item_count = 0
                for item_code, item_qty in character.inventory_map.items():
                    item = self.service.get_item(item_code)
                    if item.is_processed_food:
                        food_item_count += item_qty

                keep_consumables = food_item_count + sum(withdraw_map.values()) < character.inventory_capacity()
                new_tasks.append(Task.ensure_inventory(item_map=withdraw_map, task_id=task.task_id, keep_consumables=keep_consumables))
        else:
            logger.warning('No items to equip provided.')

        if equip_tasks:
            if required_hp >= character.hp:
                self.__handle_low_hp(character, items_map, required_hp, new_tasks, task)
            new_tasks.extend(equip_tasks)
            new_tasks.append(Task.verify_equipment(items_map))
            new_tasks.append(Task.ensure_inventory(task_id=task.task_id))

        if new_tasks:
            template_result.extend(new_tasks)
        return template_result

    def __handle_low_hp(
        self,
        character: CharacterSchemaExtension,
        items_map: Dict[str, str],
        required_hp: int,
        new_tasks: List[Task],
        task: Task,
    ):
        rest_required = True
        remaining_required_hp = required_hp
        consume_map = self.food_service.get_best_food_to_consume(character, remaining_required_hp)

        consume_from_inventory_tasks: List[Task] = []
        withdraw_tasks: List[Task] = []
        consume_withdrawn_items_tasks: List[Task] = []

        if consume_map:
            total_heal = 0
            for food_code, food_qty in consume_map.items():
                consume_from_inventory_tasks.append(Task.use_item(item=food_code, quantity=food_qty, task_id=task.task_id))
                food = self.service.get_item(food_code)
                total_heal += food_qty * food.heal_value()
            if total_heal >= remaining_required_hp:
                rest_required = False
            else:
                remaining_required_hp -= total_heal

            logger.info(
                f'Consuming food from inventory will speed up the process. Plan to consume consume_map={consume_map}, '
                f'required_hp={required_hp}, total_heal={total_heal}, remaining_required_hp={remaining_required_hp}, '
                f'rest_required={rest_required}'
            )

        food_map = self.food_service.get_best_food_to_withdraw(character, remaining_required_hp)
        if food_map:
            withdraw_tasks.append(
                Task.ensure_inventory(
                    item_map=food_map,
                    task_id=task.task_id,
                    keep_items=list(items_map.values()),
                    deposit_gold=False,
                )
            )
            total_heal = 0
            for food_code, food_qty in food_map.items():
                consume_withdrawn_items_tasks.append(Task.use_item(item=food_code, quantity=food_qty, task_id=task.task_id))
                food = self.service.get_item(food_code)
                total_heal += food_qty * food.heal_value()
            if total_heal >= remaining_required_hp:
                rest_required = False

            logger.info(
                f'Consuming food from bank will speed up the process. Plan to withdraw and consume food_map={food_map}, '
                f'required_hp={required_hp}, total_heal={total_heal}, remaining_required_hp={remaining_required_hp}, '
                f'rest_required={rest_required}'
            )
        else:
            logger.info(f'No food found at bank to speed up the process by healing remaining_required_hp={remaining_required_hp}')

        new_tasks.extend(chain(consume_from_inventory_tasks, withdraw_tasks, consume_withdrawn_items_tasks))

        if rest_required:
            logger.info(
                f'Equipping items will replace currently equipped ones with required_hp={required_hp} >= character.hp={character.hp}, remaining_required_hp={remaining_required_hp}. '
                f'Adding rest to heal to full hp.'
            )
            new_tasks.append(Task.rest())
