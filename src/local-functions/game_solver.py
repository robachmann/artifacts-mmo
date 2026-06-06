from collections import defaultdict
from datetime import datetime
from typing import Counter, Dict, List, Set
from zoneinfo import ZoneInfo

from local_environment import LocalEnvironment

from artifactsmmo.extensions import ItemSchemaExtension, MonsterSchemaExtension
from artifactsmmo.fights.combat_result import CombatResults
from artifactsmmo.fights.equipment_assembler import EquipmentScope
from artifactsmmo.game_constants import GEAR_TYPES, LEADER_CRAFTING_SKILLS, MAX_LEVEL
from artifactsmmo.log.logger import logger
from artifactsmmo.models import CraftSkill
from artifactsmmo.service.item_origin_service import ItemOrigin


class LevelConfig:
    def __init__(self, level, gear, weapon, jewelry):
        self.character_level = level
        self.gearcrafting_level = gear
        self.weaponcrafting_level = weapon
        self.jewelrycrafting_level = jewelry

    def get_key(self):
        return f'{self.character_level}.{self.gearcrafting_level}.{self.weaponcrafting_level}.{self.jewelrycrafting_level}'

    def get_skills_key(self):
        return f'{self.gearcrafting_level}.{self.weaponcrafting_level}.{self.jewelrycrafting_level}'

    @classmethod
    def from_tuple(cls, current_level, gear, weapon, jewelry):
        return cls(current_level, gear, weapon, jewelry)


class ReportFunction(LocalEnvironment):
    def __init__(self):
        super().__init__()
        self.craftable_tools: Dict[str, ItemSchemaExtension] = {}
        self.character_count: int = 3
        self.character_count_rare_gear: int = 1
        self.character_count_runes: int = 3
        self.consumable_min_qty: int = 50
        self.current_character_level: int = 1
        self.single_file: bool = True
        self.use_live_values: bool = True
        self.use_utilities_against_event_monsters: bool = False
        self.craft_tools = False if self.use_live_values else True

        self.ensured_skill_levels: Dict[str, int] = {
            CraftSkill.GEARCRAFTING: 1,
            CraftSkill.WEAPONCRAFTING: 1,
            CraftSkill.JEWELRYCRAFTING: 1,
        }
        self.skill_map = {
            CraftSkill.GEARCRAFTING: 1,
            CraftSkill.WEAPONCRAFTING: 1,
            CraftSkill.JEWELRYCRAFTING: 1,
        }
        self.crafted_items: Dict[str, int] = {}
        dt = datetime.now(ZoneInfo('Europe/Zurich')).replace(microsecond=0)
        self.timestamp = dt.replace(tzinfo=None).strftime('%Y-%m-%d_%H%M%S')

    def handler(self):
        characters = self.service.get_all_character_details()

        character = next(c for c in characters if c.name == self.character_1_name)
        character_configs: List[LevelConfig] = self.__create_character_configs()
        current_config_idx = 0
        bank_items_map = defaultdict(int)

        defeatable_monsters: Set[str] = set()
        with_consumables_defeatable_monsters: Set[str] = set()
        undefeatable_monsters: Set[str] = {m.code for m in self.service.get_all_monsters()}
        exclude_items: Dict[str, ItemOrigin] = {}

        for item in self.service.get_all_items():
            if item.type in GEAR_TYPES:
                exclude_items[item.code] = self.service.get_item_origin(item.code)

        self.unlock_items(exclude_items, defeatable_monsters)

        if self.use_live_values:
            character_configs = [
                config
                for config in character_configs
                if config.character_level >= character.level
                and config.gearcrafting_level >= character.skills[CraftSkill.GEARCRAFTING].level
                and config.weaponcrafting_level >= character.skills[CraftSkill.WEAPONCRAFTING].level
                and config.jewelrycrafting_level >= character.skills[CraftSkill.JEWELRYCRAFTING].level
            ]
            bank_items_map.update(self.service.get_global_quantity_map())
            self.crafted_items.update(bank_items_map)
            self.ensured_skill_levels[CraftSkill.GEARCRAFTING] = character.skills[CraftSkill.GEARCRAFTING].level
            self.ensured_skill_levels[CraftSkill.WEAPONCRAFTING] = character.skills[CraftSkill.WEAPONCRAFTING].level
            self.ensured_skill_levels[CraftSkill.JEWELRYCRAFTING] = character.skills[CraftSkill.JEWELRYCRAFTING].level
            self.unlock_items(exclude_items, defeatable_monsters, list(bank_items_map.keys()))
        else:
            character.level = 1
            bank_items_map['wooden_stick'] = 5
        all_characters_inventory_map = {'copper_ore': 1}

        while current_config_idx < len(character_configs):
            character.level = character_configs[current_config_idx].character_level
            self.skill_map[CraftSkill.GEARCRAFTING] = character_configs[current_config_idx].gearcrafting_level
            self.skill_map[CraftSkill.WEAPONCRAFTING] = character_configs[current_config_idx].weaponcrafting_level
            self.skill_map[CraftSkill.JEWELRYCRAFTING] = character_configs[current_config_idx].jewelrycrafting_level
            self.skill_map[CraftSkill.ALCHEMY] = character_configs[current_config_idx].character_level

            self.__check_craftable_tools(bank_items_map)

            logger.info(f'🆙 character.level={character.level}, skill_map={self.skill_map}')
            defeatable_monster_added = False
            for monster in self.service.get_monsters_by_level(max_level=character.level + 5):
                if monster.code not in defeatable_monsters or monster.code in with_consumables_defeatable_monsters:
                    result = self.__find_config(
                        monster,
                        character,
                        bank_items_map,
                        all_characters_inventory_map,
                        list(exclude_items.keys()),
                    )

                    if result and result.character_wins:
                        remove_monster = False
                        if any(c.used_utilities for c in result.characters.values()):
                            if monster.code not in with_consumables_defeatable_monsters:
                                with_consumables_defeatable_monsters.add(monster.code)
                                remove_monster = True
                        else:
                            defeatable_monsters.add(monster.code)
                            remove_monster = True
                            if monster.code in with_consumables_defeatable_monsters:
                                with_consumables_defeatable_monsters.remove(monster.code)

                        if remove_monster:
                            if monster.code in undefeatable_monsters:
                                undefeatable_monsters.remove(monster.code)
                                logger.warning(f'Remaining undefeatable monsters: {undefeatable_monsters}.')
                                defeatable_monster_added = True
                                self.unlock_items(exclude_items, defeatable_monsters | with_consumables_defeatable_monsters)
                            logger.info(
                                f'✅ character_level={character.level}, 👾 monster={monster.code} ({monster.level}): {result.character_wins}'
                            )
                            self.__log_next_result(
                                monster,
                                character.level,
                                result,
                                bank_items_map,
                            )
                            for equipment in [c.equipment for c in result.characters.values()]:
                                for gear_slot, item_code in equipment.items():
                                    bank_items_map[item_code] += 1

                            self.__check_craftable_tools(bank_items_map)

            if not defeatable_monster_added:
                current_config_idx += 1

        resolved_recipes, immediately_craftable = self.service.resolve_recipes(self.crafted_items, bank_items_map)
        self.__log_and_append(f'# crafted_items: {self.crafted_items}')
        self.__log_and_append(f'# resolved_recipes: {resolved_recipes.all_items}')

        logger.warning('#################################################################################################')
        logger.error('  #################################################################################################')
        logger.warning('#################################################################################################')

    def __find_config(self, monster, character, bank_items_map, all_characters_inventory_map, exclude_items: List[str]):
        if monster.type == 'boss':
            return self.__find_boss_config(monster, character, bank_items_map, all_characters_inventory_map, exclude_items)
        else:
            return self.__find_single_config(monster, character, bank_items_map, all_characters_inventory_map, exclude_items)

    @staticmethod
    def __create_character_configs(max_level=50, step=5):
        progression: List[LevelConfig] = []

        current_level = 1
        gear = weapon = jewelry = 1
        tier = 5

        # Handle levels before the first tier upgrade (i.e., levels 1 to 4)
        while current_level < tier:
            progression.append(LevelConfig.from_tuple(current_level, gear, weapon, jewelry))
            current_level += 1

        while tier <= max_level:
            # Step 1: When we reach the tier level, character level stays same and crafting levels update
            progression.append(LevelConfig.from_tuple(tier, gear, weapon, jewelry))  # Initial at this tier

            if gear < tier:
                gear = tier
                progression.append(LevelConfig.from_tuple(tier, gear, weapon, jewelry))
            if weapon < tier:
                weapon = tier
                progression.append(LevelConfig.from_tuple(tier, gear, weapon, jewelry))
            if jewelry < tier:
                jewelry = tier
                progression.append(LevelConfig.from_tuple(tier, gear, weapon, jewelry))

            # Step 2: Progress character level until next tier
            next_tier = tier + step
            for level in range(tier + 1, min(next_tier, max_level + 1)):
                progression.append(LevelConfig.from_tuple(level, gear, weapon, jewelry))
            tier = next_tier
            # current_level = tier

        return progression

    def __log_and_append(self, text: str):
        file_name = self.__get_file_name()
        logger.info(text)
        with open(file_name, 'a') as file:
            file.write(text + '\n')

    def __log_next_result(self, monster: MonsterSchemaExtension, required_character_level: int, config: CombatResults, bank_items_map):
        required_skills = defaultdict(int)
        for c in config.characters.values():
            for item_code in c.equipment.values():
                item = self.service.get_item(item_code)
                if item.craft:
                    required_skills[item.craft.skill] = max(required_skills[item.craft.skill], item.craft.level)

        for skill, level in required_skills.items():
            if level > self.ensured_skill_levels[skill]:
                self.__log_and_append(f'Task.level_skill(skill=CraftSkill.{str(skill).upper()}, target_level={level}, request_support=True),')
                self.ensured_skill_levels[skill] = level

        new_gear: Dict[str, int] = {}
        for c in config.characters.values():
            for gear_position, item_code in c.equipment.items():
                if item_code not in self.crafted_items:
                    characters = self.character_count
                    quantity = 1
                    if gear_position.startswith('ring'):
                        quantity = 2

                    item_origin = self.service.get_item_origin(item_code)
                    if item_code.endswith('_rune'):
                        characters = self.character_count_runes
                    elif item_origin and (item_origin.monsters or (not item_origin.monsters and item_origin.npcs)):
                        characters = self.character_count_rare_gear
                    else:
                        resolved_recipe = self.service.resolve_item_recipe(item_code, bank_items_map)
                        for dependency in resolved_recipe.all_items.keys():
                            origin = self.service.get_item_origin(dependency)
                            if origin and (
                                (origin.monsters and all(drop.is_event for drop in origin.monsters.values()))
                                or (origin.resources and all(drop.is_event for drop in origin.resources.values()))
                                # or (origin.npcs and all(drop.is_event for drop in origin.npcs.values()))
                                or (origin.tasks and all(drop for drop in origin.tasks))
                            ):
                                characters = self.character_count_rare_gear
                                break

                    if item_code not in new_gear:
                        new_gear[item_code] = quantity * characters
                    else:
                        new_gear[item_code] += quantity * characters
                    if item_code not in self.crafted_items:
                        self.crafted_items[item_code] = quantity * characters
                    else:
                        self.crafted_items[item_code] += quantity * characters

        if new_gear:
            self.__log_and_append(f'Task.ensure_equipment(exact_map={new_gear}),')
        if required_character_level > self.current_character_level:
            self.current_character_level = required_character_level
            self.__log_and_append(f'Task.level_fight(target_level={required_character_level}),')
        if any(c.used_utilities for c in config.characters.values()):
            used_utilities = Counter()
            for c in config.characters.values():
                used_utilities.update(c.used_utilities)
            for utility_code in used_utilities:
                used_utilities[utility_code] = used_utilities[utility_code] * self.consumable_min_qty
            self.__log_and_append(f'Task.ensure_equipment(exact_map={dict(used_utilities)}),')
            self.__log_and_append(f'# Monster {monster.code} ({monster.level}) can now be killed with consumables.')
            if monster.is_event_monster:
                self.__log_and_append(f"Task.send_message('Event monster {monster.name} can now be killed.'),")
        else:
            self.__log_and_append(f'# Monster {monster.code} ({monster.level}) can now be killed.')

    def __log_next_tool(self, item: ItemSchemaExtension, bank_items_map):
        required_skills = defaultdict(int)

        if item.craft:
            required_skills[item.craft.skill] = max(required_skills[item.craft.skill], item.craft.level)

        for skill, level in required_skills.items():
            if level > self.ensured_skill_levels[skill]:
                self.__log_and_append(f'Task.level_skill(skill=CraftSkill.{str(skill).upper()}, target_level={level}, request_support=True),')
                self.ensured_skill_levels[skill] = level

        new_gear: Dict[str, int] = {}

        if item.code not in self.crafted_items:
            characters = self.character_count
            quantity = 1
            if item.type.startswith('ring'):
                quantity = 2

            item_origin = self.service.get_item_origin(item.code)
            if item_origin and item_origin.monsters:
                characters = self.character_count_rare_gear
            else:
                resolved_recipe = self.service.resolve_item_recipe(item.code, bank_items_map)
                for dependency in resolved_recipe.all_items.keys():
                    origin = self.service.get_item_origin(dependency)
                    if origin and (
                        (origin.monsters and all(drop.is_event for drop in origin.monsters.values()))
                        or (origin.resources and all(drop.is_event for drop in origin.resources.values()))
                        # or (origin.npcs and all(drop.is_event for drop in origin.npcs.values()))
                        or (origin.tasks and all(drop for drop in origin.tasks))
                    ):
                        characters = self.character_count_rare_gear
                        break

            new_gear[item.code] = quantity * characters
            if item.code not in self.crafted_items:
                self.crafted_items[item.code] = quantity * characters
            else:
                self.crafted_items[item.code] += quantity * characters

        if new_gear:
            self.__log_and_append(f'Task.ensure_equipment(exact_map={new_gear}),')

    def unlock_items(self, exclude_items: Dict[str, ItemOrigin], defeatable_monsters: Set[str], existing_items: List[str] = None):
        delete_keys = existing_items or []
        for item_code, item_origin in exclude_items.items():
            obtainable = True
            if item_origin:
                for monster_list in item_origin.monster_tree:
                    if not any(monster_code in defeatable_monsters for monster_code in monster_list):
                        obtainable = False
            if obtainable:
                delete_keys.append(item_code)

        for item_code in delete_keys:
            if item_code in exclude_items and item_code != 'corrupted_skull':
                del exclude_items[item_code]
                tool = self.service.get_item(item_code)
                if tool.subtype == 'tool':
                    self.craftable_tools[tool.code] = tool
                    logger.info(f'Unlocked tool {tool.code}')
                else:
                    logger.info(f'Unlocked gear {item_code}')

    def __check_craftable_tools(self, bank_items_map):
        if self.craft_tools:
            remove_tools = []
            for tool_code, tool in self.craftable_tools.items():
                if tool_code not in self.crafted_items and self.ensured_skill_levels[CraftSkill.WEAPONCRAFTING] >= tool.level:
                    self.__log_next_tool(tool, bank_items_map)
                    remove_tools.append(tool_code)

            for tool_code in remove_tools:
                del self.craftable_tools[tool_code]

    def __get_file_name(self) -> str:
        if self.single_file:
            level_bracket = ''
        else:
            level_bracket = '_' + self.__get_level_bracket_suffix(self.skill_map)
        return f'game_solver_{self.timestamp}{level_bracket}.txt'

    @staticmethod
    def __get_level_bracket_suffix(skill_map):
        if any(skill_map[skill] < 10 for skill in LEADER_CRAFTING_SKILLS):
            return '1_9'
        elif any(skill_map[skill] < 20 for skill in LEADER_CRAFTING_SKILLS):
            return '10_19'
        elif any(skill_map[skill] < 30 for skill in LEADER_CRAFTING_SKILLS):
            return '20_29'
        elif any(skill_map[skill] < 40 for skill in LEADER_CRAFTING_SKILLS):
            return '30_39'
        elif any(skill_map[skill] < MAX_LEVEL for skill in LEADER_CRAFTING_SKILLS):
            return '40_49'
        else:
            return '50'

    def __find_boss_config(self, monster, character, bank_items_map, all_characters_inventory_map, exclude_items):
        craftable_config = self.fight_simulator.find_best_multi_character_fight_config(
            monster=monster,
            characters=3 * [character],
            exclude_drops_from_monsters=[],
            exclude_items_if_unavailable=[],
            exclude_items=exclude_items,
            include_items=[],
            equipment_scope=EquipmentScope.CRAFTABLE_AND_MONSTER_DROPS,
            utility_scope=EquipmentScope.CRAFTABLE
            if self.use_utilities_against_event_monsters and monster.is_event_monster
            else EquipmentScope.NONE,
            # skill_map=self.skill_map,
            # calculator_mode=CombatCalculatorMode.GENERIC,
            bank_items_map=bank_items_map,
            # all_characters_inventory_map=all_characters_inventory_map,
        )

        if craftable_config and craftable_config.character_wins:
            available_config = self.fight_simulator.find_best_multi_character_fight_config(
                monster=monster,
                characters=3 * [character],
                exclude_drops_from_monsters=[],
                exclude_items_if_unavailable=[],
                exclude_items=exclude_items,
                include_items=[],
                equipment_scope=EquipmentScope.AVAILABLE,
                utility_scope=EquipmentScope.CRAFTABLE
                if self.use_utilities_against_event_monsters and monster.is_event_monster
                else EquipmentScope.NONE,
                # skill_map=self.skill_map,
                # calculator_mode=CombatCalculatorMode.GENERIC,
                bank_items_map=bank_items_map,
                # all_characters_inventory_map=all_characters_inventory_map,
            )

            if available_config and available_config.character_wins:
                time_delta = available_config.gather_time - craftable_config.gather_time
                if time_delta < 0:
                    return available_config

        return craftable_config

    def __find_single_config(self, monster, character, bank_items_map, all_characters_inventory_map, exclude_items):
        craftable_config = self.fight_simulator.find_best_fight_config(
            monster=monster,
            character=character,
            exclude_drops_from_monsters=[],
            exclude_items_if_unavailable=[],
            exclude_items=exclude_items,
            include_items=[],
            equipment_scope=EquipmentScope.CRAFTABLE_AND_MONSTER_DROPS,
            utility_scope=EquipmentScope.CRAFTABLE
            if self.use_utilities_against_event_monsters and monster.is_event_monster
            else EquipmentScope.NONE,
            skill_map=self.skill_map,
            bank_items_map=bank_items_map,
            all_characters_inventory_map=all_characters_inventory_map,
        )

        if craftable_config.character_wins:
            available_config = self.fight_simulator.find_best_fight_config(
                monster=monster,
                character=character,
                exclude_drops_from_monsters=[],
                exclude_items_if_unavailable=[],
                exclude_items=exclude_items,
                include_items=[],
                equipment_scope=EquipmentScope.AVAILABLE,
                utility_scope=EquipmentScope.CRAFTABLE
                if self.use_utilities_against_event_monsters and monster.is_event_monster
                else EquipmentScope.NONE,
                skill_map=self.skill_map,
                bank_items_map=bank_items_map,
                all_characters_inventory_map=all_characters_inventory_map,
            )

            if available_config and available_config.character_wins:
                time_delta = available_config.gather_time - craftable_config.gather_time
                if time_delta < 0:
                    return available_config

        return craftable_config


report_function = ReportFunction()


if __name__ == '__main__':
    report_function.handler()
