from artifactsmmo.service.helpers import (
    character_1_name,
    character_2_name,
    character_3_name,
    character_4_name,
    character_5_name,
)

# monster: ['sea_marauder', 'bandit_lizard', 'corrupted_ogre', 'corrupted_owlbear', 'grimlet', 'cultist_emperor', 'duskworm', 'demon', 'efreet_sultan']
# npc: ['fish_merchant', 'gemstone_merchant', 'herbal_merchant', 'nomadic_merchant', 'timber_merchant']
# resource: ['magic_tree', 'strange_rocks']


def event_priorities():
    return {
        character_1_name(): ['strange_rocks', 'magic_tree'],
        character_2_name(): ['strange_rocks', 'magic_tree'],
        character_3_name(): ['strange_rocks', 'magic_tree'],
        character_4_name(): ['strange_rocks', 'magic_tree'],
        character_5_name(): ['strange_rocks', 'magic_tree'],
    }
