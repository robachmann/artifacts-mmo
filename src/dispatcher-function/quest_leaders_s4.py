from typing import Dict, List

from artifactsmmo.models import Skill
from artifactsmmo.service.helpers import character_1_name, character_2_name, character_3_name, character_4_name, character_5_name
from artifactsmmo.service.tasks import Task


def get_quest_join_exclusions() -> List[str]:
    return [character_1_name()]


def get_quest_join_exclusion_map() -> Dict[str, List[str]]:
    return {
        character_1_name(): [
            # character_2_name(),
            # character_3_name(),
            character_4_name(),
            character_5_name(),
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
            # character_2_name(),
            # character_3_name(),
            # character_4_name(),
        ],
    }
    # example to prevent characters 1-4 to join quests of character 5
    # return {character_5_name(): [character_1_name(), character_2_name(), character_3_name(), character_4_name()]}


def get_quest_leaders() -> List[str]:
    return list(quest_leaders().keys())


def quest_leaders() -> Dict[str, List[Task]]:
    character_name = character_1_name()
    tasks: List[Task] = []
    # PHASE 1
    # tasks.extend(craft_item(5, 'wooden_staff', character_name))
    # tasks.extend(craft_item(5, 'copper_dagger', character_name))
    # tasks.extend(craft_item(5, 'copper_boots', character_name))
    # tasks.extend(craft_item(5, 'copper_helmet', character_name))
    # tasks.extend(craft_item(5, 'wooden_shield', character_name))
    # tasks.extend(craft_item(10, 'copper_ring', character_name))
    # tasks.extend(craft_item(5, 'wooden_staff', character_name))
    # tasks.append(Task.level_skill(CraftSkill.GEARCRAFTING, 5))
    # tasks.extend(craft_item(5, 'copper_legs_armor', character_name))
    # tasks.extend(craft_item(5, 'copper_armor', character_name))
    # tasks.extend(craft_item(5, 'feather_coat', character_name))
    # tasks.append(Task.level_skill(CraftSkill.JEWELRYCRAFTING, 5))
    # tasks.append(Task.level_skill(CraftSkill.WEAPONCRAFTING, 5, item='copper_dagger'))
    # tasks.append(Task.level_fight(5))
    # tasks.extend(craft_item(5, 'sticky_sword', character_name))
    # tasks.extend(craft_item(5, 'sticky_dagger', character_name))
    # tasks.extend(craft_item(5, 'water_bow', character_name))
    # tasks.extend(craft_item(5, 'fire_staff', character_name))
    # tasks.extend(craft_item(5, 'life_amulet', character_name))
    # tasks.append(Task.level_fight(10))
    # tasks.append(Task.level_skill(CraftSkill.WEAPONCRAFTING, 10, stock_only=True))
    # tasks.append(Task.level_skill(CraftSkill.WEAPONCRAFTING, 10))
    # tasks.append(Task.level_skill(CraftSkill.MINING, 10, stock_only=True))
    # tasks.append(Task.level_skill(CraftSkill.MINING, 10))
    # tasks.extend(craft_item(5, 'iron_sword', character_name))
    # tasks.extend(craft_item(5, 'iron_dagger', character_name))
    # tasks.append(Task.level_skill(CraftSkill.WOODCUTTING, 10, stock_only=True))
    # tasks.append(Task.level_skill(CraftSkill.WOODCUTTING, 10))
    # tasks.extend(craft_item(5, 'greater_wooden_staff', character_name))
    # tasks.extend(craft_item(5, 'fire_bow', character_name))
    # tasks.append(Task.level_skill(CraftSkill.JEWELRYCRAFTING, 10, stock_only=True))
    # tasks.append(Task.level_skill(CraftSkill.JEWELRYCRAFTING, 10))
    # tasks.extend(craft_item(10, 'iron_ring', character_name))
    # tasks.extend(craft_item(5, 'fire_and_earth_amulet', character_name))
    # tasks.append(Task.level_skill(CraftSkill.GEARCRAFTING, 10, stock_only=True))
    # tasks.append(Task.level_skill(CraftSkill.GEARCRAFTING, 10))
    # tasks.extend(craft_item(5, 'iron_helm', character_name))
    # tasks.extend(craft_item(5, 'iron_boots', character_name))
    # tasks.extend(craft_item(5, 'slime_shield', character_name))  # cow can now be defeated
    # tasks.extend(craft_item(5, 'iron_armor', character_name))
    # tasks.extend(craft_item(5, 'iron_legs_armor', character_name))
    # tasks.extend(craft_item(1, 'spruce_fishing_rod', character_name))
    # tasks.extend(craft_item(5, 'leather_hat', character_name))
    # tasks.extend(craft_item(5, 'leather_armor', character_name))
    # tasks.extend(craft_item(5, 'leather_legs_armor', character_name))
    # tasks.extend(craft_item(5, 'adventurer_vest', character_name))
    # tasks.extend(craft_item(5, 'leather_boots', character_name))
    # tasks.extend(craft_item(5, 'air_and_water_amulet', character_name))
    # tasks.extend(craft_item(5, 'adventurer_helmet', character_name))  # cow can now be defeated most efficiently
    # tasks.append(Task.solve_task(allow_cancellation=True))
    # tasks.append(Task.exchange_task_coins())
    # tasks.append(Task.level_skill(CraftSkill.WEAPONCRAFTING, 15, stock_only=True))
    # tasks.append(Task.level_skill(CraftSkill.WEAPONCRAFTING, 15))
    # tasks.append(Task.level_skill(CraftSkill.GEARCRAFTING, 15, stock_only=True))
    # tasks.append(Task.level_skill(CraftSkill.GEARCRAFTING, 15))
    #
    # PHASE 2
    # tasks.append(Task.recycle_item('life_amulet', 5))
    # tasks.append(Task.recycle_item('sticky_sword', 5))
    # tasks.append(Task.recycle_item('water_bow', 5))
    # tasks.append(Task.recycle_item('sticky_dagger', 5))
    # tasks.append(Task.recycle_item('fire_staff', 5))
    #
    # tasks.extend(craft_item(1, 'iron_pickaxe', character_name))
    # tasks.extend(craft_item(1, 'iron_axe', character_name))
    # tasks.extend(craft_item(1, 'burn_rune', character_name))
    # tasks.append(Task.exchange_task_coins())
    # tasks.append(Task.level_skill(CraftSkill.JEWELRYCRAFTING, 15, stock_only=True))
    # tasks.append(Task.level_skill(CraftSkill.JEWELRYCRAFTING, 15))
    # tasks.extend(craft_item(10, 'earth_ring', character_name))
    # tasks.extend(craft_item(1, 'adventurer_pants', character_name))
    # tasks.extend(craft_item(1, 'adventurer_boots', character_name))
    # tasks.extend(craft_item(2, 'multislimes_sword', character_name))
    # tasks.extend(craft_item(1, 'mushmush_jacket', character_name))
    # tasks.extend(craft_item(5, 'adventurer_pants', character_name))
    # tasks.extend(craft_item(5, 'adventurer_boots', character_name))
    # tasks.extend(craft_item(1, 'highwayman_dagger', character_name))
    # tasks.extend(craft_item(1, 'wolf_ears', character_name))
    # tasks.extend(craft_item(1, 'lifesteal_rune', character_name))
    # tasks.extend(craft_item(2, 'water_ring', character_name))
    # tasks.extend(craft_item(1, 'lucky_wizard_hat', character_name))
    # tasks.extend(craft_item(1, 'mushmush_wizard_hat', character_name))
    # tasks.extend(craft_item(5, 'highwayman_dagger', character_name))
    # tasks.extend(craft_item(5, 'wolf_ears', character_name))
    # tasks.append(Task.level_skill(CraftSkill.WEAPONCRAFTING, 20, stock_only=True))
    # tasks.append(Task.level_skill(CraftSkill.WEAPONCRAFTING, 20))
    # tasks.extend(craft_item(5, 'battlestaff', character_name))
    # tasks.extend(craft_item(5, 'skull_staff', character_name))
    # # tasks.extend(craft_item(5, 'steel_battleaxe', character_name))
    # tasks.append(Task.level_skill(CraftSkill.GEARCRAFTING, 20, stock_only=True))
    # tasks.append(Task.level_skill(CraftSkill.GEARCRAFTING, 20))
    # tasks.extend(craft_item(5, 'skeleton_pants', character_name))
    # # tasks.extend(craft_item(5, 'steel_legs_armor', character_name))
    # # tasks.extend(craft_item(5, 'steel_shield', character_name))
    # # tasks.extend(craft_item(5, 'steel_helm', character_name))
    # # tasks.extend(craft_item(5, 'steel_armor', character_name))
    # # tasks.extend(craft_item(5, 'serpent_skin_boots', character_name))
    # tasks.append(Task.level_skill(CraftSkill.JEWELRYCRAFTING, 20, stock_only=True))
    # tasks.append(Task.level_skill(CraftSkill.JEWELRYCRAFTING, 20))
    # tasks.extend(craft_item(5, 'skull_amulet', character_name))
    # tasks.extend(craft_item(2, 'skull_ring', character_name))
    # tasks.extend(craft_item(10, 'steel_ring', character_name))
    # tasks.extend(craft_item(5, 'tromatising_mask', character_name))
    # tasks.extend(craft_item(5, 'skeleton_armor', character_name))
    # tasks.extend(craft_item(2, 'ring_of_chance', character_name))
    # tasks.extend(craft_item(5, 'steel_shield', character_name))
    # tasks.extend(craft_item(5, 'magic_wizard_hat', character_name))
    # tasks.extend(craft_item(5, 'steel_legs_armor', character_name))
    # tasks.extend(craft_item(5, 'dreadful_amulet', character_name))
    # tasks.extend(craft_item(5, 'steel_boots', character_name))
    # tasks.extend(craft_item(1, 'healing_rune', character_name))
    #
    # # for bandit_lizard:
    # tasks.append(Task.level_skill(CraftSkill.GEARCRAFTING, 25, stock_only=True))
    # tasks.append(Task.level_skill(CraftSkill.GEARCRAFTING, 25))
    # tasks.extend(craft_item(1, 'piggy_armor', character_name))
    # tasks.extend(craft_item(1, 'piggy_pants', character_name))
    # tasks.append(Task.level_skill(CraftSkill.JEWELRYCRAFTING, 25, stock_only=True))
    # tasks.append(Task.level_skill(CraftSkill.JEWELRYCRAFTING, 25, item='skull_amulet'))
    # tasks.append(Task.level_skill(CraftSkill.JEWELRYCRAFTING, 25))
    # tasks.extend(craft_item(1, 'ruby_amulet', character_name))
    # # tasks.append(Task.send_message('👾 Bandit Lizard can now be defeated.'))
    #
    # tasks.extend(craft_item(2, 'iron_axe', character_name))
    # tasks.extend(craft_item(2, 'iron_pickaxe', character_name))
    # tasks.extend(craft_item(2, 'spruce_fishing_rod', character_name))
    #
    # # tasks.append(Task.solve_task(allow_cancellation=True))
    #
    # # requires spider parts
    # tasks.extend(craft_item(2, 'mushmush_jacket', character_name))
    # tasks.extend(craft_item(1, 'steel_armor', character_name))
    # tasks.extend(craft_item(1, 'serpent_skin_boots', character_name))
    # tasks.extend(craft_item(5, 'steel_armor', character_name))
    # tasks.extend(craft_item(5, 'serpent_skin_boots', character_name))

    # road to lich
    # tasks.extend(craft_item(1, 'steel_helm', character_name))
    # tasks.extend(craft_item(1, 'stormforged_armor', character_name))
    # tasks.extend(craft_item(4, 'ring_of_chance', character_name))
    # tasks.extend(craft_item(2, 'piggy_armor', character_name))

    # tasks.append(Task.recycle_item('iron_sword', 5))

    # tasks.append(Task.recycle_item('greater_wooden_staff', 5))
    # tasks.append(Task.recycle_item('iron_dagger', 5))
    # tasks.append(Task.recycle_item('iron_ring', 10))
    # tasks.append(Task.recycle_item('adventurer_helmet', 5))
    # tasks.append(Task.recycle_item('leather_boots', 5))
    # tasks.append(Task.recycle_item('iron_boots', 5))
    # tasks.append(Task.recycle_item('slime_shield', 5))

    #
    # # tasks.extend(craft_item(2, 'piggy_pants', character_name))
    # # tasks.extend(craft_item(2, 'ruby_amulet', character_name))
    # # tasks.append(Task.send_message('👾 Bandit Lizard can now be defeated by two characters.'))
    # # tasks.extend(craft_item(1, 'iron_dagger', character_name))
    # tasks.extend(craft_item(2, 'burn_rune', character_name))
    # tasks.extend(craft_item(5, 'piggy_helmet', character_name))
    #
    # tasks.extend(craft_item(3, 'death_knight_sword', character_name))
    # tasks.extend(craft_item(3, 'burn_rune', character_name))

    #
    # tasks.append(Task.level_skill(CraftSkill.GEARCRAFTING, 30, stock_only=True))
    # tasks.append(Task.level_skill(CraftSkill.GEARCRAFTING, 30))
    # tasks.extend(craft_item(5, 'gold_shield', character_name))
    # tasks.extend(craft_item(5, 'gold_platelegs', character_name))
    # tasks.extend(craft_item(5, 'gold_boots', character_name))
    # tasks.extend(craft_item(5, 'royal_skeleton_pants', character_name))
    # tasks.extend(craft_item(5, 'royal_skeleton_helmet', character_name))
    # tasks.extend(craft_item(5, 'gold_mask', character_name))
    # tasks.extend(craft_item(1, 'obsidian_helmet', character_name))
    # tasks.extend(craft_item(1, 'conjurer_skirt', character_name))
    # tasks.append(Task.fight_monster(monster='lich', ttl=10))
    # tasks.append(Task.level_skill(CraftSkill.JEWELRYCRAFTING, 30, stock_only=True))
    # tasks.append(Task.level_skill(CraftSkill.JEWELRYCRAFTING, 30))
    # tasks.extend(craft_item(2, 'topaz_ring', character_name))
    # tasks.extend(craft_item(2, 'prospecting_amulet', character_name))
    # tasks.extend(craft_item(2, 'greater_dreadful_amulet', character_name))
    # tasks.extend(craft_item(2, 'lost_amulet', character_name))
    # tasks.extend(craft_item(2, 'steel_shield', character_name))
    #
    # tasks.append(Task.level_skill(CraftSkill.WEAPONCRAFTING, 30, stock_only=True))
    # tasks.append(Task.level_skill(CraftSkill.WEAPONCRAFTING, 30))
    # tasks.extend(craft_item(5, 'gold_sword', character_name))
    # tasks.extend(craft_item(2, 'gold_axe', character_name))
    # tasks.extend(craft_item(2, 'gold_pickaxe', character_name))
    # tasks.extend(craft_item(1, 'golden_gloves', character_name))
    # tasks.extend(craft_item(5, 'enchanted_bow', character_name))

    # tasks.extend(craft_item(1, 'obsidian_battleaxe', character_name))
    # # tasks.append(Task.send_message('👾 Lich can now be defeated by one character.'))
    # tasks.extend(craft_item(2, 'gold_platelegs', character_name))
    # tasks.extend(craft_item(4, 'topaz_ring', character_name))
    # tasks.extend(craft_item(2, 'greater_dreadful_amulet', character_name))
    # tasks.extend(craft_item(2, 'obsidian_battleaxe', character_name))
    # # tasks.append(Task.send_message('👾 Lich can now be defeated by two characters.'))
    # tasks.extend(craft_item(2, 'gold_fishing_rod', character_name))
    # tasks.extend(craft_item(1, 'elderwood_staff', character_name))
    # tasks.extend(craft_item(5, 'elderwood_staff', character_name))

    # tasks.append(Task.recycle_item('fire_and_earth_amulet', 5))
    # tasks.append(Task.recycle_item('leather_armor', 5))
    # tasks.append(Task.recycle_item('mushmush_wizard_hat', 5))
    # tasks.append(Task.recycle_item('lucky_wizard_hat', 5))

    #
    # tasks.append(Task.level_skill(CraftSkill.GEARCRAFTING, 35, stock_only=True))
    # tasks.append(Task.level_skill(CraftSkill.GEARCRAFTING, 35, item='gold_platelegs'))
    #
    # tasks.append(Task.ensure_item(item='enchanter_pants', global_max=1))
    # tasks.append(Task.ensure_item(item='lizard_skin_armor', global_max=1))
    # tasks.append(Task.ensure_item(item='greater_dreadful_staff', global_max=1))
    # tasks.append(Task.ensure_item(item='jester_hat', global_max=1))
    # tasks.append(Task.ensure_item(item='strangold_legs_armor', global_max=1))
    # tasks.append(Task.ensure_item(item='gold_platebody', global_max=1))
    # tasks.append(Task.ensure_item(item='lizard_boots', global_max=1))
    # tasks.append(Task.ensure_item(item='sapphire_ring', global_max=2))
    #
    # tasks.append(Task.ensure_item(item='enchanter_boots', global_max=1))
    # tasks.append(Task.ensure_item(item='malefic_armor', global_max=1))
    #
    # tasks.append(Task.ensure_item(item='lich_crown', global_max=1))
    # tasks.append(Task.ensure_item(item='life_crystal', global_max=1))
    #
    # tasks.append(Task.ensure_item(item='dreadful_shield', global_max=1))
    # tasks.append(Task.ensure_item(item='ancient_jean', global_max=1))
    #
    #
    #
    # # tasks.append(Task.ensure_item(item='cursed_hat', global_max=1))
    # tasks.append(Task.level_skill(CraftSkill.WEAPONCRAFTING, 35, stock_only=True))
    # tasks.append(Task.level_skill(CraftSkill.WEAPONCRAFTING, 35, item='gold_sword'))
    # tasks.append(Task.ensure_item(item='magic_bow', global_max=1))
    # tasks.append(Task.ensure_item(item='serpent_skin_armor', global_max=1))
    # tasks.append(Task.ensure_item(item='prospecting_amulet', global_max=3))
    # tasks.append(Task.ensure_item(item='emerald_ring', global_max=2))
    # tasks.append(Task.ensure_item(item='diamond_sword', global_max=1))
    # tasks.append(Task.ensure_item(item='sapphire_amulet', global_max=1))
    # tasks.append(Task.ensure_item(item='cursed_sceptre', global_max=1))
    # tasks.append(Task.level_skill(CraftSkill.JEWELRYCRAFTING, 35, stock_only=True))
    # tasks.append(Task.level_skill(CraftSkill.JEWELRYCRAFTING, 35, item='gold_ring'))
    # tasks.append(Task.ensure_item(item='malefic_ring', global_max=2))
    # tasks.append(Task.ensure_item(item='masterful_necklace', global_max=1))
    # tasks.append(Task.ensure_item(item='magic_stone_amulet', global_max=1))
    # tasks.append(Task.ensure_item(item='cursed_hat', global_max=1))
    # tasks.append(Task.ensure_item(item='ruby_ring', global_max=2))
    # tasks.append(Task.ensure_item(item='dreadful_armor', global_max=1))

    # tasks.append(Task.ensure_item(item='life_crystal', global_max=2))
    # tasks.append(Task.ensure_item(item='life_crystal', global_max=3))
    # tasks.append(Task.ensure_item(item='life_crystal', global_max=4))
    # tasks.append(Task.ensure_item(item='life_crystal', global_max=5))
    # tasks.append(Task.ensure_item(item='gold_pickaxe', global_max=3))

    # tasks.append(Task.level_skill(CraftSkill.GEARCRAFTING, 40, stock_only=True))
    # tasks.append(Task.level_skill(CraftSkill.GEARCRAFTING, 40, item='gold_mask'))
    # tasks.append(Task.ensure_item(item='mithril_shield', global_max=1))
    # tasks.append(Task.ensure_item(item='batwing_helmet', global_max=1))
    # tasks.append(Task.ensure_item(item='white_knight_armor', global_max=1))
    # tasks.append(Task.ensure_item(item='wrathpants', global_max=1))
    # tasks.append(Task.ensure_item(item='masterful_necklace', global_max=2))

    # tasks.append(Task.ensure_item(item='white_knight_pants', global_max=1))
    # tasks.append(Task.ensure_item(item='cultist_boots', global_max=1))
    # tasks.append(Task.ensure_item(item='fire_shield', global_max=1))
    # tasks.append(Task.ensure_item(item='cursed_sceptre', global_max=2))
    # tasks.append(Task.ensure_item(item='cultist_pants', global_max=1))
    # tasks.append(Task.ensure_item(item='ruby_ring', global_max=4))
    #
    # tasks.append(Task.ensure_item(item='wratharmor', global_max=1))
    # tasks.append(Task.ensure_item(item='mithril_platelegs', global_max=1))
    # tasks.append(Task.ensure_item(item='cultist_hat', global_max=1))
    # tasks.append(Task.ensure_item(item='mithril_platebody', global_max=1))
    # tasks.append(Task.ensure_item(item='mithril_boots', global_max=1))
    # # tasks.append(Task.ensure_item(item='cooked_hellhound_meat', global_max=200))
    #
    # tasks.append(Task.ensure_item(item='mithril_shield', global_max=3))
    # tasks.append(Task.ensure_item(item='white_knight_armor', global_max=3))
    # tasks.append(Task.ensure_item(item='wrathpants', global_max=3))
    # tasks.append(Task.ensure_item(item='lizard_boots', global_max=2))
    # tasks.append(Task.ensure_item(item='cultist_boots', global_max=2))
    # tasks.append(Task.ensure_item(item='masterful_necklace', global_max=3))
    # tasks.append(Task.ensure_item(item='topaz_ring', global_max=4))
    # tasks.append(Task.ensure_item(item='white_knight_pants', global_max=2))
    # # tasks.append(Task.ensure_item(item='batwing_helmet', global_max=2))
    #
    # tasks.append(Task.exchange_task_coins())
    # # tasks.append(Task.solve_recycling_achievements())
    # # tasks.append(Task.recycle_excess_items())
    #
    # # tasks.append(Task.fight_monster('hellhound', ttl=10))
    # # tasks.append(Task.fight_monster('orc', ttl=10))
    #
    # tasks.append(Task.level_skill(CraftSkill.JEWELRYCRAFTING, item='royal_skeleton_ring'))
    # tasks.append(Task.level_skill(CraftSkill.JEWELRYCRAFTING, 40, stock_only=True))
    # tasks.append(Task.level_skill(CraftSkill.JEWELRYCRAFTING, 40))
    # tasks.append(Task.ensure_item(item='greater_topaz_amulet', global_max=3))
    # tasks.append(Task.ensure_equipment(equipment_list=['vampire_bow', 'steel_shield', 'steel_boots']))
    # tasks.append(Task.ensure_item(item='greater_ruby_amulet', global_max=3))
    # tasks.append(Task.ensure_item(item='ruby_amulet', global_max=1))
    #
    # tasks.append(Task.level_skill(CraftSkill.WEAPONCRAFTING, 40, stock_only=True))
    # tasks.append(Task.level_skill(CraftSkill.WEAPONCRAFTING, 40, item='elderwood_staff'))
    # # tasks.append(Task.ensure_equipment(equipment_list=['obsidian_battleaxe', 'stormforged_pants', 'obsidian_helmet']))
    # tasks.append(Task.ensure_item(item='lightning_sword', global_max=5))
    # tasks.append(Task.ensure_item(item='malefic_ring', global_max=4))
    # tasks.append(Task.ensure_item(item='batwing_helmet', global_max=2))
    #
    # tasks.append(Task.recycle_item('skull_amulet', 5))
    # tasks.append(Task.recycle_item('air_and_water_amulet', 5))
    # tasks.append(Task.recycle_item('satchel', 5))
    # tasks.append(Task.recycle_item('gold_platebody', 5))
    # tasks.append(Task.recycle_item('lizard_skin_armor', 5))
    # tasks.append(Task.recycle_item('piggy_armor', 5))
    # tasks.append(Task.recycle_item('stormforged_armor', 5))
    # tasks.append(Task.recycle_item('iron_boots', 5))
    # tasks.append(Task.recycle_item('steel_boots', 5))
    # tasks.append(Task.recycle_item('serpent_skin_boots', 5))
    # tasks.append(Task.recycle_item('leather_hat', 5))
    # tasks.append(Task.recycle_item('magic_wizard_hat', 5))
    # tasks.append(Task.recycle_item('piggy_helmet', 5))
    # tasks.append(Task.recycle_item('stormforged_pants', 5))
    # tasks.append(Task.recycle_item('piggy_pants', 5))
    # tasks.append(Task.recycle_item('ring_of_chance', 5))
    # tasks.append(Task.recycle_item('steel_shield', 5))
    # tasks.append(Task.recycle_item('spruce_fishing_rod', 5))
    # tasks.append(Task.recycle_item('iron_pickaxe', 5))
    # tasks.append(Task.recycle_item('iron_axe', 5))
    # tasks.append(Task.recycle_item('vampire_bow', 5))
    # tasks.append(Task.recycle_item('obsidian_battleaxe', 5))
    #
    # tasks.append(Task.ensure_item(item='greater_ruby_amulet', global_max=4))
    # tasks.append(Task.ensure_item(item='greater_sapphire_amulet', global_max=1))
    #
    # tasks.append(Task.ensure_item(item='gold_fishing_rod', global_max=5))
    # tasks.append(Task.ensure_item(item='gold_axe', global_max=5))
    # tasks.append(Task.ensure_item(item='gold_pickaxe', global_max=5))
    # tasks.append(Task.ensure_item(item='golden_gloves', global_max=5))

    # tasks.append(Task.ensure_equipment(equipment_list=['eggstra_protection', 'eggscalibur']))

    tasks.append(Task.exchange_task_coins())

    #
    # tasks.append(Task.ensure_equipment(equipment_list=['hork_helmet', 'hell_armor', 'mithril_boots', 'burn_rune'], quantity=5))
    #
    # tasks.append(Task.recycle_item('dreadful_amulet', 5))
    # tasks.append(Task.recycle_item('gold_platelegs', 5))
    # tasks.append(Task.recycle_item('gold_sword', 5))
    # tasks.append(Task.recycle_item('obsidian_battleaxe', 5))

    # tasks.append(Task.ensure_item(item='healing_rune', global_max=5))
    # tasks.append(Task.ensure_item(item='hork_helmet', global_max=1))
    # tasks.append(Task.ensure_item(item='cultist_cloak', global_max=1))
    # tasks.append(Task.ensure_item(item='greater_emerald_amulet', global_max=1))
    # tasks.append(Task.ensure_item(item='hell_legs_armor', global_max=1))
    # tasks.append(Task.ensure_item(item='bow_from_hell', global_max=1))
    # tasks.append(Task.ensure_item(item='bow_from_hell', global_max=4))
    # tasks.append(Task.ensure_item(item='hell_armor', global_max=1))
    # tasks.append(Task.ensure_item(item='eggscalibur', global_max=1))

    equipment_map = {
        'weapon': 'bow_from_hell',
        'shield': 'eggstra_protection',
        'helmet': 'hork_helmet',
        'body_armor': 'hell_armor',
        'leg_armor': 'white_knight_pants',
        'boots': 'mithril_boots',
        'amulet': 'greater_emerald_amulet',
        'ring1': 'emerald_ring',
        'ring2': 'emerald_ring',
        'rune': 'burn_rune',
        'artifact1': 'emerald_book',
        'artifact2': 'life_crystal',
        'artifact3': 'cursed_egg',
    }
    #
    # tasks.append(
    #     Task.fight_monster(
    #         monster='rabbit_warrior',
    #         until=Until(drop_item='greater_easter_egg', drop_count=4),
    #         equip_map=equipment_map,
    #         required_hp=1164,
    #         expected_win_rate=95,
    #         task_id=Task.generate_task_id(),
    #     )
    # )

    # gee = Task.ensure_item('greater_easter_egg', 10)
    tasks.append(Task.ensure_item(item='eggstra_protection', global_max=5))
    tasks.append(Task.ensure_item(item='eggscalibur', global_max=5))

    tasks.append(
        Task.ensure_equipment(
            equipment_list=[
                'enchanter_pants',
                'enchanter_boots',
                'prospecting_amulet',
                'serpent_skin_armor',
                'cultist_boots',
                'lizard_skin_armor',
                'mithril_platelegs',
                'cultist_cloak',
                'conjurer_cloak',
                'gold_platelegs',
                'dreadful_armor',
                'white_knight_shield',
            ],
            quantity=5,
        )
    )
    tasks.append(
        Task.ensure_equipment(
            equipment_list=[
                'ruby_ring',
                'malefic_ring',
            ],
            quantity=10,
        )
    )
    tasks.append(
        Task.ensure_equipment(
            equipment_list=[
                'fire_shield',
                'water_shield',
                'air_shield',
                'earth_shield',
            ],
            quantity=2,
        )
    )

    gee = Task.ensure_item('lich_crown', 500)

    tasks.append(gee)

    # tasks.append(Task.ensure_item(item='eggstra_protection', global_max=5))
    # tasks.append(Task.ensure_item(item='eggscalibur', global_max=5))

    tasks.append(Task.level_skill(Skill.FISHING, 45))
    tasks.append(Task.level_skill(Skill.WOODCUTTING, 45))

    # tasks.append(Task.solve_tasks_achievements())

    # tasks.append(Task.solve_task(allow_cancellation=True))

    return {character_name: tasks}


#
# def quest_leaders_season3() -> Dict[str, List[Task]]:
#     character_name = character_1_name()
#     tasks: List[Task] = []
#     # tasks.extend(craft_item(5, 'wooden_staff', character_name))
#     # tasks.extend(craft_item(5, 'copper_dagger', character_name))
#     # tasks.extend(craft_item(5, 'copper_boots', character_name))
#     # tasks.extend(craft_item(5, 'copper_helmet', character_name))
#     # tasks.extend(craft_item(5, 'wooden_shield', character_name))
#     # tasks.extend(craft_item(10, 'copper_ring', character_name))
#     # tasks.append(Task.level_skill('gearcrafting', 5))
#     # tasks.extend(craft_item(5, 'copper_legs_armor', character_name))
#     # tasks.extend(craft_item(5, 'copper_armor', character_name))
#     # tasks.extend(craft_item(5, 'feather_coat', character_name))
#     # tasks.append(Task.level_skill('jewelrycrafting', 5))
#     # tasks.extend(craft_item(5, 'life_amulet', character_name))
#     # tasks.append(Task.level_skill('weaponcrafting', 5))
#     # tasks.extend(craft_item(5, 'sticky_sword', character_name))
#     # tasks.extend(craft_item(5, 'sticky_dagger', character_name))
#     # tasks.extend(craft_item(5, 'water_bow', character_name))
#     # tasks.extend(craft_item(5, 'fire_staff', character_name))
#     # tasks.append(Task.level_fight(10))
#     # tasks.append(Task.level_skill('weaponcrafting', 10, stock_only=True))
#     # tasks.append(Task.level_skill('weaponcrafting', 10))
#     # tasks.append(Task.level_skill('mining', 10, stock_only=True))
#     # tasks.append(Task.level_skill('mining', 10))
#     # tasks.extend(craft_item(5, 'iron_sword', character_name))
#     # tasks.extend(craft_item(5, 'iron_dagger', character_name))
#     # tasks.append(Task.level_skill('woodcutting', 10, stock_only=True))
#     # tasks.append(Task.level_skill('woodcutting', 10))
#     # tasks.extend(craft_item(5, 'iron_axe', character_name))
#     # tasks.extend(craft_item(5, 'iron_pickaxe', character_name))
#     # tasks.extend(craft_item(5, 'greater_wooden_staff', character_name))
#     # tasks.extend(craft_item(5, 'fire_bow', character_name))
#     # tasks.append(Task.level_skill('gearcrafting', 10))
#     # tasks.extend(craft_item(5, 'iron_boots', character_name))
#     # tasks.extend(craft_item(5, 'iron_armor', character_name))
#     # tasks.extend(craft_item(5, 'iron_legs_armor', character_name))
#     # tasks.extend(craft_item(5, 'iron_helm', character_name))
#     # tasks.extend(craft_item(5, 'leather_boots', character_name))
#     # tasks.extend(craft_item(5, 'slime_shield', character_name))
#     # tasks.extend(craft_item(5, 'adventurer_pants', character_name))
#     # tasks.extend(craft_item(5, 'leather_armor', character_name))
#     # tasks.extend(craft_item(5, 'leather_hat', character_name))
#     # tasks.extend(craft_item(5, 'adventurer_vest', character_name))
#     # tasks.extend(craft_item(5, 'adventurer_helmet', character_name))
#     # tasks.append(Task.level_skill('jewelrycrafting', 10))
#     # tasks.extend(craft_item(10, 'iron_ring', character_name))
#     # tasks.extend(craft_item(5, 'air_and_water_amulet', character_name))
#     # tasks.extend(craft_item(5, 'fire_and_earth_amulet', character_name))
#     # tasks.append(Task.level_skill('gearcrafting', 15))
#     # tasks.extend(craft_item(5, 'adventurer_boots', character_name))
#     # tasks.append(Task.level_skill('weaponcrafting', 15))
#     # tasks.extend(craft_item(1, 'multislimes_sword', character_name))
#     # tasks.extend(craft_item(5, 'multislimes_sword', character_name))
#     # tasks.extend(craft_item(1, 'mushmush_jacket', character_name))
#     # tasks.extend(craft_item(5, 'mushmush_jacket', character_name))
#     # tasks.append(Task.level_skill('jewelrycrafting', 15))
#     # tasks.extend(craft_item(10, 'life_ring', character_name))
#     # tasks.extend(craft_item(10, 'water_ring', character_name))
#     # tasks.extend(craft_item(10, 'fire_ring', character_name))
#     # tasks.extend(craft_item(10, 'earth_ring', character_name))
#     # tasks.extend(craft_item(10, 'air_ring', character_name))
#
#     # # tasks.extend(gather_and_craft_recipe(item='apple_pie', quantity=250, leader=character_name))
#     # tasks.append(Task.level_skill('weaponcrafting', 20))
#     # tasks.extend(craft_item(5, 'skull_staff', character_name))
#     # tasks.extend(craft_item(5, 'battlestaff', character_name))
#     # # tasks.extend(craft_item(5, 'forest_whip', character_name))
#     # # tasks.extend(craft_item(5, 'steel_battleaxe', character_name)) # prefer wooden club
#     # tasks.extend(craft_item(1, 'spruce_fishing_rod', character_name))
#     # tasks.append(Task.level_skill('gearcrafting', 20))
#     # tasks.extend(craft_item(5, 'skeleton_pants', character_name))  # required for ogre / best against skeleton
#     # tasks.extend(craft_item(5, 'tromatising_mask', character_name))  # required for ogre
#     # tasks.append(Task.level_skill('jewelrycrafting', 20))
#     # tasks.extend(craft_item(5, 'skull_amulet', character_name))  # required for ogre
#     # # ogre can now be defeated
#     # tasks.extend(craft_item(5, 'skeleton_armor', character_name))  # best gear against ogre
#     # tasks.extend(craft_item(5, 'steel_boots', character_name))  # best gear against ogre
#     # tasks.extend(craft_item(5, 'steel_shield', character_name))  # best gear against ogre
#     # # ogre can now be defeated most efficiently
#     # tasks.extend(craft_item(5, 'steel_armor', character_name))  # required for vampire / best gear against skeleton
#     # tasks.extend(craft_item(5, 'steel_legs_armor', character_name))  # required for vampire
#     # tasks.extend(craft_item(5, 'magic_wizard_hat', character_name))  # required for vampire
#     # tasks.extend(craft_item(5, 'serpent_skin_boots', character_name))  # required for vampire
#     # tasks.extend(craft_item(5, 'dreadful_amulet', character_name))  # required for vampire
#     # vampire can now be defeated
#     # bandit_lizard cannot be defeated with <25 gear without jasper_crystal
#     # tasks.extend(craft_item(5, 'skeleton_helmet', character_name))  # required for what?
#     # tasks.append(Task.level_skill('gearcrafting', 25))
#     # tasks.extend(craft_item(1, 'piggy_armor', character_name))  # required for bandit_lizard
#     # tasks.extend(craft_item(1, 'piggy_pants', character_name))  # required for bandit_lizard
#
#     # tasks.extend(craft_item(2, 'skull_ring', character_name))  # required for bandit_lizard
#     # tasks.extend(craft_item(10, 'steel_ring', character_name))
#     # tasks.append(Task.level_skill('jewelrycrafting', 25))
#     # tasks.extend(craft_item(1, 'ruby_amulet', character_name))  # required for bandit_lizard
#     # bandit_lizard can now be defeated by one character -> farm for bandit_armor
#
#     # tasks.append(Task.level_skill('weaponcrafting', 25))
#     # tasks.extend(craft_item(1, 'skull_wand', character_name))  # required for cyclops
#
#     # tasks.extend(craft_item(5, 'piggy_armor', character_name))  # required for bandit_lizard
#     # tasks.extend(craft_item(5, 'piggy_helmet', character_name))  # required for bandit_lizard
#     # tasks.extend(craft_item(2, 'piggy_pants', character_name))  # required for bandit_lizard
#     # tasks.extend(craft_item(2, 'ruby_amulet', character_name))  # required for bandit_lizard
#     # tasks.extend(craft_item(3, 'piggy_pants', character_name))  # required for bandit_lizard
#     # tasks.extend(craft_item(3, 'ruby_amulet', character_name))  # required for bandit_lizard
#     # tasks.extend(craft_item(5, 'piggy_pants', character_name))  # required for bandit_lizard
#     # tasks.extend(craft_item(10, 'skull_ring', character_name))  # required for bandit_lizard
#     # tasks.extend(craft_item(5, 'ruby_amulet', character_name))  # required for bandit_lizard
#     # tasks.extend(craft_item(10, 'dreadful_ring', character_name))  # required for bandit_lizard
#     # bandit_lizard can now be defeated by all characters
#
#     # tasks.extend(craft_item(5, 'steel_helm', character_name))  # required for owlbear
#
#     # tasks.extend(craft_item(1, 'gold_fishing_rod', character_name))
#     # tasks.extend(craft_item(1, 'gold_axe', character_name))
#
#     # for imp
#     # tasks.append(Task.level_skill('gearcrafting', 30))
#     # tasks.extend(craft_item(4, 'gold_platelegs', character_name))
#
#     # tasks.append(Task.level_skill('weaponcrafting', 30))
#     # tasks.extend(craft_item(4, 'elderwood_staff', character_name))
#
#     # tasks.append(Task.level_skill('jewelrycrafting', 30))
#     # tasks.extend(craft_item(10, 'gold_ring', character_name))
#     # tasks.extend(craft_item(4, 'ruby_ring', character_name))
#     # tasks.extend(craft_item(2, 'sapphire_ring', character_name))
#
#     # additional gear
#     # tasks.extend(craft_item(4, 'gold_axe', character_name))
#
#     # for owlbear
#     # tasks.extend(craft_item(1, 'obsidian_battleaxe', character_name))
#     # tasks.extend(craft_item(3, 'greater_dreadful_amulet', character_name))
#     # tasks.extend(craft_item(3, 'greater_dreadful_staff', character_name))
#     # tasks.extend(craft_item(3, 'royal_skeleton_pants', character_name))
#     # tasks.extend(craft_item(3, 'royal_skeleton_helmet', character_name))
#     # tasks.extend(craft_item(3, 'royal_skeleton_armor', character_name))
#     # tasks.extend(craft_item(3, 'lizard_boots', character_name))
#     # tasks.extend(craft_item(2, 'topaz_ring', character_name))
#     # tasks.extend(craft_item(3, 'obsidian_battleaxe', character_name))
#
#     # for demon
#     # tasks.extend(craft_item(5, 'gold_shield', character_name))
#
#     # beyond
#     # tasks.extend(craft_item(4, 'gold_pickaxe', character_name))  # requires demon horn
#     # tasks.extend(craft_item(5, 'gold_sword', character_name))  # requires demon horn
#     # tasks.extend(craft_item(5, 'gold_mask', character_name))  # requires demon horn
#     # tasks.extend(craft_item(5, 'gold_axe', character_name))
#     # tasks.extend(craft_item(5, 'gold_pickaxe', character_name))  # requires demon horn
#     # tasks.extend(craft_item(5, 'gold_platebody', character_name))  # requires demon horn
#     # tasks.extend(craft_item(5, 'gold_helm', character_name))  # requires demon horn
#     # tasks.extend(craft_item(1, 'golden_gloves', character_name))
#     # tasks.extend(craft_item(5, 'gold_boots', character_name))  # requires demon horn
#     # tasks.extend(craft_item(5, 'greater_dreadful_amulet', character_name))
#
#     # tasks.append(Task.fight_monster('lich', ttl=2))
#     # tasks.extend(craft_item(1, 'lich_crown', character_name))
#     # tasks.extend(craft_item(1, 'life_crystal', character_name))
#     # # tasks.append(Task.fight_monster('rosenblood', ttl=2))
#     # # tasks.append(Task.fight_monster('cultist_acolyte', ttl=2))
#     #
#     # tasks.extend(craft_item(1, 'obsidian_armor', character_name))
#     # tasks.extend(craft_item(4, 'topaz_ring', character_name))
#
#     # tasks.extend(craft_item(5, 'obsidian_legs_armor', character_name))
#
#     # tasks.extend(craft_item(4, 'cursed_book', character_name))  # cultist_acolyte (4/5 can defeat without pot.)
#     # tasks.extend(craft_item(5, 'goblin_tooth', character_name))  # goblin (2/5 can defeat without pot.)
#     # tasks.append(Task.level_skill('woodcutting', 35))
#     # tasks.append(Task.level_skill('mining', 35))
#     # tasks.extend(craft_item(2, 'astralyte_crystal', character_name))  # task
#     #
#     # tasks.append(Task.level_skill('jewelrycrafting', 30))
#     #
#     # # tasks.extend(craft_item(3, 'magic_stone', character_name))  # cultist_acolyte (4/5 can defeat without pot.)
#     # # tasks.extend(craft_item(3, 'lizard_skin', character_name))
#     # # tasks.extend(craft_item(3, 'wolf_hair', character_name))
#     # # tasks.extend(craft_item(1, 'sapphire', character_name))
#     # # tasks.extend(craft_item(2, 'magical_cure', character_name))  # task
#     # # tasks.extend(craft_item(5, 'serpent_skin_armor', character_name))
#     # # tasks.extend(craft_item(2, 'topaz_amulet', character_name))
#     # tasks.append(Task.level_skill('weaponcrafting', 35, item='gold_sword'))
#     # tasks.extend(craft_item(1, 'magic_bow', character_name))
#     #
#     # tasks.append(Task.level_skill('mining', 40))
#     # # tasks.extend(craft_item(5, 'magic_bow', character_name))
#     # # tasks.extend(craft_item(8, 'mithril', character_name))
#     # # tasks.extend(craft_item(3, 'goblin_tooth', character_name))  # goblin (2/5 can defeat without pot.)
#     # # tasks.extend(craft_item(3, 'vampire_blood', character_name))
#     # # tasks.extend(craft_item(5, 'jasper_crystal', character_name))  # task
#     #
#     # # not needing event items
#     # tasks.extend(craft_item(5, 'royal_skeleton_pants', character_name))
#     # tasks.extend(craft_item(5, 'royal_skeleton_helmet', character_name))
#     # tasks.extend(craft_item(5, 'royal_skeleton_armor', character_name))
#     #
#     # # not needing task items but event items
#     # tasks.extend(craft_item(5, 'obsidian_legs_armor', character_name))
#     # tasks.extend(craft_item(5, 'obsidian_armor', character_name))
#     # tasks.extend(craft_item(5, 'gold_platelegs', character_name))
#     # tasks.extend(craft_item(5, 'obsidian_helmet', character_name))
#     #
#     # # task items and event items
#     # tasks.extend(craft_item(5, 'gold_shield', character_name))
#     # tasks.extend(craft_item(1, 'lizard_boots', character_name))  # 1x magical_cure
#     # tasks.extend(craft_item(1, 'gold_boots', character_name))  # 3x demon_horn, 1x magical_cure
#     # tasks.extend(craft_item(1, 'lost_amulet', character_name))
#     #
#     # # tasks.append(Task.level_skill('gearcrafting', 35, stock_only=True))
#     # tasks.append(Task.level_skill('gearcrafting', 35, allow_event_parts=True))
#     # tasks.extend(craft_item(1, 'strangold_helmet', character_name))  # 1x diamond, 1x enchanted_fabric
#     # tasks.extend(craft_item(1, 'strangold_armor', character_name))  # 4x demon_horn, 2x magical_cure
#     # tasks.extend(craft_item(1, 'ancient_jean', character_name))  # 4x obsidian, 2x magical_cure
#     # tasks.extend(craft_item(5, 'dreadful_shield', character_name))  # 8x obsidian, 1x ruby, 1x astralyte_crystal
#     # tasks.extend(craft_item(1, 'strangold_legs_armor', character_name))  # 2x magical_cure
#
#     # tasks.extend(craft_item(5, 'lost_amulet', character_name))
#     # tasks.append(Task.level_skill('jewelrycrafting', 35))
#     # tasks.extend(craft_item(1, 'ancestral_talisman', character_name))  # cursed_book -> cultist_acolyte
#     # tasks.extend(craft_item(2, 'emerald_ring', character_name))
#     #
#     # tasks.append(Task.level_skill('gearcrafting', 40, item='gold_platelegs'))
#     # tasks.append(Task.level_skill('gearcrafting', 40))
#     # tasks.extend(craft_item(1, 'mithril_helm', character_name))
#     # tasks.extend(craft_item(1, 'mithril_platebody', character_name))  # enchanted fabric
#     # tasks.extend(craft_item(1, 'dreadful_battleaxe', character_name))
#     # tasks.extend(craft_item(1, 'diamond_amulet', character_name))
#     # tasks.extend(craft_item(5, 'mithril_platelegs', character_name))
#     #
#     # tasks.append(Task.recycle_excess_items())
#     #
#     # # tasks.extend(craft_item(1, 'book_from_hell', character_name))  # efreet_sultan
#     # # tasks.extend(craft_item(5, 'life_crystal', character_name))
#     # # tasks.extend(craft_item(5, 'lich_crown', character_name))
#     #
#     # # fight cultist_emperor:
#     # tasks.extend(craft_item(5, 'white_knight_armor', character_name))
#     # tasks.extend(craft_item(1, 'mithril_boots', character_name))  # hellhound_hair
#     # tasks.extend(craft_item(3, 'magic_bow', character_name))  # 8x magical_cure
#     # tasks.extend(craft_item(3, 'mithril_helm', character_name))  # 4x jasper_crystal
#     # tasks.extend(craft_item(3, 'dreadful_battleaxe', character_name))  # 4x jasper_crystal
#     #
#     # ##
#     # # tasks.extend(craft_item(25, 'broken_sword', character_name))  # goblin_wolfrider
#     #
#     # tasks.extend(craft_item(1, 'white_knight_helmet', character_name))  # hellhound_bone
#     # tasks.extend(craft_item(5, 'mithril_shield', character_name))  # hellhound_hair
#     # tasks.extend(craft_item(1, 'wrathpants', character_name))  # hellhound_bone
#     # # tasks.append(Task.level_skill('woodcutting', 40))
#     # tasks.extend(craft_item(1, 'white_knight_pants', character_name))
#     # tasks.extend(craft_item(1, 'white_knight_shield', character_name))  # 3x demon_horn, 3x hellhound_hair
#     # tasks.append(Task.level_skill('jewelrycrafting', 40))
#     # tasks.extend(craft_item(2, 'sacred_ring', character_name))
#     # tasks.extend(craft_item(1, 'greater_emerald_amulet', character_name))
#     # tasks.extend(craft_item(2, 'eternity_ring', character_name))
#     # tasks.extend(craft_item(2, 'greater_emerald_amulet', character_name))
#     # tasks.append(Task.level_skill('weaponcrafting', 40, item='elderwood_staff'))
#     # tasks.extend(craft_item(1, 'lightning_sword', character_name))
#     # tasks.extend(craft_item(1, 'bow_from_hell', character_name))
#     # tasks.append(Task.craft_stronger_gear(4))
#
#     # require drops from cultist_emperor -> re-enable with enough malefic_cloth
#     # tasks.extend(craft_item(1, 'cursed_sceptre', character_name))  # 3x malefic_cloth, magical_cure, cursed_book -> cultist_emperor & cultist_acolyte
#     # tasks.extend(craft_item(1, 'malefic_armor', character_name))  # 2x malefic_cloth, magical_cure -> cultist_emperor
#     # tasks.extend(craft_item(5, 'dreadful_armor', character_name))  # 5*2x malefic_cloth, piece_of_obsidian, ogre_eye -> cultist_emperor & imp & ogre
#     # tasks.extend(craft_item(1, 'cultist_boots', character_name)) # 2x malefic_cloth
#
#     # tasks.extend(craft_item(1, 'cultist_hat', character_name)) # 1x malefic_cloth
#     # tasks.extend(craft_item(1, 'cultist_pants', character_name)) # 2x malefic_cloth
#
#     # tasks.extend(craft_item(1, 'cursed_hat', character_name))  # cultist_hat is the better choice! 2x malefic_cloth, cursed_book -> cultist_emperor & cultist_acolyte
#
#     return {character_name: tasks}
