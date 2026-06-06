from typing import Dict, List

from artifactsmmo.game_constants import LEADER_CRAFTING_SKILLS, MAX_LEVEL
from artifactsmmo.log.logger import logger
from artifactsmmo.models import CraftSkill
from artifactsmmo.service.helpers import character_1_name, character_2_name, character_3_name, character_4_name, character_5_name
from artifactsmmo.service.tasks import Task


def get_quest_join_exclusions() -> List[str]:
    return [character_1_name(), character_5_name()]


def get_quest_join_exclusion_map() -> Dict[str, List[str]]:
    return {
        character_1_name(): [
            # character_2_name(),
            # character_3_name(),
            character_4_name(),
            # character_5_name(),
        ],
        character_2_name(): [
            # character_1_name(),
            # character_3_name(),
            # character_4_name(),
            # character_5_name(),
        ],
        character_3_name(): [
            # character_1_name(),
            # character_2_name(),
            # character_4_name(),
            # character_5_name(),
        ],
        character_4_name(): [
            # character_1_name(),
            # character_2_name(),
            # character_3_name(),
            # character_5_name(),
        ],
        character_5_name(): [
            # character_1_name(),
            character_2_name(),
            character_3_name(),
            character_4_name(),
        ],
    }
    # example to prevent characters 1-4 to join quests of character 5
    # return {character_5_name(): [character_1_name(), character_2_name(), character_3_name(), character_4_name()]}


def get_quest_leaders() -> List[str]:
    return [character_1_name()]


def quest_leaders(skill_map: Dict[str, int]) -> Dict[str, List[Task]]:
    character_name = character_1_name()
    tasks: List[Task] = []

    if any(skill_map[skill] < 10 for skill in LEADER_CRAFTING_SKILLS):
        logger.info('At least one skill is < 10')

        # tasks: List[Task] = [
        #     Task.ensure_item(item='copper_pickaxe', global_max=5),
        #     Task.ensure_item(item='copper_axe', global_max=5),
        #     Task.ensure_item(item='fishing_net', global_max=1),
        #     # Task.ensure_item(item='apprentice_gloves', global_max=1),
        # ]
        #
        # tasks.extend(
        #     [
        #         Task.ensure_equipment(equipment_list=['wooden_staff'], quantity=5),
        #         Task.ensure_equipment(equipment_list=['wooden_staff', 'wooden_shield', 'copper_helmet', 'copper_boots'], quantity=4),
        #         Task.ensure_equipment(equipment_list=['copper_ring'], quantity=8),
        #         # Monster chicken can now be killed.
        #         Task.ensure_equipment(equipment_list=['copper_dagger'], quantity=4),
        #         # Monster yellow_slime can now be killed.
        #         Task.ensure_equipment(equipment_list=['sticky_sword'], quantity=4),
        #         # Monster green_slime can now be killed.
        #         Task.level_skill(skill=CraftSkill.WEAPONCRAFTING, target_level=5, request_support=True),
        #         Task.level_skill(skill=CraftSkill.GEARCRAFTING, target_level=5, request_support=True),
        #         Task.level_skill(skill=CraftSkill.JEWELRYCRAFTING, target_level=5, request_support=True),
        #         Task.ensure_equipment(equipment_list=['water_bow', 'feather_coat', 'copper_legs_armor'], quantity=4),
        #         Task.level_fight(target_level=5),
        #         # Monster sheep can now be killed.
        #         Task.ensure_equipment(equipment_list=['copper_armor'], quantity=4),
        #         # Monster blue_slime can now be killed.
        #         Task.ensure_equipment(equipment_list=['water_bow', 'feather_coat'], quantity=4),
        #         # Monster red_slime can now be killed.
        #         Task.ensure_equipment(equipment_list=['life_amulet'], quantity=4),
        #         # Monster cow can now be killed.
        #         Task.level_skill(skill=CraftSkill.WEAPONCRAFTING, target_level=10, request_support=True),
        #     ]
        # )
        #
        # tasks.extend(
        #     [
        #         Task.ensure_item(item='spruce_fishing_rod', global_max=1),
        #         Task.ensure_item(item='iron_axe', global_max=1),
        #         Task.ensure_item(item='iron_pickaxe', global_max=1),
        #         # Task.ensure_item(item='leather_gloves', global_max=1),
        #     ]
        # )

        tasks.extend(
            [
                # Task.level_skill(skill=CraftSkill.GEARCRAFTING, target_level=10, request_support=True),
                # Task.ensure_equipment(
                #     equipment_list=['iron_dagger', 'slime_shield', 'leather_hat', 'adventurer_vest', 'leather_legs_armor', 'iron_boots'],
                #     quantity=4,
                # ),
                # Task.level_fight(target_level=10),
                # # Monster mushmush can now be killed.
                # Task.ensure_equipment(equipment_list=['greater_wooden_staff', 'leather_armor'], quantity=4),
                # # Monster flying_snake can now be killed.
                # Task.ensure_equipment(equipment_list=['iron_sword', 'adventurer_helmet', 'iron_legs_armor'], quantity=4),
                # Task.ensure_equipment(equipment_list=['forest_ring'], quantity=8),
                # # Monster wolf can now be killed.
                # # Monster highwayman can now be killed.
                # Task.level_skill(skill=CraftSkill.GEARCRAFTING, target_level=15, request_support=True),
                # Task.level_skill(skill=CraftSkill.JEWELRYCRAFTING, target_level=10, request_support=True),
            ]
        )
    elif any(skill_map[skill] < 20 for skill in LEADER_CRAFTING_SKILLS):
        logger.info('At least one skill is < 20')
        # Task.ensure_equipment(equipment_list=['wolf_ears', 'mushmush_jacket', 'adventurer_pants', 'fire_and_earth_amulet'], quantity=4),
        # Task.level_fight(target_level=15),
        # # Monster pig can now be killed.
        # Task.ensure_equipment(
        #     equipment_list=['multislimes_sword', 'wolf_ears', 'adventurer_pants', 'leather_boots', 'wisdom_amulet'], quantity=4
        # ),
        # Task.ensure_equipment(equipment_list=['life_ring'], quantity=8),
        # Task.level_fight(target_level=16),
        # Monster skeleton can now be killed.
        # Task.send_message('Monster Skeleton can now be killed.'),
        # Task.level_skill(skill=CraftSkill.WEAPONCRAFTING, target_level=20, request_support=True),
        # Task.ensure_equipment(equipment_list=['wisdom_amulet'], quantity=4),

        # tasks.extend(
        #     [
        #         Task.ensure_item(item='steel_fishing_rod', global_max=1),
        #         Task.ensure_item(item='steel_axe', global_max=1),
        #         Task.ensure_item(item='steel_pickaxe', global_max=1),
        #         # Task.ensure_item(item='steel_gloves', global_max=1),
        # Task.level_skill(skill=CraftSkill.WEAPONCRAFTING, target_level=20, request_support=True),
        # Task.level_skill(skill=CraftSkill.GEARCRAFTING, target_level=20, request_support=True),
        # Task.level_skill(skill=CraftSkill.JEWELRYCRAFTING, target_level=20, request_support=True),
        #     ]
        # )
    elif any(skill_map[skill] < 30 for skill in LEADER_CRAFTING_SKILLS):
        logger.info('At least one skill is < 30')

        tasks.extend(
            [
                # Task.fight_monster('lich'),
                Task.exchange_task_coins(),
                # Task.ensure_equipment(
                #     equipment_list=[
                #         'skull_staff',
                #         'tromatising_mask',
                #         'skeleton_armor',
                #         'skeleton_pants',
                #         'hard_leather_boots',
                #         'skull_amulet',
                #         #'healing_rune',
                #         #'perfect_pearl',
                #         #'lost_world_map',
                #     ],
                #     quantity=4,
                # ),
                # Task.ensure_equipment(equipment_list=['apprentice_gloves'], quantity=3),
                Task.ensure_equipment(equipment_list=['healing_rune', 'burn_rune', 'lifesteal_rune'], quantity=1),
                Task.ensure_equipment(equipment_list=['healing_rune', 'lifesteal_rune'], quantity=2),
                Task.ensure_equipment(equipment_list=['burn_rune'], quantity=3),
                Task.ensure_equipment(equipment_list=['healing_rune'], quantity=3),
                # Task.level_fight(target_level=20),
                # Task.ensure_equipment(equipment_list=['ring_of_chance'], quantity=6),
                Task.ensure_equipment(equipment_list=['steel_boots'], quantity=4),
                # Monster ogre (20) can now be killed.
                # Task.ensure_equipment(equipment_list=['steel_shield', 'magic_wizard_hat', 'dreadful_amulet'], quantity=4),
                Task.ensure_equipment(equipment_str='steel_shield magic_wizard_hat dreadful_amulet', quantity=4),
                Task.ensure_equipment(equipment_list=['battlestaff', 'hard_leather_helmet', 'steel_legs_armor', 'wisdom_amulet'], quantity=4),
                Task.ensure_equipment(equipment_list=['steel_armor'], quantity=4),
                # Monster spider (20) can now be killed.
                Task.ensure_tools(level=20, mining=1, woodcutting=1, fishing=1, alchemy=0),
                Task.ensure_equipment(
                    equipment_list=['steel_battleaxe', 'hard_leather_armor', 'hard_leather_pants', 'snakeskin_boots'], quantity=4
                ),
                # Monster vampire (24) can now be killed.
                Task.ensure_equipment(equipment_list=['steel_armor', 'air_and_water_amulet'], quantity=4),
                Task.level_fight(target_level=25),
                Task.ensure_equipment(equipment_list=['vampire_bow'], quantity=1),
                Task.ensure_equipment(equipment_list=['piggy_armor'], quantity=2),
                # Task.ensure_equipment(exact_map={'small_antidote': 1, 'minor_health_potion': 7}),
                # Monster bandit_lizard (25) can now be killed with consumables.
                # Task.ensure_equipment(equipment_list=['piggy_armor'], quantity=1),
                Task.ensure_equipment(equipment_list=['piggy_pants'], quantity=1),
                # Task.send_message('Event monster Bandit Lizard can now be killed.'),
                # Task.ensure_equipment(equipment_list=['bandit_armor'], quantity=4),
                # Monster cyclops (25) can now be killed.
                # Monster owlbear (30) can now be killed.
                Task.level_skill(skill=CraftSkill.GEARCRAFTING, target_level=25, request_support=True),
                Task.ensure_equipment(equipment_list=['forest_whip', 'snakeskin_armor', 'snakeskin_legs_armor'], quantity=2),
                Task.ensure_equipment(equipment_list=['piggy_helmet', 'piggy_pants'], quantity=2),
                Task.ensure_equipment(equipment_list=['hunting_bow'], quantity=2),
                # Task.ensure_equipment(equipment_list=['skull_ring'], quantity=2),
                # Monster imp (28) can now be killed.
                Task.level_skill(skill=CraftSkill.WEAPONCRAFTING, target_level=25, request_support=True),
                # Task.ensure_equipment(equipment_list=['skull_wand'], quantity=2),
                # Task.ensure_equipment(equipment_list=['fire_boost_potion'], quantity=1),
                # Monster corrupted_ogre (20) can now be killed with consumables.
                # Task.send_message('Event monster Corrupted Ogre can now be killed with consumables.'),
                Task.ensure_equipment(equipment_list=['steel_shield', 'steel_boots'], quantity=2),
                # Monster bandit_lizard (25) can now be killed.
                # Monster death_knight (28) can now be killed.
                # Task.ensure_equipment(
                #     equipment_list=['dreadful_staff', 'lizard_skin_armor', 'lizard_skin_legs_armor', 'dreadful_amulet'], quantity=2
                # ),
                # Monster demon (30) can now be killed.
                Task.level_skill(skill=CraftSkill.JEWELRYCRAFTING, target_level=25, request_support=True),
                Task.level_skill(skill=CraftSkill.GEARCRAFTING, target_level=30, request_support=True),
                Task.level_skill(skill=CraftSkill.WEAPONCRAFTING, target_level=30, request_support=True),
                # Task.ensure_equipment(equipment_list=['dreadful_ring'], quantity=2),
                Task.ensure_tools(level=30, mining=3, woodcutting=3, fishing=1, alchemy=1),
                Task.ensure_equipment(equipment_list=['death_knight_sword'], quantity=1),
                Task.ensure_equipment(equipment_list=['emerald_amulet'], quantity=1),
                # Monster corrupted_ogre (20) can now be killed.
                Task.ensure_equipment(equipment_list=['topaz_amulet'], quantity=1),
                Task.level_fight(target_level=30),
                # Monster corrupted_owlbear (30) can now be killed.
                Task.ensure_equipment(
                    exact_map={
                        'greater_dreadful_staff': 1,
                        'gold_shield': 1,
                        'gold_helm': 1,
                        'gold_platebody': 1,
                        'obsidian_legs_armor': 1,
                        'lizard_boots': 1,
                        'sapphire_amulet': 1,
                        # 'dreadful_ring': 2,
                        'burn_rune': 1,
                        'perfect_pearl': 1,
                        'lost_world_map': 1,
                        'minor_health_potion': 6,
                    }
                ),
                # Task.send_message('Lich can now be killed with consumables.'),
                Task.ensure_equipment(equipment_list=['stormforged_pants'], quantity=2),
                # Monster cultist_acolyte (33) can now be killed.
                Task.ensure_equipment(
                    exact_map={
                        'greater_dreadful_staff': 2,
                        'gold_platebody': 3,
                        'obsidian_legs_armor': 1,
                        'lizard_boots': 2,
                        'gold_platelegs': 3,
                        'obsidian_armor': 2,
                        'gold_mask': 2,
                        'gold_sword': 3,
                    }
                ),
                Task.ensure_equipment(
                    exact_map={
                        'elderwood_staff': 2,
                        'gold_boots': 3,
                    }
                ),
                # Task.ensure_equipment(equipment_list=['gold_shield', 'obsidian_helmet', 'royal_skeleton_pants'], quantity=4),
                # Monster cursed_tree (34) can now be killed.
                # Task.ensure_equipment(
                #    equipment_list=['greater_dreadful_staff', 'gold_platebody', 'obsidian_legs_armor', 'lizard_boots', 'sapphire_amulet'],
                #    quantity=4,
                # ),
                # Monster lich (30) can now be killed.
                # Task.ensure_equipment(equipment_list=['gold_sword', 'gold_mask', 'obsidian_armor', 'gold_platelegs'], quantity=4),
                # Monster cultist_emperor (35) can now be killed with consumables.
                # Task.send_message('Event monster Cultist Emperor can now be killed.'),
                # Task.ensure_equipment(equipment_list=['conjurer_skirt'], quantity=3),
                # Monster goblin (35) can now be killed.
                Task.level_skill(skill=CraftSkill.JEWELRYCRAFTING, target_level=30, request_support=True),
            ]
        )
    elif any(skill_map[skill] < 40 for skill in LEADER_CRAFTING_SKILLS):
        logger.info('At least one skill is < 40')
        tasks.extend(
            [
                Task.ensure_equipment(exact_map={'bloodblade': 4, 'fire_shield': 3, 'corrupted_stone_amulet': 3, 'ruby_ring': 6}),
                # Task.ensure_equipment(exact_map={'water_shield': 1}),  # good match against Grimlet
                # Task.ensure_equipment(exact_map={'fire_shield': 1}),  # good match against Rosenblood
                Task.ensure_equipment(equipment_list=['healing_rune'], quantity=4),
                # Task.recycle_excess_items(),
                Task.exchange_task_coins(),
                # Task.ensure_equipment(
                #     exact_map={
                #         'mushmush_wizard_hat': 1,
                #         'earth_ring': 2,
                #     }
                # ),
                # Monster lich (30) can now be killed.
                Task.ensure_equipment(exact_map={'lich_crown': 1}),
                Task.ensure_equipment(exact_map={'life_crystal': 1}),
                # Monster corrupted_owlbear (30) can now be killed.
                # Monster cultist_acolyte (33) can now be killed.
                Task.level_skill(skill=CraftSkill.GEARCRAFTING, target_level=35, request_support=True),
                Task.ensure_equipment(exact_map={'enchanter_pants': 1}),
                Task.ensure_equipment(exact_map={'gold_ring': 8}),
                Task.ensure_equipment(exact_map={'gold_fishing_rod': 2}),
                # Monster cursed_tree (34) can now be killed.
                # Monster goblin (35) can now be killed.
                Task.ensure_equipment(exact_map={'jester_hat': 1, 'strangold_legs_armor': 1, 'dreadful_armor': 1, 'enchanter_boots': 1}),
                # Monster orc (38) can now be killed.
                Task.ensure_equipment(exact_map={'dreadful_shield': 1, 'ancient_jean': 1, 'topaz_ring': 2}),
                # Monster goblin_wolfrider (40) can now be killed.
                Task.level_skill(skill=CraftSkill.WEAPONCRAFTING, target_level=35, request_support=True),
                Task.ensure_equipment(exact_map={'diamond_sword': 1, 'magic_bow': 1}),
                Task.ensure_equipment(exact_map={'magic_bow': 1}),
                Task.level_skill(skill=CraftSkill.JEWELRYCRAFTING, target_level=35, request_support=True),
                Task.ensure_equipment(exact_map={'masterful_necklace': 1}),
                # Task.ensure_equipment(exact_map={'diamond_amulet': 1}),
                # Monster cultist_emperor (35) can now be killed.
                # Monster goblin (35) can now be killed.
                # Monster orc (38) can now be killed.
                Task.ensure_equipment(exact_map={'cursed_hat': 1}),
                # Task.ensure_equipment(exact_map={'elderwood_staff': 28}),
                # Task.recycle_item('elderwood_staff', keep_quantity=5),
                Task.recycle_item('topaz_amulet', quantity=5),
                Task.recycle_item('piggy_pants', quantity=5),
                Task.recycle_item('dreadful_ring', quantity=10),
                Task.level_skill(
                    skill=CraftSkill.WEAPONCRAFTING, target_level=40, request_support=True, allow_event_parts=True, stock_only=True
                ),
                Task.level_skill(skill=CraftSkill.WEAPONCRAFTING, target_level=40, request_support=True, allow_event_parts=True),
                Task.ensure_equipment(exact_map={'malefic_armor': 1, 'corrupted_stone_amulet': 1}),
                Task.ensure_equipment(exact_map={'bloodblade': 1, 'cursed_hat': 1, 'corrupted_stone_amulet': 1}),
                Task.ensure_equipment(exact_map={'conjurer_cloak': 4, 'conjurer_skirt': 4, 'gold_ring': 10}),
                Task.ensure_equipment(exact_map={'malefic_ring': 2, 'malefic_crystal': 1}),
                Task.ensure_equipment(exact_map={'stormforged_armor': 2}),
                Task.ensure_equipment(exact_map={'wisdom_amulet': 5}),
                # required for wisdom value. Item is level 15, don't recycle!
                Task.ensure_equipment(exact_map={'wrathpants': 2}),
                # Monster goblin_wolfrider (40) can now be killed.
                Task.level_skill(skill=CraftSkill.GEARCRAFTING, target_level=40, request_support=True, allow_event_parts=True),
                Task.ensure_equipment(
                    exact_map={
                        'mithril_sword': 1,
                        'gold_shield': 1,
                        'jester_hat': 1,
                        'dreadful_armor': 1,
                        'mithril_platelegs': 1,
                        'lizard_boots': 1,
                        'greater_dreadful_amulet': 1,
                        'sapphire_ring': 2,
                        'burn_rune': 1,
                        'perfect_pearl': 1,
                        'life_crystal': 1,
                        'lost_world_map': 1,
                        # 'air_boost_potion': 1,
                        # 'minor_health_potion': 5,
                    }
                ),
                # Monster bat (38) can now be killed.
                Task.ensure_equipment(
                    exact_map={
                        'white_knight_pants': 1,
                        'mithril_sword': 1,
                        'gold_shield': 1,
                        'jester_hat': 1,
                        'mithril_platebody': 1,
                        'mithril_platelegs': 1,
                        'lizard_boots': 1,
                        'prospecting_amulet': 1,
                        'malefic_ring': 2,
                        'healing_rune': 1,
                        'perfect_pearl': 1,
                        'life_crystal': 1,
                        'lost_world_map': 1,
                    }
                ),
                # Monster hellhound (40) can now be killed.
                Task.ensure_equipment(
                    exact_map={
                        'bloodblade': 1,
                        'gold_shield': 1,
                        'cursed_hat': 1,
                        'piggy_armor': 1,
                        # 'piggy_pants': 1,
                        'lizard_boots': 1,
                        'lost_amulet': 1,
                        'ruby_ring': 2,
                        'healing_rune': 1,
                        'perfect_pearl': 1,
                        'life_crystal': 1,
                        'lost_world_map': 1,
                        # 'air_boost_potion': 1,
                        # 'minor_health_potion': 9,
                    }
                ),
                # Monster rosenblood (40) can now be killed.
                Task.ensure_equipment(
                    exact_map={
                        'mithril_shield': 1,
                        # 'diamond_amulet': 1,
                        'white_knight_shield': 2,
                        'mithril_platebody': 2,
                        'enchanter_pants': 3,
                        'jester_hat': 2,
                        'mithril_sword': 2,
                        'mithril_platelegs': 2,
                        'sapphire_ring': 6,
                        'gold_axe': 4,
                        'enchanter_boots': 2,
                    }
                ),
                Task.ensure_equipment(  # required to fight Cultist Emperor with 3 characters without consumables
                    exact_map={
                        'mithril_sword': 3,
                        'white_knight_shield': 3,
                        'jester_hat': 3,
                        'mithril_platebody': 3,
                        'mithril_platelegs': 3,
                    }
                ),
                Task.ensure_equipment(  # required to fight Rosenblood with 2 characters
                    exact_map={'bloodblade': 2, 'mithril_shield': 2, 'malefic_armor': 2, 'ruby_ring': 4, 'life_crystal': 2}
                ),
                Task.ensure_equipment(  # required to fight Rosenblood with 3 characters
                    exact_map={'cultist_hat': 1, 'cultist_pants': 2, 'cultist_boots': 1, 'mithril_boots': 1}
                ),
                # Monster grimlet (45) can now be killed.
                # Task.fight_monster(until=Until(achievement_code='loktar_ogar')),
                Task.ensure_equipment(exact_map={'wrathelmet': 1, 'white_knight_armor': 1, 'corrupted_skull': 1}),
                Task.ensure_equipment(exact_map={'batwing_helmet': 1}),
                Task.ensure_equipment(exact_map={'fire_shield': 2, 'malefic_armor': 4, 'mithril_boots': 2}),
                # Task.gather_recipe(item='cooked_hellhound_meat', global_max=50),
                # Task.ensure_item('cursed_plank', 2),
                # Task.level_skill(skill=CraftSkill.JEWELRYCRAFTING, target_level=40, request_support=True, allow_event_parts=True),
                Task.level_crafting_skill(skill=CraftSkill.JEWELRYCRAFTING, target_level=40, allow_event_parts=True),
                Task.solve_task(allow_cancellation=True),
                Task.solve_task(allow_cancellation=True),
                Task.solve_task(allow_cancellation=True),
                Task.solve_task(allow_cancellation=True),
                Task.solve_task(allow_cancellation=True),
                Task.solve_task(allow_cancellation=True),
            ]
        )
    elif any(skill_map[skill] < MAX_LEVEL for skill in LEADER_CRAFTING_SKILLS):
        logger.info(f'At least one skill is < {MAX_LEVEL}')
        tasks.extend(
            [
                Task.exchange_task_coins(reward='magical_cure'),
                Task.ensure_equipment(
                    exact_map={
                        'conjurer_cloak': 5,
                        'bow_from_hell': 3,
                        'water_shield': 5,
                        'corrupted_crown': 5,
                        'corrupted_skull': 5,
                    }
                ),
                # Task.recycle_item('masterful_necklace', keep_quantity=5, recraft=True),
                # Task.recycle_item('corrupted_stone_amulet', keep_quantity=5),
                # Task.ensure_equipment(exact_map={'corrupted_stone_amulet': 13}),
                Task.solve_task(allow_cancellation=True),
                Task.solve_task(allow_cancellation=True),
                Task.solve_task(allow_cancellation=True),
                Task.solve_task(allow_cancellation=True),
                Task.solve_task(allow_cancellation=True),
                Task.solve_task(allow_cancellation=True),
                Task.solve_task(allow_cancellation=True),
            ]
        )
    else:
        logger.info(f'All skills are at max level ({MAX_LEVEL})')
        tasks.extend(
            [
                Task.exchange_task_coins(),
                Task.ensure_equipment(exact_map={'hell_ring': 10}),
                Task.solve_task(allow_cancellation=True),
                Task.solve_task(allow_cancellation=True),
                Task.solve_task(allow_cancellation=True),
                Task.solve_task(allow_cancellation=True),
                Task.solve_task(allow_cancellation=True),
                Task.solve_task(allow_cancellation=True),
                Task.solve_task(allow_cancellation=True),
                Task.solve_task(allow_cancellation=True),
            ]
        )
    return {character_name: tasks}
