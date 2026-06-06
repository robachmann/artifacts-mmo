from typing import Optional

from artifactsmmo.actions.action_result import ActionResult
from artifactsmmo.actions.action_strategy import ActionStrategy
from artifactsmmo.extensions import CharacterSchemaExtension
from artifactsmmo.game_constants import SUPPRESS_DROP_CODES
from artifactsmmo.log.logger import logger
from artifactsmmo.models import LogType
from artifactsmmo.service.execution_context import ExecutionContext
from artifactsmmo.service.helpers import escape_string
from artifactsmmo.service.tasks import NextMove, Task


class GatherAction(ActionStrategy):
    def action(self) -> str:
        return 'gather'

    @staticmethod
    def describe_task(task: Task) -> str:
        if task.until:
            if task.until.drop_item:
                return f'{task.until.drop_item} at {task.extra.get("resource")} ({task.until.progress}/{task.until.drop_count})'
            elif task.until.skill_name and task.until.skill_level:
                return f'{task.extra.get("resource")} to level up {task.until.skill_name} to {task.until.skill_level}'
            elif task.until.achievement_code:
                return f'{task.extra.get("resource")} to solve achievement {task.until.achievement_code}'
        return f'{task.extra.get("resource")}'

    def process(self, character: CharacterSchemaExtension, task: Task, quest_id: str = None, context: ExecutionContext = None) -> ActionResult:
        action_result: ActionResult = ActionResult()
        extra = task.extra
        skill_name: Optional[str] = extra.get('skill')
        resource_name: Optional[str] = extra.get('resource')
        craft_into_code: Optional[str] = extra.get('craft')

        resource = self.service.get_resource(resource_name)
        resource_drop_count = len(resource.drops)

        if character.is_inventory_full(spacer=min(4, resource_drop_count)):
            will_craft = False
            if craft_into_code:
                craftable_count = self.service.get_craftable_recipe_count(craft_into_code, character.inventory_map)
                if craftable_count:
                    item = self.service.get_item(craft_into_code)
                    action_result.append(Task.move(content_type='workshop', content_code=str(item.craft.skill)))

                    action_result.append(Task.craft(item=craft_into_code, quantity=craftable_count, skill=skill_name))
                    current_map = self.service.get_map_by_id(character.map_id)
                    current_type = current_map.interactions.content.type
                    current_code = current_map.interactions.content.code
                    action_result.append(Task.ensure_inventory(next_move=NextMove(content_type=current_type, content_code=current_code)))
                    will_craft = True
                    logger.info(
                        f'Plan to craft {craftable_count}x {craft_into_code} at {skill_name} workshop before '
                        f'depositing items at bank and returning to {current_type}/{current_code}.'
                    )
                    # TODO: Check path costs

            if not will_craft:
                logger.info(
                    f'Inventory cannot hold expected number of drops of resource={resource_name}: '
                    f'current_total={character.inventory_map.total()}, inventory_size={character.inventory_max_items}, '
                    f'resource_drop_count={resource_drop_count}'
                )
                action_result.append(Task.ensure_inventory(task_id=task.task_id, return_previous_position=True))
            action_result.repeat()
        else:
            status_code, result, error = self.actions_client.gather(character)
            match status_code:
                case 200:  # The resource has been successfully gathered.
                    logger.debug('The resource has been successfully gathered.')

                    if skill_name:
                        received_xp = result.details.xp
                        if received_xp is not None and result.character and character:
                            if resource_name:
                                item_code = resource_name
                            else:
                                items = [i.code for i in result.details.items]
                                item_code = ','.join(items)

                            previous_skill_level = character.skills[skill_name].level
                            current_skill_level = getattr(result.character, f'{skill_name}_level')

                            if current_skill_level != previous_skill_level:
                                self.telegram_client.send_notification(
                                    f'🆙 *{escape_string(character.name)}* '
                                    f'improved *{escape_string(skill_name)}* to level '
                                    f'*{escape_string(str(current_skill_level))}*\\.',
                                    parse_mode='MarkdownV2',
                                )

                            resource = self.service.get_resource(resource_name)

                            self.skill_stats_table.put_skill_stats(
                                action=LogType.GATHERING,
                                skill=skill_name,
                                level=previous_skill_level,
                                subject=item_code,
                                gained_xp=received_xp,
                                cooldown=result.character.cooldown,
                                subject_level=resource.level,
                                wisdom=character.wisdom,
                            )

                    self.counters_table.increment(resource_name, 'resources', duration=result.cooldown.total_seconds)
                    for drop in result.details.items:
                        self.counters_table.increment(drop.code, f'drops.resources.{resource_name}', drop.quantity)
                        action_result.drops[drop.code] += drop.quantity

                        if self.service.is_item_rare_drop(drop.code) and drop.code not in SUPPRESS_DROP_CODES:
                            self.telegram_client.send_notification(
                                f'💎 *{escape_string(character.name)}* gathered {drop.quantity} *{escape_string(drop.code)}*\\.',
                                parse_mode='MarkdownV2',
                            )

                case 497:  # Character inventory is full.
                    logger.info('Character inventory is full. Adding tasks to deposit current inventory at bank and return to this location.')
                    reloaded_character = self.service.get_character_details(character.name)
                    action_result.update_character(reloaded_character)
                    action_result.append(Task.ensure_inventory(task_id=task.task_id, return_previous_position=True))
                    action_result.repeat()

                case 499:  # The character is in cooldown.
                    msg = error.get('message', '')
                    character_cooldown = msg if msg else 'The character is in cooldown.'
                    logger.info(f'{character_cooldown} Fetching current character again.')
                    reloaded_character = self.service.get_character_details(character.name)
                    action_result.update_character(reloaded_character)
                    action_result.repeat()

                case 598:  # Resource not found on this map.
                    reloaded_character = self.service.get_character_details(character.name)
                    action_result.update_character(reloaded_character)
                    message = (
                        f'Resource ({resource_name}) not found on this map. Character expected to stand at '
                        f'x={character.x}, y={character.y}. Character stands at '
                        f'x={reloaded_character.x}, y={reloaded_character.y}. Aborting.'
                    )
                    logger.error(message)
                    action_result.abort(message)

                case _:
                    logger.error(f'Unexpected response: {error}')
                    action_result.abort(f'{task.action}: {error}')

            if result and result.character:
                action_result.update_character(result.character)
        return action_result
