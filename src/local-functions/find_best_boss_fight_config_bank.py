from collections import Counter
import json
from typing import List

from local_environment import LocalEnvironment
from matplotlib.offsetbox import AnchoredText
import matplotlib.pyplot as plt
import numpy as np

from artifactsmmo.extensions import CharacterSchemaExtension, MonsterSchemaExtension
from artifactsmmo.fights.combat_result import CombatResults
from artifactsmmo.fights.equipment_assembler import EquipmentScope
from artifactsmmo.log.logger import logger


class ReportFunction(LocalEnvironment):
    def handler(self):
        characters = {c.name: c for c in self.service.get_all_character_details()}
        leader = self.character_1_name
        participants = [self.character_2_name, self.character_3_name]
        fight_characters: List[CharacterSchemaExtension] = [characters[leader]]
        for participant in participants:
            fight_characters.append(characters[participant])
        skill_map = self.service.get_skill_map(characters=list(characters.values()))

        for fight_character in fight_characters:
            for slot in fight_character.equipment:
                fight_character.equipment[slot] = ''

            fight_character.equipped_items = Counter()

        bank_items_map = {
            # ring
            'copper_ring': 6,  # level: 1, drop rate: 12060
            'iron_ring': 6,  # level: 10, drop rate: 14634
            'forest_ring': 6,  # level: 10, drop rate: 1410
            'air_ring': 6,  # level: 15, drop rate: 17628
            'earth_ring': 6,  # level: 15, drop rate: 17620
            'fire_ring': 6,  # level: 15, drop rate: 17640
            'life_ring': 6,  # level: 15, drop rate: 28012
            'water_ring': 6,  # level: 15, drop rate: 17636
            'ring_of_chance': 6,  # level: 20, drop rate: 23269
            'dreadful_ring': 6,  # level: 20, drop rate: 24472
            'steel_ring': 6,  # level: 20, drop rate: 27448
            'skull_ring': 6,  # level: 20, drop rate: 17844
            'ring_of_the_adept': 5,  # level: 25, drop rate: 0
            'ruby_ring': 6,  # level: 30, drop rate: 50358
            'topaz_ring': 6,  # level: 30, drop rate: 50358
            'gold_ring': 6,  # level: 30, drop rate: 31579
            'sapphire_ring': 6,  # level: 30, drop rate: 50358
            'emerald_ring': 6,  # level: 30, drop rate: 50358
            'royal_skeleton_ring': 6,  # level: 30, drop rate: 30910
            'malefic_ring': 6,  # level: 35, drop rate: 79214
            'sacred_ring': 6,  # level: 40, drop rate: 51450
            'divinity_ring': 6,  # level: 40, drop rate: 51450
            'eternity_ring': 6,  # level: 40, drop rate: 50389
            'celest_ring': 6,  # level: 40, drop rate: 50422
            'mithril_ring': 6,  # level: 40, drop rate: 31790
            'hell_ring': 6,  # level: 45, drop rate: 47171
            'adamantite_ring': 6,  # level: 50, drop rate: 54281
            'skullforged_ring': 6,  # level: 50, drop rate: 50677
            'eternal_red_ring': 6,  # level: 50, drop rate: 50840
            # boots
            'copper_boots': 3,  # level: 1, drop rate: 16080
            'iron_boots': 3,  # level: 10, drop rate: 13527
            'leather_boots': 3,  # level: 10, drop rate: 8104
            'adventurer_boots': 3,  # level: 15, drop rate: 15745
            'steel_boots': 3,  # level: 20, drop rate: 27794
            'snakeskin_boots': 3,  # level: 20, drop rate: 17930
            'old_boots': 3,  # level: 20, drop rate: 1320
            'hard_leather_boots': 3,  # level: 20, drop rate: 21978
            'lizard_boots': 3,  # level: 30, drop rate: 33133
            'gold_boots': 3,  # level: 30, drop rate: 31878
            'flying_boots': 3,  # level: 30, drop rate: 29919
            'enchanter_boots': 3,  # level: 35, drop rate: 39650
            'cultist_boots': 3,  # level: 40, drop rate: 25408
            'mithril_boots': 3,  # level: 40, drop rate: 36965
            'sand_snakeskin_boots': 3,  # level: 45, drop rate: 47478
            'darkforged_boots': 3,  # level: 45, drop rate: 37970
            'vital_boots': 3,  # level: 50, drop rate: 34730
            'adamantite_boots': 3,  # level: 50, drop rate: 51304
            # shield
            'wooden_shield': 3,  # level: 1, drop rate: 6060
            'iron_shield': 3,  # level: 10, drop rate: 13551
            'slime_shield': 3,  # level: 20, drop rate: 22059
            'gold_shield': 3,  # level: 30, drop rate: 36653
            'dreadful_shield': 3,  # level: 35, drop rate: 52677
            'goblin_guard_shield': 3,  # level: 35, drop rate: 1635
            'fire_shield': 3,  # level: 40, drop rate: 45990
            'water_shield': 3,  # level: 40, drop rate: 43858
            'air_shield': 3,  # level: 40, drop rate: 45885
            'earth_shield': 3,  # level: 40, drop rate: 43790
            'mithril_shield': 3,  # level: 40, drop rate: 30334
            'white_knight_shield': 3,  # level: 40, drop rate: 23397
            'demoniac_shield': 3,  # level: 45, drop rate: 145252
            'darkforged_shield': 3,  # level: 45, drop rate: 123828
            'adamantite_shield': 3,  # level: 50, drop rate: 46671
            'magic_shield': 3,  # level: 50, drop rate: 34744
            # artifact
            'novice_guide': 3,  # level: 10, drop rate: 0
            'perfect_pearl': 3,  # level: 20, drop rate: 8400
            'lost_world_map': 3,  # level: 20, drop rate: 0
            'corrupted_skull': 3,  # level: 25, drop rate: 86250
            'life_crystal': 3,  # level: 30, drop rate: 25920
            'malefic_crystal': 3,  # level: 35, drop rate: 26040
            'ruby_book': 3,  # level: 40, drop rate: 32700
            'emerald_book': 3,  # level: 40, drop rate: 32700
            'sapphire_book': 3,  # level: 40, drop rate: 32700
            'topaz_book': 3,  # level: 40, drop rate: 32700
            'sandwhisper_codex': 3,  # level: 50, drop rate: 26400
            # body_armor
            'feather_coat': 3,  # level: 5, drop rate: 7065
            'copper_armor': 3,  # level: 5, drop rate: 12084
            'leather_armor': 3,  # level: 10, drop rate: 8464
            'iron_armor': 3,  # level: 10, drop rate: 13548
            'adventurer_vest': 3,  # level: 10, drop rate: 16578
            'mushmush_jacket': 3,  # level: 15, drop rate: 21420
            'steel_armor': 3,  # level: 20, drop rate: 29493
            'skeleton_armor': 3,  # level: 20, drop rate: 20005
            'hard_leather_armor': 3,  # level: 20, drop rate: 32128
            'bandit_armor': 3,  # level: 25, drop rate: 1625
            'lizard_skin_armor': 3,  # level: 25, drop rate: 19845
            'snakeskin_armor': 3,  # level: 25, drop rate: 19499
            'piggy_armor': 3,  # level: 25, drop rate: 19862
            'stormforged_armor': 3,  # level: 25, drop rate: 19877
            'gold_platebody': 3,  # level: 30, drop rate: 30922
            'obsidian_armor': 3,  # level: 30, drop rate: 44968
            'royal_skeleton_armor': 3,  # level: 30, drop rate: 44645
            'conjurer_cloak': 3,  # level: 30, drop rate: 41759
            'strangold_armor': 3,  # level: 35, drop rate: 33123
            'malefic_armor': 3,  # level: 35, drop rate: 24127
            'dreadful_armor': 3,  # level: 35, drop rate: 48474
            'mithril_platebody': 3,  # level: 40, drop rate: 33705
            'cultist_cloak': 3,  # level: 40, drop rate: 24650
            'wratharmor': 3,  # level: 40, drop rate: 33790
            'white_knight_armor': 3,  # level: 40, drop rate: 33695
            'hell_armor': 3,  # level: 45, drop rate: 119252
            'sand_snakeskin_armor': 3,  # level: 45, drop rate: 46480
            'darkforged_plate': 3,  # level: 45, drop rate: 119354
            'mesh_armor': 3,  # level: 45, drop rate: 38812
            'vital_armor': 3,  # level: 50, drop rate: 44308
            'duskarmor': 3,  # level: 50, drop rate: 53229
            'adamantite_platebody': 3,  # level: 50, drop rate: 47805
            'skullforged_armor': 3,  # level: 50, drop rate: 33807
            # leg_armor
            'copper_legs_armor': 3,  # level: 5, drop rate: 12068
            'iron_legs_armor': 3,  # level: 10, drop rate: 13548
            'leather_legs_armor': 3,  # level: 10, drop rate: 8548
            'adventurer_pants': 3,  # level: 15, drop rate: 25397
            'steel_legs_armor': 3,  # level: 20, drop rate: 29484
            'skeleton_pants': 3,  # level: 20, drop rate: 15295
            'hard_leather_pants': 3,  # level: 20, drop rate: 32374
            'snakeskin_legs_armor': 3,  # level: 25, drop rate: 22471
            'lizard_skin_legs_armor': 3,  # level: 25, drop rate: 34117
            'piggy_pants': 3,  # level: 25, drop rate: 27094
            'stormforged_pants': 3,  # level: 25, drop rate: 31022
            'gold_platelegs': 3,  # level: 30, drop rate: 40181
            'obsidian_legs_armor': 3,  # level: 30, drop rate: 45025
            'royal_skeleton_pants': 3,  # level: 30, drop rate: 39965
            'conjurer_skirt': 3,  # level: 30, drop rate: 50098
            'strangold_legs_armor': 3,  # level: 35, drop rate: 45537
            'ancient_jean': 3,  # level: 35, drop rate: 37788
            'enchanter_pants': 3,  # level: 35, drop rate: 24179
            'mithril_platelegs': 3,  # level: 40, drop rate: 31714
            'cultist_pants': 3,  # level: 40, drop rate: 100041
            'wrathpants': 3,  # level: 40, drop rate: 33713
            'white_knight_pants': 3,  # level: 40, drop rate: 33728
            'hell_legs_armor': 3,  # level: 45, drop rate: 28718
            'sand_snakeskin_pants': 3,  # level: 45, drop rate: 44604
            'mesh_legs_armor': 3,  # level: 45, drop rate: 38798
            'duskpants': 3,  # level: 50, drop rate: 34759
            'adamantite_platelegs': 3,  # level: 50, drop rate: 56237
            'skullforged_pants': 3,  # level: 50, drop rate: 33793
            # amulet
            'life_amulet': 3,  # level: 5, drop rate: 6070
            'fire_and_earth_amulet': 3,  # level: 10, drop rate: 12458
            'air_and_water_amulet': 3,  # level: 10, drop rate: 12460
            'wisdom_amulet': 3,  # level: 15, drop rate: 12566
            'dreadful_amulet': 3,  # level: 20, drop rate: 19070
            'skull_amulet': 3,  # level: 20, drop rate: 16084
            'topaz_amulet': 3,  # level: 25, drop rate: 23433
            'emerald_amulet': 3,  # level: 25, drop rate: 23433
            'sapphire_amulet': 3,  # level: 25, drop rate: 23433
            'ruby_amulet': 3,  # level: 25, drop rate: 23433
            'greater_dreadful_amulet': 3,  # level: 30, drop rate: 48890
            'lost_amulet': 3,  # level: 30, drop rate: 46218
            'prospecting_amulet': 3,  # level: 30, drop rate: 20789
            'diamond_amulet': 3,  # level: 35, drop rate: 46358
            'corrupted_stone_amulet': 3,  # level: 35, drop rate: 30591
            'masterful_necklace': 3,  # level: 35, drop rate: 30576
            'ancestral_talisman': 3,  # level: 35, drop rate: 27827
            'greater_emerald_amulet': 3,  # level: 40, drop rate: 55541
            'greater_sapphire_amulet': 3,  # level: 40, drop rate: 55541
            'greater_topaz_amulet': 3,  # level: 40, drop rate: 55505
            'greater_ruby_amulet': 3,  # level: 40, drop rate: 55505
            'heart_amulet': 3,  # level: 50, drop rate: 32741
            'dust_amulet': 3,  # level: 50, drop rate: 46800
            'amulet_of_the_grand_master': 3,  # level: 50, drop rate: 0
            # helmet
            'copper_helmet': 3,  # level: 1, drop rate: 12060
            'adventurer_helmet': 3,  # level: 10, drop rate: 14472
            'iron_helm': 3,  # level: 10, drop rate: 13551
            'leather_hat': 3,  # level: 10, drop rate: 8116
            'mushmush_wizard_hat': 3,  # level: 15, drop rate: 14304
            'lucky_wizard_hat': 3,  # level: 15, drop rate: 24594
            'wolf_ears': 3,  # level: 15, drop rate: 1215
            'magic_wizard_hat': 3,  # level: 20, drop rate: 18604
            'steel_helm': 3,  # level: 20, drop rate: 31699
            'skeleton_helmet': 3,  # level: 20, drop rate: 20874
            'tromatising_mask': 3,  # level: 20, drop rate: 27478
            'hard_leather_helmet': 3,  # level: 20, drop rate: 24132
            'piggy_helmet': 3,  # level: 25, drop rate: 23346
            'lich_crown': 3,  # level: 30, drop rate: 1630
            'gold_mask': 3,  # level: 30, drop rate: 30896
            'gold_helm': 3,  # level: 30, drop rate: 30906
            'obsidian_helmet': 3,  # level: 30, drop rate: 45005
            'royal_skeleton_helmet': 3,  # level: 30, drop rate: 60082
            'cursed_hat': 3,  # level: 35, drop rate: 101798
            'strangold_helmet': 3,  # level: 35, drop rate: 35398
            'jester_hat': 3,  # level: 35, drop rate: 97148
            'batwing_helmet': 3,  # level: 40, drop rate: 34950
            'hork_helmet': 3,  # level: 40, drop rate: 29978
            'mithril_helm': 3,  # level: 40, drop rate: 41163
            'cultist_hat': 3,  # level: 40, drop rate: 25751
            'wrathelmet': 3,  # level: 40, drop rate: 33849
            'white_knight_helmet': 3,  # level: 40, drop rate: 36390
            'corrupted_crown': 3,  # level: 45, drop rate: 253000
            'hell_helmet': 3,  # level: 45, drop rate: 32643
            'sand_snakeskin_bandana': 3,  # level: 45, drop rate: 46550
            'darkforged_helmet': 3,  # level: 45, drop rate: 41650
            'desert_wrap': 3,  # level: 50, drop rate: 1350
            'dark_horned_helmet': 3,  # level: 50, drop rate: 43201
            'adamantite_mask': 3,  # level: 50, drop rate: 51603
            'dust_helmet': 3,  # level: 50, drop rate: 33831
            # rune
            'lifesteal_rune': 3,  # level: 20, drop rate: 0
            'burn_rune': 3,  # level: 20, drop rate: 0
            'healing_rune': 3,  # level: 20, drop rate: 0
            'protection_rune': 3,  # level: 20, drop rate: 0
            'healing_aura_rune': 3,  # level: 20, drop rate: 0
            'greater_healing_rune': 3,  # level: 40, drop rate: 113000
            'greater_protection_rune': 3,  # level: 40, drop rate: 113000
            'greater_lifesteal_rune': 3,  # level: 40, drop rate: 113000
            'vampiric_rune': 3,  # level: 40, drop rate: 113000
            # weapon
            'copper_dagger': 3,  # level: 1, drop rate: 12060
            'wooden_staff': 3,  # level: 1, drop rate: 404
            'wooden_stick': 3,  # level: 1, drop rate: 0
            'copper_axe': 3,  # level: 1, drop rate: 12060
            'apprentice_gloves': 3,  # level: 1, drop rate: 6054
            'copper_pickaxe': 3,  # level: 1, drop rate: 12060
            'fishing_net': 3,  # level: 1, drop rate: 6060
            'fire_staff': 3,  # level: 5, drop rate: 7084
            'sticky_dagger': 3,  # level: 5, drop rate: 12078
            'sticky_sword': 3,  # level: 5, drop rate: 12074
            'water_bow': 3,  # level: 5, drop rate: 7082
            'iron_sword': 3,  # level: 10, drop rate: 14618
            'greater_wooden_staff': 3,  # level: 10, drop rate: 8632
            'iron_dagger': 3,  # level: 10, drop rate: 14618
            'fire_bow': 3,  # level: 10, drop rate: 8634
            'iron_pickaxe': 3,  # level: 10, drop rate: 21013
            'iron_axe': 3,  # level: 10, drop rate: 21013
            'spruce_fishing_rod': 3,  # level: 10, drop rate: 15013
            'leather_gloves': 3,  # level: 10, drop rate: 12161
            'king_slime_sword': 3,  # level: 15, drop rate: 24975
            'mushstaff': 3,  # level: 15, drop rate: 13655
            'mushmush_bow': 3,  # level: 15, drop rate: 13655
            'highwayman_dagger': 3,  # level: 15, drop rate: 1215
            'battlestaff': 3,  # level: 20, drop rate: 23585
            'forest_whip': 3,  # level: 20, drop rate: 15861
            'steel_battleaxe': 3,  # level: 20, drop rate: 21404
            'skull_staff': 3,  # level: 20, drop rate: 21620
            'hunting_bow': 3,  # level: 20, drop rate: 15956
            'steel_fishing_rod': 3,  # level: 20, drop rate: 25439
            'steel_pickaxe': 3,  # level: 20, drop rate: 25418
            'steel_gloves': 3,  # level: 20, drop rate: 25412
            'steel_axe': 3,  # level: 20, drop rate: 25450
            'shuriken': 3,  # level: 20, drop rate: 21162
            'dreadful_staff': 3,  # level: 25, drop rate: 18061
            'skull_wand': 3,  # level: 25, drop rate: 14767
            'wooden_club': 3,  # level: 25, drop rate: 1225
            'vampire_bow': 3,  # level: 25, drop rate: 27261
            'greater_dreadful_staff': 3,  # level: 30, drop rate: 37012
            'death_knight_sword': 3,  # level: 30, drop rate: 1630
            'gold_sword': 3,  # level: 30, drop rate: 31636
            'gold_fishing_rod': 3,  # level: 30, drop rate: 31168
            'gold_axe': 3,  # level: 30, drop rate: 31126
            'gold_pickaxe': 3,  # level: 30, drop rate: 30086
            'golden_gloves': 3,  # level: 30, drop rate: 30262
            'elderwood_staff': 3,  # level: 30, drop rate: 22005
            'obsidian_battleaxe': 3,  # level: 30, drop rate: 45076
            'enchanted_bow': 3,  # level: 30, drop rate: 30872
            'magic_bow': 3,  # level: 35, drop rate: 27937
            'cursed_sceptre': 3,  # level: 35, drop rate: 29765
            'strangold_sword': 3,  # level: 35, drop rate: 30786
            'dreadful_battleaxe': 3,  # level: 35, drop rate: 25759
            'diamond_sword': 3,  # level: 35, drop rate: 28342
            'sanguine_edge_of_rosen': 3,  # level: 40, drop rate: 1640
            'mithril_sword': 3,  # level: 40, drop rate: 32363
            'lightning_sword': 3,  # level: 40, drop rate: 26328
            'bloodblade': 3,  # level: 40, drop rate: 33725
            'wrathsword': 3,  # level: 40, drop rate: 33345
            'mithril_axe': 3,  # level: 40, drop rate: 31749
            'mithril_pickaxe': 3,  # level: 40, drop rate: 31754
            'mithril_fishing_rod': 3,  # level: 40, drop rate: 59997
            'mithril_gloves': 3,  # level: 40, drop rate: 31755
            'bow_from_hell': 3,  # level: 45, drop rate: 52900
            'hell_staff': 3,  # level: 45, drop rate: 161780
            'demoniac_dagger': 3,  # level: 45, drop rate: 80675
            'blade_of_hell': 3,  # level: 45, drop rate: 65370
            'hell_reaper': 3,  # level: 45, drop rate: 66158
            'desert_whip': 3,  # level: 50, drop rate: 32794
            'adamantite_sword': 3,  # level: 50, drop rate: 44790
            'dust_sword': 3,  # level: 50, drop rate: 41916
            'moonlight_staff': 3,  # level: 50, drop rate: 36833
            # 'adamantite_axe': 3,  # level: 50, drop rate: 43820
            # 'adamantite_pickaxe': 3,  # level: 50, drop rate: 43804
            # 'adamantite_fishing_rod': 3,  # level: 50, drop rate: 66990
            # 'adamantite_gloves': 3,  # level: 50, drop rate: 44814
            # 'voidstone_axe': 3,  # level: 50, drop rate: 0
            # 'voidstone_gloves': 3,  # level: 50, drop rate: 0
            # 'voidstone_fishing_rod': 3,  # level: 50, drop rate: 0
            # 'voidstone_pickaxe': 3,  # level: 50, drop rate: 0
            # utility
            'small_health_potion': 100,  # level: 5, drop rate: 903
            'earth_boost_potion': 100,  # level: 10, drop rate: 1714
            'air_boost_potion': 100,  # level: 10, drop rate: 1716
            'fire_boost_potion': 100,  # level: 10, drop rate: 1719
            'water_boost_potion': 100,  # level: 10, drop rate: 1718
            'minor_health_potion': 100,  # level: 20, drop rate: 1041
            'small_antidote': 100,  # level: 20, drop rate: 3042
            'health_potion': 100,  # level: 30, drop rate: 2646
            'antidote': 100,  # level: 30, drop rate: 7100
            'health_splash_potion': 100,  # level: 30, drop rate: 1342
            'greater_health_potion': 100,  # level: 40, drop rate: 2094
            'health_boost_potion': 100,  # level: 40, drop rate: 2755
            'enchanted_boost_potion': 100,  # level: 40, drop rate: 3755
            'earth_res_potion': 100,  # level: 40, drop rate: 4464
            'fire_res_potion': 100,  # level: 40, drop rate: 4474
            'water_res_potion': 100,  # level: 40, drop rate: 4472
            'air_res_potion': 100,  # level: 40, drop rate: 4468
            'enchanted_health_potion': 100,  # level: 45, drop rate: 3006
            'diabolic_elixir': 100,  # level: 45, drop rate: 2300
            'enchanted_antidote': 100,  # level: 45, drop rate: 7035
            'enchanted_health_splash_potion': 100,  # level: 50, drop rate: 2775
        }

        bank_items_map_counter = Counter(bank_items_map)
        monster = self.service.get_monster('sandwhisper_empress')

        raw_results: List[CombatResults] = []
        best_result = self.fight_simulator.find_best_multi_character_fight_config(
            bank_items_map=bank_items_map_counter,
            monster=monster,
            characters=fight_characters,
            exclude_drops_from_monsters=[],
            exclude_items_if_unavailable=[],
            exclude_items=[],
            include_items=[],
            equipment_scope=EquipmentScope.AVAILABLE,
            utility_scope=EquipmentScope.AVAILABLE,
            skill_map=skill_map,
            raw_results=raw_results,
            force_utilities=True,
        )

        if best_result:
            self.fight_simulator.print_fight_config(best_result, {})
            simulator_json = best_result.format_simulator_json()
            logger.info(f'Use this json at https://simulator.artifactsmmo.com/: {simulator_json}')
            self.plot_raw_results(raw_results, best_result, monster, color_by='prospecting')

    @staticmethod
    def plot_raw_results(
        results: List[CombatResults],
        best_result: CombatResults,
        monster: MonsterSchemaExtension,
        color_by: str = 'weapon',
        y_axis: str = 'win_rate',
    ):
        # Extract data
        x = [item.fight_bundle.est_turns_ratio for item in results]
        if y_axis == 'win_rate':
            y = [item.raw_result.win_rate for item in results]
            y_label = 'Win Rate [%]'
        elif y_axis == 'gather_time':
            y = [item.gather_time for item in results]
            y_label = 'Gather Time [s]'
        elif y_axis == 'cooldown':
            y = [item.raw_result.cooldown for item in results]
            y_label = 'Cooldown [s]'
        else:
            logger.error(f'Unknown y_axis: {y_axis}')
            exit(1)

        plt.figure(figsize=(10, 6))

        # -----------------------------
        # COLOR CODING
        # -----------------------------
        if color_by == 'weapon':
            # Color by weapon code
            weapon_codes = [r.equipment.get('weapon') for item in results for r in item.characters.values()]
            unique_weapons = sorted(set(weapon_codes))
            cmap = plt.get_cmap('tab10')  # Good for up to 10 distinct categories
            color_map = {weapon: cmap(i) for i, weapon in enumerate(unique_weapons)}
            colors = [color_map[w] for w in weapon_codes]

            # Scatter plot
            plt.scatter(x, y, c=colors, s=60, alpha=0.7, edgecolors='black')

            # Legend
            handles = [
                plt.Line2D([], [], marker='o', color='w', markerfacecolor=color_map[weapon], markersize=8, label=weapon)
                for weapon in unique_weapons
            ]
            plt.legend(handles=handles, title='Weapon Code', loc='best')

        elif color_by == 'prospecting':
            # Color by prospecting stat
            prospecting_stats = np.array([item.prospecting_stat for item in results])
            scatter = plt.scatter(
                x,
                y,
                c=prospecting_stats,
                cmap='viridis',
                s=60,
                alpha=0.7,
                edgecolors='black',
            )

            # Colorbar for prospecting
            cbar = plt.colorbar(scatter)
            cbar.set_label('Prospecting Stat')

        else:
            raise ValueError("Invalid color_by value. Use 'weapon' or 'prospecting'.")

        # -----------------------------
        # HIGHLIGHT BEST RESULT
        # -----------------------------
        best_x_value = best_result.fight_bundle.est_turns_ratio

        if y_axis == 'win_rate':
            best_y_value = best_result.raw_result.win_rate
        elif y_axis == 'gather_time':
            best_y_value = best_result.gather_time
        elif y_axis == 'cooldown':
            best_y_value = best_result.raw_result.cooldown
        else:
            logger.error(f'Unknown y_axis: {y_axis}')
            exit(1)

        # Highlight point with red edge
        plt.scatter(
            best_x_value,
            best_y_value,
            facecolors='none',
            edgecolors='red',
            linewidths=2,
            s=90,
            alpha=1.0,
            label='Best Result',
        )

        # Create custom text box similar to legend
        lines = [
            'Best Result',
            f'Turns Ratio: {best_x_value:.2f}',
            f'Win Rate: {best_result.raw_result.win_rate:.2f} %',
            f'Cooldown: {best_result.raw_result.cooldown:.2f}',
            f'Required HP: {best_result.raw_result.required_hp:.2f}',
            f'Turns to win: {best_result.raw_result.turns_to_win:.2f}',
            f'Prospecting: {best_result.prospecting_stat}',
            f'Gather Time: {best_result.gather_time} s',
            '',
            json.dumps(list(best_result.characters.values())[0].equipment, indent=0).translate(str.maketrans('', '', '{},"')),
        ]

        best_result_text = '\n'.join(lines)

        # Place the text box outside the plot area on the right
        anchored_text = AnchoredText(
            best_result_text,
            loc='center left',  # Start relative to the figure edge
            bbox_to_anchor=(1.02, 0.5),  # Outside right
            bbox_transform=plt.gca().transAxes,
            frameon=True,
            prop=dict(size=10, color='black'),
        )

        # Style the text box
        anchored_text.patch.set_edgecolor('black')
        anchored_text.patch.set_linewidth(1)
        anchored_text.patch.set_facecolor('white')

        # Add the anchored text to the current axes
        plt.gca().add_artist(anchored_text)

        # -----------------------------
        # FINAL TOUCHES
        # -----------------------------
        plt.title(f'{y_label} vs Estimated Turns Ratio against {monster.name}')
        plt.xlabel('Estimated Turns Ratio')
        plt.ylabel(y_label)
        plt.grid(True)
        plt.tight_layout()
        plt.show()


report_function = ReportFunction()


if __name__ == '__main__':
    report_function.handler()
