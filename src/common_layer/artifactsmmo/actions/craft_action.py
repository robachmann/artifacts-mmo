from typing import Dict

from artifactsmmo.actions.action_result import ActionResult
from artifactsmmo.actions.action_strategy import ActionStrategy
from artifactsmmo.extensions import CharacterSchemaExtension, ItemSchemaExtension
from artifactsmmo.log.logger import logger
from artifactsmmo.models import ItemType, LogType
from artifactsmmo.service.execution_context import ExecutionContext
from artifactsmmo.service.helpers import escape_string
from artifactsmmo.service.tasks import Task


class CraftAction(ActionStrategy):
    def action(self) -> str:
        return 'craft'

    @staticmethod
    def describe_task(task: Task) -> str:
        target = ' (♻️)' if task.extra.get('target') == 'recycle' else ''
        return f'{task.extra.get("quantity") * task.ttl if task.ttl else task.extra.get("quantity")}x {task.extra.get("item")}{target}'

    def process(self, character: CharacterSchemaExtension, task: Task, quest_id: str = None, context: ExecutionContext = None) -> ActionResult:
        action_result: ActionResult = ActionResult()
        extra = task.extra
        item_code = extra.get('item')
        quantity = int(extra.get('quantity', 1))
        allow_fewer = bool(extra.get('allow_fewer', False))
        should_recraft = bool(extra.get('recraft', False))
        skill_name = extra.get('skill')
        target = extra.get('target', 'bank')
        if target is None:
            target = 'bank'

        if character.inventory_map.total() > 0:
            if allow_fewer:
                quantity = self.get_max_quantity(character.inventory_map, item_code, quantity)
            craft_again = True
            logger.info(f'Craft item {item_code} {quantity} times (allow_fewer={allow_fewer}).')
            if quantity > 0:
                while craft_again:
                    craft_again = False
                    status_code, result, error = self.actions_client.craft(character, item_code, quantity)
                    match status_code:
                        case 200:
                            logger.info(
                                f'Crafted item {item_code} {quantity} times, '
                                f'target={target}, received_xp={result.details.xp}, '
                                f'xp_per_craft={result.details.xp / quantity}'
                            )
                            item = self.service.get_item(item_code)

                            for craft in result.details.items:
                                self.counters_table.increment(craft.code, 'crafts', craft.quantity, result.cooldown.total_seconds)

                            if target == 'recycle':
                                if item.craft and item.type != ItemType.CONSUMABLE:
                                    action_result.append(Task.recycle(item=item_code, quantity=quantity, recraft=should_recraft))

                            elif target == 'tasks_master':
                                action_result.append(Task.move(content_type='tasks_master', content_code='items'))
                                action_result.append(Task.trade(item=item_code, quantity=quantity))
                            else:
                                if item.type not in [ItemType.RESOURCE, ItemType.UTILITY, ItemType.CONSUMABLE]:
                                    self.telegram_client.send_notification(
                                        f'🛠 *{escape_string(character.name)}* crafted {quantity} *{escape_string(item_code)}*\\.',
                                        parse_mode='MarkdownV2',
                                    )

                            if not skill_name and item.craft:
                                skill_name = str(item.craft.skill)
                            if skill_name:
                                received_xp = result.details.xp
                                if received_xp is not None and result.character and character:
                                    previous_skill_level = character.skills[skill_name].level
                                    current_skill_level = getattr(result.character, f'{skill_name}_level')

                                    self.skill_stats_table.put_skill_stats(
                                        action=LogType.CRAFTING,
                                        skill=skill_name,
                                        level=previous_skill_level,
                                        subject=item_code,
                                        gained_xp=received_xp,
                                        count=quantity,
                                        cooldown=result.character.cooldown,
                                        subject_level=item.level,
                                        wisdom=character.wisdom,
                                    )

                                    if current_skill_level != previous_skill_level:
                                        self.telegram_client.send_notification(
                                            f'🆙 *{escape_string(character.name)}* '
                                            f'improved *{escape_string(skill_name)}* to level '
                                            f'*{escape_string(str(current_skill_level))}*\\.',
                                            parse_mode='MarkdownV2',
                                        )

                        case 478:
                            reloaded_character = self.service.get_character_details(character.name)
                            action_result.update_character(reloaded_character)
                            if allow_fewer and quantity > 1:
                                quantity -= 1
                                craft_again = True
                            else:
                                logger.warning(f'Missing item or insufficient quantity in your inventory: item={item_code}, quantity={quantity}')

                        case 499:  # The character is in cooldown.
                            msg = error.get('message', '')
                            character_cooldown = msg if msg else 'The character is in cooldown.'
                            logger.info(f'{character_cooldown} Fetching current character again.')
                            reloaded_character = self.service.get_character_details(character.name)
                            action_result.update_character(reloaded_character)
                            action_result.repeat()

                        case _:
                            logger.error(f'Unexpected response: {error}')
                            action_result.abort(f'{task.action}: {error}')

                    if result and result.character:
                        action_result.update_character(result.character)
            else:
                logger.warning(f'Not enough resources to craft item={item_code}')
        else:
            logger.warning('Inventory of Character is empty, skipping "craft" task.')

        return action_result

    def get_max_quantity(self, inventory_map: Dict[str, int], item_code: str, desired_quantity: int):
        max_quantity = desired_quantity
        item: ItemSchemaExtension = self.service.get_item(item_code=item_code)
        if item.craft:
            for i in item.craft.items:
                available = inventory_map.get(i.code, 0)
                possible = available // i.quantity
                if possible < max_quantity:
                    max_quantity = possible
        logger.info(f'Craft {item_code}, desired_quantity={desired_quantity}, max_quantity: {max_quantity}')
        return max_quantity
