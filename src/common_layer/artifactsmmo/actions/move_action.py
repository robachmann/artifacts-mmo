from collections import defaultdict
from typing import Optional

from artifactsmmo.actions.action_result import ActionResult
from artifactsmmo.actions.action_strategy import ActionStrategy
from artifactsmmo.extensions import CharacterSchemaExtension, ItemSchemaExtension
from artifactsmmo.extensions.MapSchemaExtension import MapSchemaExtension
from artifactsmmo.log.logger import logger
from artifactsmmo.service.execution_context import ExecutionContext
from artifactsmmo.service.map_service import Route
from artifactsmmo.service.tasks import NextMove, Task


class MoveAction(ActionStrategy):
    def action(self) -> str:
        return 'move'

    def describe_task(self, task: Task) -> str:
        if task.extra.get('map_id') is not None:
            map_id = task.extra.get('map_id')
            target_map = self.service.get_map_by_id(map_id)
            if not target_map:
                logger.error(f'map_id={map_id} not found.')
                content_str = ''
            else:
                content_str = (
                    target_map.interactions.content.code
                    if target_map.interactions and target_map.interactions.content
                    else target_map.name.lower()
                )
            return f'to ({target_map.layer}, {target_map.x}, {target_map.y}) [{content_str}]'
        elif task.extra.get('x') is not None and task.extra.get('y') is not None:
            return f'({task.extra.get("x")}, {task.extra.get("y")})'
        elif task.extra.get('content_code'):
            return 'to ' + task.extra.get('content_code')
        return ''

    def process(self, character: CharacterSchemaExtension, task: Task, quest_id: str = None, context: ExecutionContext = None) -> ActionResult:
        action_result: ActionResult = ActionResult()
        target_x = task.extra.get('x')
        target_y = task.extra.get('y')
        content_type = task.extra.get('content_type')
        content_code = task.extra.get('content_code')
        target_map_id = task.extra.get('map_id')

        current_layer, current_x, current_y = character.position
        current_map = self.service.get_map_by_id(character.map_id)

        if target_map_id:
            target_map = self.service.get_map_by_id(target_map_id)
        elif target_x is not None or target_y is not None:
            target_map = self.service.get_map(target_x, target_y, 'overworld')
        else:
            target_map = self.service.get_closest_location(content_type, content_code, current_map)
            if not target_map:
                message = f'Could not find location of content_type={content_type}, content_code={content_code}'
                logger.error(message)
                action_result.abort(message)

        if target_map:
            if current_map.map_id != target_map.map_id:
                teleport_item = self.get_teleport_item(character, target_map, content_type, content_code)
                if teleport_item:
                    action_result.append(Task.use_item(teleport_item.code, task_id=task.task_id))
                    if teleport_item.item_effects['teleport'] != target_map.map_id:
                        action_result.repeat()
                else:
                    route = self.service.get_route(current_map.cluster_id, target_map.cluster_id)
                    if route:
                        if route.is_same_cluster:
                            self.__perform_move_action(character, target_map, action_result, task)
                        else:
                            if self.__is_shortcut_cheaper(character, route, current_map, target_map):
                                self.__use_shortcut(character, action_result, current_map)
                            else:
                                self.__move_to_target_cluster(character, route, action_result)
                    else:
                        action_result.abort(f'Could not find route from {current_map.map_id} to {target_map.map_id}')
            else:
                logger.info(
                    f'Character already stands at destination: current position=({current_x}, {current_y}) '
                    f'target position=({target_map.x}, {target_map.y})'
                )
        return action_result

    def get_teleport_item(
        self, character: CharacterSchemaExtension, target_map: MapSchemaExtension, content_type: str, content_code: str
    ) -> Optional[ItemSchemaExtension]:
        teleport_threshold = 6
        current_map = self.service.get_map_by_id(character.map_id)
        distance_walk = self.service.get_distance_between(current_map, target_map)
        cost_walk = self.service.get_cost_between(current_map, target_map)
        if distance_walk > teleport_threshold or cost_walk:
            teleport_options = []
            for item_code in character.inventory_map:
                item = self.service.get_item(item_code)
                if item.is_teleport_item:
                    teleport_id = item.item_effects['teleport']
                    teleport_map = self.service.get_map_by_id(teleport_id)
                    if teleport_id != character.map_id:
                        if teleport_id == target_map.map_id:
                            distance_teleport = 0
                            cost_teleport = 0
                        else:
                            if content_type or content_code:
                                location = self.service.get_closest_location(content_type, content_code, teleport_map)
                                if location:
                                    target_map = location
                            distance_teleport = self.service.get_distance_between(teleport_map, target_map)
                            cost_teleport = self.service.get_cost_between(teleport_map, target_map)

                        if distance_teleport + teleport_threshold < distance_walk or cost_teleport < cost_walk:
                            teleport_options.append(dict(item=item, cost=cost_teleport, distance=distance_teleport))
                        else:
                            logger.info(
                                f'Walking from ({character.x}, {character.y}) to ({target_map.x}, {target_map.y}) is faster than using {item.code}: distance_walk={distance_walk}, '
                                f'distance_teleport={distance_teleport} (+{teleport_threshold})'
                            )
            if teleport_options:
                best_element = min(teleport_options, key=lambda x: (x['cost'], x['distance']))
                item = best_element['item']

                teleport_map = self.service.get_map_by_id(item.item_effects['teleport'])
                logger.info(
                    f'Teleport plan: {character.layer}({character.x},{character.y}) -> '
                    f'{teleport_map.layer}({teleport_map.x},{teleport_map.y}) '
                    f"using '{item.code}' | "
                    f'Target: {target_map.layer}({target_map.x},{target_map.y}) | '
                    f'Walk: {distance_walk}, Teleport: {best_element["distance"]}, '
                    f'Saved: {(distance_walk - best_element["distance"]) * 5}s'
                )
                return item
        return None

    def __perform_move_action(
        self, character: CharacterSchemaExtension, target_map: MapSchemaExtension, action_result: ActionResult, task: Task
    ):
        status_code, result, error = self.actions_client.move(character, target_map.map_id)

        match status_code:
            case 200:
                logger.info(f'The character has moved successfully to layer={target_map.layer}, x={target_map.x}, y={target_map.y}.')
                self.counters_table.increment('tile', 'moves', result.cooldown.total_seconds // 5, result.cooldown.total_seconds)

            case 490:
                reloaded_character = self.service.get_character_details(character.name)
                action_result.update_character(reloaded_character)
                logger.info(
                    f'Character already at destination ({reloaded_character.x}, {reloaded_character.y}). Fetching current character again.'
                )

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

    def __move_to_target_cluster(self, character: CharacterSchemaExtension, route: Route, action_result: ActionResult):
        gateways = [gateway.map_id for gateway in route.gateways]
        next_move = NextMove(map_id=gateways[0])

        total_gold = 0
        item_map = defaultdict(int)
        for gateway in route.gateways:
            for condition in gateway.interactions.transition.conditions:
                if condition.code == 'gold':
                    total_gold += int(condition.value)
                else:
                    item = self.service.get_item(condition.code)
                    if item:
                        if item.code not in character.equipped_items:
                            item_map[condition.code] += int(condition.value)
                    else:
                        pass  # likely an achievement

        if total_gold > 0 or item_map:
            action_result.append(
                Task.ensure_inventory(
                    item_map=item_map,
                    gold=total_gold,
                    keep_consumables=True,
                    next_move=next_move,
                    deposit_gold=False,
                    keep_items=list(character.inventory_map.keys()),
                )
            )
        else:
            action_result.append(Task.move(map_id=gateways[0]))
        action_result.append(Task.transition())

        for map_id in gateways[1:]:  # start at second gateway
            action_result.append(Task.move(map_id=map_id))
            action_result.append(Task.transition())
        action_result.repeat()

    def __use_shortcut(self, character: CharacterSchemaExtension, action_result, current_map: MapSchemaExtension):
        closest_monster = self.service.get_closest_location(content_type='monster', current_map=current_map)
        action_result.append(Task.move(map_id=closest_monster.map_id))
        equipped_weapon = character.equipment.get('weapon')
        should_unequip_weapon = not character.is_inventory_full() and equipped_weapon
        if should_unequip_weapon:
            action_result.append(Task.unequip('weapon'))
        action_result.append(Task.force_fight(monster=closest_monster.interactions.content.code))
        if should_unequip_weapon:
            action_result.append(Task.equip(equipped_weapon, 'weapon'))

        action_result.repeat()
        logger.info(
            f'Plan to use shortcut via {closest_monster.interactions.content.code} at ({closest_monster.layer}, {closest_monster.x}, {closest_monster.y})'
        )

    def __is_shortcut_cheaper(self, character, route, current_map: MapSchemaExtension, target_map: MapSchemaExtension):
        spawn_map = self.service.get_map(0, 0)

        total_gold = 0
        total_distance = 0
        from_map = current_map
        for gateway in route.gateways:
            if gateway.cluster_id != spawn_map.cluster_id:
                total_distance += self.service.get_distance_between(from_map, gateway)
                from_map = self.service.get_map_by_id(gateway.interactions.transition.map_id)
                for condition in gateway.interactions.transition.conditions:
                    if condition.code == 'gold':
                        total_gold += int(condition.value)
            else:
                break
        total_distance += self.service.get_distance_between(from_map, target_map)

        nearest_monster_map = self.service.get_closest_location(content_type='monster', current_map=current_map)

        monster_code = nearest_monster_map.interactions.content.code
        monster = self.service.get_monster(monster_code)
        attack = sum(monster.attack_elem.values())
        turns_to_lose = min(100, character.hp // attack)
        seconds_to_lose = turns_to_lose * 2
        tiles_equivalent = min(2, seconds_to_lose // 5)

        shortcut_distance = (
            self.service.get_distance_between(spawn_map, target_map)
            + self.service.get_distance_between(current_map, nearest_monster_map)
            + tiles_equivalent
        )

        logger.info(
            f'Comparing distances: direct: current_map ({current_map.layer}, {current_map.x}, {current_map.y}) -> target_map ({target_map.layer}, '
            f'{target_map.x}, {target_map.y}), total_distance={total_distance}; '
            f'shortcut: spawn_map ({spawn_map.layer}, {spawn_map.x}, {spawn_map.y}) -> target_map ({target_map.layer}, {target_map.x}, '
            f'{target_map.y}), shortcut_distance={shortcut_distance}'
        )

        return total_gold > 0 or total_distance > shortcut_distance
