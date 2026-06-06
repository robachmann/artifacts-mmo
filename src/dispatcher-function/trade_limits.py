from typing import Dict


def get_trade_limits() -> Dict[str, Dict[str, int]]:
    return {
        'bandit_armor': {'max_quantity': 5},
        'death_knight_sword': {'max_quantity': 5},
        'forest_ring': {'max_quantity': 10},
        'golden_egg': {'max_quantity': 0},
        'golden_shrimp': {'max_quantity': 0},
        'highwayman_dagger': {'max_quantity': 5},
        'lich_crown': {'max_quantity': 5},
        'old_boots': {'max_quantity': 5},
        'shell': {'max_quantity': 0},
        'wolf_ears': {'max_quantity': 5},
        'wooden_club': {'max_quantity': 5},
    }


# available items/npcs
# {
#     'algae': 'fish_merchant',
#     'ash_wood': 'timber_merchant',
#     'astralyte_crystal': 'tasks_trader',
#     'backpack': 'nomadic_merchant', # 🛒 buy only for 50'000g each
#     'bag_of_gold': 'cultist_wizard',
#     'bandit_armor': 'nomadic_merchant', # 💰 sell only for 5000g each
#     'bass': 'fish_merchant',
#     'birch_wood': 'timber_merchant',
#     'book_from_hell': 'archaeologist',
#     'burn_rune': 'rune_vendor', # 🛒 buy only for 25'000g each
#     'cloth': 'tailor',
#     'coal': 'gemstone_merchant',
#     'copper_ore': 'gemstone_merchant',
#     'corrupted_crown': 'cultist_wizard',
#     'corrupted_fruit': 'cultist_wizard',
#     'corrupted_skull': 'cultist_wizard',
#     'cursed_wood': 'timber_merchant',
#     'dead_wood': 'timber_merchant',
#     'death_knight_sword': 'nomadic_merchant', # 💰 sell only for 5000g each
#     'diabolic_elixir': 'cultist_wizard',
#     'diamond': 'gemstone_merchant',
#     'emerald': 'gemstone_merchant',
#     'emerald_book': 'archaeologist',
#     'enchanted_fabric': 'tasks_trader',
#     'forest_ring': 'nomadic_merchant', # 💰 sell only for 200g each
#     'frozen_axe': 'timber_merchant', # 🛒 buy only for 200'000g each
#     'frozen_fishing_rod': 'fish_merchant', # 🛒 buy only for 200'000g each
#     'frozen_gloves': 'herbal_merchant', # 🛒 buy only for 200'000g each
#     'frozen_pickaxe': 'gemstone_merchant', # 🛒 buy only for 200'000g each
#     'glowstem_leaf': 'herbal_merchant',
#     'gold_ore': 'gemstone_merchant',
#     'golden_egg': 'nomadic_merchant', # 💰 sell only for 2000g each
#     'golden_shrimp': 'fish_merchant', # 💰 sell only for 1000g each
#     'gudgeon': 'fish_merchant',
#     'hard_leather': 'tailor',
#     'healing_rune': 'rune_vendor', # 🛒 buy only for 20'000g each
#     'highwayman_dagger': 'nomadic_merchant', # 💰 sell only for 500g each
#     'iron_ore': 'gemstone_merchant',
#     'jasper_crystal': 'tasks_trader',
#     'lich_crown': 'nomadic_merchant', # 💰 sell only for 10'000g each
#     'life_crystal': 'archaeologist',
#     'lifesteal_rune': 'rune_vendor', # 🛒 buy only for 30'000g each
#     'lost_world_map': 'nomadic_merchant', # 🛒 buy only for 10'000g each
#     'magic_sap': 'timber_merchant',
#     'magic_wood': 'timber_merchant',
#     'magical_cure': 'tasks_trader',
#     'malefic_crystal': 'archaeologist',
#     'maple_sap': 'timber_merchant',
#     'maple_wood': 'timber_merchant',
#     'minor_health_potion': 'nomadic_merchant',
#     'mithril_ore': 'gemstone_merchant',
#     'nettle_leaf': 'herbal_merchant',
#     'old_boots': 'nomadic_merchant', # 💰 sell only for 800g each
#     'perfect_pearl': 'fish_merchant', # 💰 sell only for 5000g each
#     'perfect_pearl': 'archaeologist',
#     'piece_of_obsidian': 'gemstone_merchant',
#     'recall_potion': 'herbal_merchant', # 🛒 buy only for 50g each
#     'ruby': 'gemstone_merchant',
#     'ruby_book': 'archaeologist',
#     'salmon': 'fish_merchant',
#     'sap': 'timber_merchant',
#     'sapphire': 'gemstone_merchant',
#     'sapphire_book': 'archaeologist',
#     'shell': 'fish_merchant', # 💰 sell only for 120g each
#     'shrimp': 'fish_merchant',
#     'small_antidote': 'nomadic_merchant',
#     'snakeskin': 'tailor',
#     'south_bank_potion': 'herbal_merchant', # 🛒 buy only for 50g each
#     'spruce_wood': 'timber_merchant',
#     'strange_ore': 'gemstone_merchant',
#     'sunflower': 'herbal_merchant',
#     'topaz': 'gemstone_merchant',
#     'topaz_book': 'archaeologist',
#     'trout': 'fish_merchant',
#     'wolf_ears': 'nomadic_merchant', # 💰 sell only for 500g each
#     'wooden_club': 'nomadic_merchant', # 💰 sell only for 600g each
# }
