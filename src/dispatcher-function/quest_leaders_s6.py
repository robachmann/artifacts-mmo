from datetime import timedelta
from typing import Dict, List

from artifactsmmo.game_constants import LEADER_CRAFTING_SKILLS, MAX_LEVEL
from artifactsmmo.log.logger import logger
from artifactsmmo.models import CraftSkill, GatheringSkill
from artifactsmmo.service.helpers import character_1_name, character_2_name, character_3_name, character_4_name, character_5_name
from artifactsmmo.service.tasks import Task
from artifactsmmo.service.until import Until


def get_quest_join_exclusions() -> List[str]:
    return [
        character_1_name(),
        # character_2_name(),
        character_3_name(),
        character_4_name(),
        character_5_name(),
    ]


def get_quest_join_exclusion_map() -> Dict[str, List[str]]:
    return {
        character_1_name(): [
            character_2_name(),
            character_3_name(),
            character_4_name(),
            character_5_name(),
        ],
        character_2_name(): [
            character_1_name(),
            character_3_name(),
            character_4_name(),
            character_5_name(),
        ],
        character_3_name(): [
            character_1_name(),
            character_2_name(),
            character_4_name(),
            character_5_name(),
        ],
        character_4_name(): [
            # character_1_name(),
            character_2_name(),
            # character_3_name(),
            # character_5_name(),
        ],
        character_5_name(): [
            character_1_name(),
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
        tasks.extend(
            [
                Task.ensure_equipment(exact_map={'wooden_staff': 5}),
                Task.ensure_equipment(exact_map={'copper_pickaxe': 3}),
                Task.ensure_equipment(exact_map={'copper_axe': 3}),
                Task.ensure_equipment(exact_map={'fishing_net': 1}),
                Task.ensure_equipment(
                    exact_map={
                        'copper_dagger': 4,
                        'wooden_shield': 4,
                        'copper_helmet': 4,
                        'copper_boots': 5,
                        'copper_ring': 8,
                    }
                ),
                # Monster chicken (1) can now be killed.
                Task.ensure_equipment(exact_map={'apprentice_gloves': 1}),
                # Monster yellow_slime (2) can now be killed.
                # Task.level_fight(target_level=5),
                # Monster green_slime (4) can now be killed.
                Task.level_skill(skill=CraftSkill.WEAPONCRAFTING, target_level=5, request_support=True),
                Task.level_skill(skill=CraftSkill.GEARCRAFTING, target_level=5, request_support=True),
                # Task.solve_task(),
                # Task.solve_task(),
                # Task.solve_task(),
                # Task.solve_task(),
                Task.ensure_equipment(exact_map={'sticky_dagger': 4, 'feather_coat': 4, 'copper_legs_armor': 4}),
                # Monster sheep (5) can now be killed.
                Task.ensure_equipment(exact_map={'sticky_sword': 3, 'copper_armor': 3}),
                # Monster blue_slime (6) can now be killed.
                Task.ensure_equipment(exact_map={'water_bow': 3}),
                # Monster red_slime (7) can now be killed.
                Task.level_skill(skill=CraftSkill.GEARCRAFTING, target_level=10, request_support=True),
                Task.level_skill(skill=CraftSkill.JEWELRYCRAFTING, target_level=5, request_support=True),
                Task.ensure_equipment(exact_map={'iron_shield': 4, 'life_amulet': 4}),
                # Task.solve_task(),
                # Task.solve_task(),
                # Task.solve_task(),
                # Task.solve_task(),
                # Task.solve_task(),
                # Task.solve_task(),
                # Task.solve_task(),
                Task.level_fight(target_level=10),
                # Monster cow (8) can now be killed.
                Task.level_skill(skill=CraftSkill.WEAPONCRAFTING, target_level=10, request_support=True),
                Task.ensure_equipment(
                    exact_map={'iron_dagger': 4, 'leather_hat': 4, 'leather_armor': 4, 'leather_legs_armor': 4, 'iron_boots': 4}
                ),
                # Monster mushmush (10) can now be killed.
                Task.ensure_equipment(exact_map={'iron_pickaxe': 2}),
                Task.ensure_equipment(exact_map={'iron_axe': 2}),
                Task.ensure_equipment(exact_map={'spruce_fishing_rod': 1}),
                Task.ensure_equipment(exact_map={'leather_gloves': 1}),
                Task.ensure_equipment(exact_map={'greater_wooden_staff': 4, 'forest_ring': 2}),
                # Monster flying_snake (12) can now be killed.
                Task.ensure_equipment(exact_map={'iron_sword': 4, 'iron_armor': 4, 'iron_legs_armor': 4}),
                # Monster wolf (15) can now be killed.
                # Monster highwayman (15) can now be killed.
                Task.level_skill(skill=CraftSkill.WEAPONCRAFTING, target_level=15, request_support=True),
                Task.level_skill(skill=CraftSkill.GEARCRAFTING, target_level=15, request_support=True),
                Task.ensure_equipment(exact_map={'mushstaff': 1, 'mushmush_wizard_hat': 4, 'mushmush_jacket': 4, 'adventurer_pants': 4}),
                Task.ensure_equipment(exact_map={'adventurer_boots': 1, 'adventurer_vest': 1}),
                # Task.solve_task(),
                # Task.solve_task(),
                # Task.solve_task(),
                # Task.solve_task(),
                Task.level_fight(target_level=15),
                # Monster pig (19) can now be killed.
                Task.level_skill(skill=CraftSkill.JEWELRYCRAFTING, target_level=10, request_support=True),
                Task.ensure_equipment(exact_map={'air_and_water_amulet': 3}),
                Task.level_skill(skill=CraftSkill.JEWELRYCRAFTING, target_level=15, request_support=True),
            ]
        )
    elif any(skill_map[skill] < 20 for skill in LEADER_CRAFTING_SKILLS):
        logger.info('At least one skill is < 20')
        tasks.extend(
            [
                Task.ensure_equipment(exact_map={'life_ring': 2, 'wisdom_amulet': 1}),
                Task.level_skill(skill=CraftSkill.WEAPONCRAFTING, target_level=20, request_support=True),
                Task.level_skill(skill=CraftSkill.GEARCRAFTING, target_level=20, request_support=True),
                Task.ensure_equipment(exact_map={'battlestaff': 3, 'hard_leather_helmet': 3, 'air_and_water_amulet': 3, 'healing_aura_rune': 3}),
                Task.level_fight(target_level=20),
                # Task.solve_task(),
                # Task.solve_task(),
                # Monster king_slime (15) can now be killed.
                # Task.fight_boss_monster('king_slime', [character_2_name(), character_3_name()], 10),
                Task.level_skill(skill=CraftSkill.JEWELRYCRAFTING, target_level=20, request_support=True),
            ]
        )
    elif any(skill_map[skill] < 30 for skill in LEADER_CRAFTING_SKILLS):
        logger.info('At least one skill is < 30')
        # against King Slime:
        # {
        #     'weapon': 'battlestaff',
        #     'shield': 'iron_shield',
        #     'helmet': 'hard_leather_helmet',
        #     'body_armor': 'mushmush_jacket',
        #     'leg_armor': 'leather_legs_armor',
        #     'boots': 'hard_leather_boots',
        #     'amulet': 'air_and_water_amulet',
        #     'ring1': 'water_ring',
        #     'ring2': 'water_ring',
        #     'artifact1': 'perfect_pearl',
        #     'artifact2': 'lost_world_map',
        #     'rune': 'healing_aura_rune',
        # }
        tasks.extend(
            [
                Task.recycle_item('copper_axe', keep_quantity=0),
                Task.recycle_item('iron_dagger', keep_quantity=0),
                Task.recycle_item('greater_wooden_staff', keep_quantity=0),
                Task.recycle_item('leather_legs_armor', keep_quantity=0),
                Task.recycle_item('copper_boots', keep_quantity=0),
                Task.recycle_item('leather_boots', keep_quantity=0),
                Task.recycle_item('leather_armor', keep_quantity=0),
                Task.recycle_item('air_and_water_amulet', keep_quantity=0),
                # Task.fight_boss_monster('king_slime', [character_2_name(), character_3_name()], 400),
                Task.ensure_equipment(
                    exact_map={
                        'skull_staff': 4,
                        'slime_shield': 4,
                        'tromatising_mask': 4,
                        'skeleton_armor': 4,
                        'skeleton_pants': 4,
                        #    'leather_boots': 4,
                        'skull_amulet': 4,
                        'skull_ring': 2,
                    }
                ),
                # Monster ogre (20) can now be killed.
                Task.ensure_equipment(exact_map={'steel_fishing_rod': 1, 'steel_axe': 2}),
                Task.ensure_equipment(exact_map={'magic_wizard_hat': 4, 'steel_legs_armor': 4, 'dreadful_amulet': 4, 'ring_of_chance': 2}),
                # Monster spider (20) can now be killed.
                Task.ensure_equipment(exact_map={'steel_pickaxe': 2}),
                Task.ensure_equipment(exact_map={'hard_leather_armor': 4, 'snakeskin_boots': 4}),
                Task.ensure_equipment(exact_map={'steel_battleaxe': 2, 'hard_leather_armor': 1, 'hard_leather_pants': 2, 'ring_of_chance': 4}),
                Task.ensure_equipment(exact_map={'steel_armor': 4}),
                # Monster vampire (24) can now be killed.
                Task.level_skill(skill=CraftSkill.GEARCRAFTING, target_level=25, request_support=True),
                Task.ensure_equipment(
                    exact_map={
                        'snakeskin_armor': 1,
                        'wisdom_amulet': 2,
                        'piggy_pants': 1,
                        'steel_boots': 4,
                        'satchel': 5,
                    }
                ),
                Task.level_fight(target_level=25),
                # Monster cyclops (25) can now be killed.
                Task.level_skill(skill=CraftSkill.WEAPONCRAFTING, target_level=25, request_support=True),
                Task.ensure_equipment(exact_map={'skull_wand': 1, 'snakeskin_legs_armor': 4}),
                # Monster corrupted_ogre (20) can now be killed.
                # Requires woodcutting level 30
                Task.level_gathering_skill(GatheringSkill.WOODCUTTING, 30),
                # Task.fight_boss_monster('king_slime', [character_2_name(), character_3_name()], 100),
                Task.ensure_equipment(exact_map={'piggy_armor': 1, 'hard_leather_boots': 4}),
                Task.ensure_equipment(exact_map={'piggy_helmet': 4}),
                Task.ensure_equipment(
                    exact_map={
                        'skull_wand': 2,
                        'healing_rune': 2,
                        'piggy_pants': 2,
                    }
                ),
                Task.ensure_equipment(exact_map={'fire_ring': 2}),
                Task.ensure_equipment(exact_map={'death_knight_sword': 1}),
                # Task.ensure_equipment(exact_map={'skull_ring': 4}),
                Task.level_skill(skill=CraftSkill.JEWELRYCRAFTING, target_level=25, request_support=True),
                Task.ensure_equipment(exact_map={'ruby_amulet': 1}),
                Task.level_skill(skill=CraftSkill.WEAPONCRAFTING, target_level=30, request_support=True),
                Task.ensure_equipment(exact_map={'gold_axe': 2, 'gold_pickaxe': 2, 'gold_fishing_rod': 1}),
                Task.ensure_equipment(exact_map={'ring_of_chance': 6}),
                Task.ensure_equipment(
                    exact_map={
                        'old_boots': 5,
                        'wolf_ears': 5,
                        'snakeskin_armor': 5,
                        'piggy_armor': 5,
                        'steel_ring': 8,
                        'adventurer_pants': 5,
                        'wisdom_amulet': 5,
                    }
                ),
                # Task.solve_task(),
                Task.ensure_equipment(exact_map={'death_knight_sword': 2}),
                Task.level_skill(skill=CraftSkill.GEARCRAFTING, target_level=30, request_support=True),
                Task.ensure_equipment(exact_map={'conjurer_skirt': 1, 'conjurer_cloak': 1}),
                Task.level_skill(skill=CraftSkill.JEWELRYCRAFTING, target_level=30, request_support=True),
            ]
        )
    elif any(skill_map[skill] < 40 for skill in LEADER_CRAFTING_SKILLS):
        logger.info('At least one skill is < 40')
        tasks.extend(
            [
                # Get rid of all level <30 gear:
                Task.recycle_item(
                    keep_map={
                        'forest_whip': 0,
                        'skull_wand': 0,
                        'skeleton_pants': 0,
                        'snakeskin_legs_armor': 0,
                        'piggy_pants': 0,
                        'lizard_skin_legs_armor': 0,
                        'tromatising_mask': 0,
                        'hard_leather_helmet': 0,
                        'piggy_helmet': 0,
                        'snakeskin_armor': 0,
                        'piggy_armor': 0,
                        'lizard_skin_armor': 0,
                        'skull_amulet': 0,
                        'mushmush_jacket': 0,
                        'skeleton_armor': 0,
                        'skeleton_helmet': 0,
                        'magic_wizard_hat': 0,
                        'steel_boots': 0,
                        'slime_shield': 0,
                        'ring_of_chance': 2,
                        'steel_battleaxe': 0,
                        'skull_staff': 0,
                        'battlestaff': 0,
                        #'steel_ring': 10,  # needed for wisdom?
                        'skull_ring': 0,
                        'steel_legs_armor': 0,
                        'hard_leather_pants': 0,
                        #'wolf_ears': 5,  # needed for wisdom?
                        'snakeskin_boots': 0,
                        'hard_leather_boots': 0,
                        #'old_boots': 5,  # needed for wisdom?
                        'steel_armor': 0,
                        'hard_leather_armor': 0,
                        'dreadful_amulet': 0,
                        'gold_pickaxe': 2,
                    }
                ),
                # Task.fight_boss_monster('lich', [character_5_name(), character_3_name()], 31),
                # Task.solve_recycling_achievements(),
                # Task.ensure_equipment(
                #     exact_map={
                #         'gold_pickaxe': 4,
                #         'gold_axe': 3,
                #         'adventurer_vest': 1,
                #         'gold_platebody': 3,
                #         'enchanter_pants': 3,
                #         'greater_dreadful_amulet': 3,
                #         'jester_hat': 3,
                #         'lizard_boots': 2,
                #     }
                # ),
                # # Task.fight_boss_monster('lich', [character_3_name(), character_2_name()], 200),
                # # Task.ensure_equipment(
                # #     exact_map={
                # #         'gold_platebody': 1,
                # #         'enchanter_pants': 1,
                # #         'greater_dreadful_amulet': 2,
                # #         'royal_skeleton_ring': 6,
                # #         'protection_rune': 1,
                # #     }
                # # ),
                # # Task.upgrade_basic_parts(CraftSkill.MINING),
                # Task.ensure_equipment(
                #     exact_map={
                #         'conjurer_skirt': 3,
                #         'conjurer_cloak': 3,
                #         'obsidian_helmet': 3,
                #         'flying_boots': 3,
                #         # 'ruby_amulet': 2, # requires another jasper_crystal
                #         'ruby_ring': 4,
                #     }
                # ),
                # # Task.recycle_item('fire_and_earth_amulet', keep_quantity=0),
                # Task.ensure_equipment(
                #     exact_map={
                #         'elderwood_staff': 1,
                #         'gold_shield': 1,
                #         'obsidian_helmet': 1,
                #         'bandit_armor': 1,
                #         'royal_skeleton_pants': 1,
                #         'gold_boots': 1,
                #         'prospecting_amulet': 1,
                #         'royal_skeleton_ring': 2,
                #         'healing_rune': 1,
                #     }
                # ),
                # Task.ensure_equipment(
                #     exact_map={
                #         'elderwood_staff': 4,
                #         'gold_sword': 4,
                #         'enchanted_bow': 4,
                #         'greater_dreadful_staff': 2,
                #         'gold_platelegs': 2,
                #         'lizard_boots': 2,
                #     }
                # ),
                # Task.ensure_equipment(exact_map={'ruby_ring': 2, 'gold_shield': 3}),
                # Task.level_skill(skill=CraftSkill.WEAPONCRAFTING, target_level=35, request_support=True, allow_event_parts=True),
                # Task.ensure_equipment(exact_map={'magic_bow': 1, 'gold_mask': 1, 'lost_amulet': 1, 'emerald_ring': 2, 'prospecting_amulet': 4}),
                # Task.ensure_equipment(exact_map={'dreadful_battleaxe': 2}),
                # Task.ensure_equipment(
                #     exact_map={
                #         'lizard_skin_legs_armor': 1,
                #         'flying_boots': 1,
                #         'sapphire_ring': 2,
                #         'obsidian_legs_armor': 1,
                #         'greater_dreadful_amulet': 1,
                #     }
                # ),
                # Task.level_skill(skill=CraftSkill.GEARCRAFTING, target_level=35, request_support=True),
                # Task.level_gathering_skill(GatheringSkill.MINING, 35),
                # Task.ensure_equipment(
                #     exact_map={
                #         'jester_hat': 1,
                #         'strangold_legs_armor': 3,
                #         'gold_boots': 3,
                #     }
                # ),
                # Task.level_skill(skill=CraftSkill.JEWELRYCRAFTING, target_level=35, request_support=True, allow_event_parts=True),
                # Task.ensure_equipment(
                #     exact_map={
                #         'obsidian_battleaxe': 1,
                #         'dreadful_shield': 1,
                #         'stormforged_armor': 1,
                #         'ancient_jean': 1,
                #         'enchanter_boots': 1,
                #         'masterful_necklace': 1,
                #         'malefic_ring': 2,
                #     }
                # ),
                # Task.level_skill(skill=CraftSkill.WEAPONCRAFTING, target_level=40, request_support=True, allow_event_parts=True),
                # Task.ensure_equipment(
                #     exact_map={
                #         'golden_gloves': 1,
                #         'gold_helm': 1,
                #         'bloodblade': 1,
                #     }
                # ),
                Task.ensure_equipment(
                    exact_map={
                        'mithril_sword': 1,
                        'lightning_sword': 1,
                        'wrathsword': 1,
                        'prospecting_amulet': 5,
                        'mithril_shield': 3,
                    }
                ),
                Task.level_skill(skill=CraftSkill.GEARCRAFTING, target_level=40, request_support=True, allow_event_parts=True),
                Task.ensure_equipment(exact_map={'cultist_cloak': 3}),
                Task.ensure_equipment(exact_map={'mithril_platelegs': 1, 'cultist_boots': 1, 'cultist_hat': 1}),
                Task.ensure_equipment(
                    exact_map={
                        'mithril_pickaxe': 3,
                        'mithril_axe': 2,
                        'mithril_fishing_rod': 1,
                    }
                ),
                Task.ensure_equipment(
                    exact_map={
                        'mithril_shield': 1,
                        'white_knight_armor': 1,
                    }
                ),
                # Task.ensure_equipment(
                #     exact_map={
                #         'dreadful_battleaxe': 3,
                #         'gold_shield': 3,
                #         'jester_hat': 3,  ## vs. hard_leather_helmet
                #         'lizard_skin_armor': 3,
                #         'strangold_legs_armor': 3,  ## or enchanter_pants
                #         'lizard_boots': 3,  ## or hard_leather_boots
                #         'sapphire_amulet': 3,  ## better than prospecting_amulet
                #         'sapphire_ring': 6,
                #         'healing_aura_rune': 3,
                #         #'water_boost_potion': 3,
                #         #'health_potion': 60,
                #         # 'level': 35,
                #         # 'weapon_slot': 'dreadful_battleaxe',
                #         # 'helmet_slot': 'jester_hat',
                #         # 'body_armor_slot': 'lizard_skin_armor',
                #         # 'leg_armor_slot': 'strangold_legs_armor',
                #         # 'boots_slot': 'lizard_boots',
                #         # 'shield_slot': 'gold_shield',
                #         # 'ring1_slot': 'sapphire_ring',
                #         # 'ring2_slot': 'sapphire_ring',
                #         # 'amulet_slot': 'sapphire_amulet',
                #         # 'artifact1_slot': '',
                #         # 'artifact2_slot': '',
                #         # 'artifact3_slot': '',
                #         # 'rune_slot': 'healing_aura_rune',
                #         # 'utility1_slot': 'water_boost_potion',
                #         # 'utility1_slot_quantity': 1,
                #         # 'utility2_slot': 'health_potion',
                #         # 'utility2_slot_quantity': 20,
                #     }
                # ),
                Task.level_skill(skill=CraftSkill.JEWELRYCRAFTING, target_level=40, request_support=True, allow_event_parts=True),
            ]
        )
    elif any(skill_map[skill] < MAX_LEVEL for skill in LEADER_CRAFTING_SKILLS):
        logger.info(f'At least one skill is < {MAX_LEVEL}')
        tasks.extend(
            [
                # Task.fight_boss_monster(
                #    'rosenblood', [character_2_name(), character_3_name()], until=Until(drop_item='elemental_page', drop_count=90)
                # ),
                # Task.fight_boss_monster('duskworm', [character_2_name(), character_3_name()], 300, map_id=1238),
                # Task.upgrade_basic_parts(CraftSkill.WOODCUTTING, include_items=['dead_wood_plank']),
                # Task.upgrade_basic_parts(CraftSkill.MINING),
                # Task.solve_recycling_achievements(gather_parts=False),
                # Task.recycle_item(keep_map={'steel_fishing_rod': 0}),
                # Task.ensure_equipment(
                #     exact_map={
                #         'white_knight_pants': 1,
                #         'greater_ruby_amulet': 1,
                #         'darkforged_plate': 1,
                #         'hell_reaper': 1,
                #         'greater_sapphire_amulet': 1,
                #         'darkforged_helmet': 1,
                #         'bow_from_hell': 1,
                #         'malefic_armor': 3,
                #         'blade_of_hell': 1,
                #         'sand_snakeskin_bandana': 1,
                #         'sand_snakeskin_pants': 1,
                #         'sand_snakeskin_armor': 1,
                #         'sand_snakeskin_boots': 1,
                #         'darkforged_boots': 1,
                #         'mithril_boots': 1,
                #         'adamantite_shield': 1,
                #         'dark_horned_helmet': 1,
                #         'vital_armor': 1,
                #         'hell_staff': 1,
                #         'earth_shield': 1,
                #     }
                # ),
                # Task.ensure_equipment(exact_map={'duskarmor': 1, 'duskpants': 1, 'sapphire_book': 1}),
                # Task.send_message('Scorpion can now be killed with enough earth_res_potion.'),
                # Task.ensure_equipment(exact_map={'magic_shield': 1, 'skullforged_pants': 1, 'skullforged_armor': 1}),
                # Task.level_skill(skill=CraftSkill.WEAPONCRAFTING, target_level=50, request_support=True, allow_event_parts=True),
                # against sandwarden
                Task.ensure_equipment(exact_map={'adamantite_boots': 1}),
                # Task.send_message('Sandwarden can now be killed with enough earth_boost_potion.'),
                Task.level_skill(
                    skill=CraftSkill.JEWELRYCRAFTING,
                    target_level=50,
                    request_support=True,
                    allow_event_parts=True,
                    item='mithril_ring',
                ),
            ]
        )
    else:
        # logger.info(f'All skills are at max level ({MAX_LEVEL})')
        tasks.extend(
            [
                # Task.fight_boss_monster(
                #     'rosenblood', [character_2_name(), character_5_name()], until=Until(drop_item='elemental_page', drop_count=30)
                # ),
                # Task.ensure_equipment(exact_map={'christmas_stocking': 5}),
                Task.ensure_equipment(
                    exact_map={
                        'christmas_star': 5,
                        'sandwhisper_bag': 4,
                        'christmas_cane': 5,
                        'eternal_red_ring': 4,
                        'topaz_book': 3,
                        'adamantite_gloves': 3,
                        'adamantite_fishing_rod': 3,
                        'adamantite_pickaxe': 3,
                        'adamantite_axe': 3,
                        'moonlight_staff': 3,
                        'dust_sword': 3,
                        'adamantite_sword': 3,
                        'desert_whip': 5,
                    }
                ),
                # Task.exchange_currency(item='small_bag_of_gold', currency='gift'),
                Task.ensure_equipment(  # against krampus
                    exact_map={
                        'dust_sword': 3,
                        'water_shield': 3,
                        'dust_helmet': 3,
                        'dreadful_armor': 3,
                        'duskpants': 3,
                        'sand_snakeskin_boots': 3,
                        'dust_amulet': 3,
                        'mithril_ring': 6,
                        'sandwhisper_codex': 1,
                        'ruby_book': 3,
                        'life_crystal': 3,
                        'greater_healing_rune': 3,
                        'corrupted_skull': 2,
                    }
                ),
                # Task.fight_monster('nutcracker', until=Until(timespan=timedelta(days=7))),
                Task.solve_task(),
                # Task.fight_monster('desert_scorpion', until=Until(drop_count=50, drop_item='desert_scorpion_meat')),
                # Task.ensure_equipment(exact_map={'dust_amulet': 1}),
                # Task.ensure_equipment(exact_map={'vital_boots': 1}),
                # Task.ensure_equipment(  # against empress (alternative)
                #     exact_map={
                #         'dust_helmet': 1,
                #         'desert_whip': 3,  # 0 missing
                #         'adamantite_shield': 3,  # 0 missing
                #         'desert_wrap': 3,  # 0 missing
                #         'skullforged_armor': 3,  # 0 missing
                #         'skullforged_pants': 3,  # 0 missing # requires 6 adventurer skulls
                #         'adamantite_boots': 3,  # 0 missing
                #         'heart_amulet': 3,  # 0 missing
                #         'mithril_ring': 6,  # 0 missing
                #         'topaz_book': 2,  # 0 missing # better 3, should work with 2
                #         'life_crystal': 3,  # 0 missing
                #         'corrupted_skull': 3,  # 0 missing
                #         'greater_healing_rune': 2,  # 0 missing  # better 3, should work with 2
                #         # 'fire_res_potion': 6,
                #         # 'health_boost_potion': 6,
                #     }
                # ),
                # # Task.send_message('Empress can now be killed.'),
                # Task.solve_tasks_achievements(),
            ]
        )
    return {character_name: tasks}
