from artifactsmmo.models import CraftSkill, GatheringSkill, LogType, Skill

GEAR_POSITIONS = [
    'weapon',
    'shield',
    'helmet',
    'body_armor',
    'leg_armor',
    'boots',
    'amulet',
    'ring1',
    'ring2',
    'artifact1',
    'artifact2',
    'artifact3',
    'rune',
    'bag',
]
GEAR_TYPES = {
    'weapon',
    'shield',
    'helmet',
    'body_armor',
    'leg_armor',
    'boots',
    'amulet',
    'ring',
    'artifact',
    'rune',
    'bag',
}

SKILLS = (
    Skill.MINING,
    Skill.WOODCUTTING,
    Skill.WEAPONCRAFTING,
    Skill.GEARCRAFTING,
    Skill.JEWELRYCRAFTING,
    Skill.COOKING,
    Skill.FISHING,
    Skill.ALCHEMY,
)
GATHERING_SKILLS = (
    GatheringSkill.MINING,
    GatheringSkill.WOODCUTTING,
    GatheringSkill.FISHING,
    GatheringSkill.ALCHEMY,
)

CRAFTING_SKILLS = (
    CraftSkill.GEARCRAFTING,
    CraftSkill.WEAPONCRAFTING,
    CraftSkill.JEWELRYCRAFTING,
    CraftSkill.COOKING,
    CraftSkill.WOODCUTTING,
    CraftSkill.MINING,
    CraftSkill.ALCHEMY,
)

RECYCLING_SKILLS = (CraftSkill.WEAPONCRAFTING, CraftSkill.GEARCRAFTING, CraftSkill.JEWELRYCRAFTING)  # crafting skills that allow recycling
LEADER_CRAFTING_SKILLS = (CraftSkill.WEAPONCRAFTING, CraftSkill.GEARCRAFTING, CraftSkill.JEWELRYCRAFTING)
MAX_LEVEL = 50  # max player level
TASK_COIN_EXCHANGE_RATE = 6  # required task coins to exchange for rewards
TASK_COINS_RESERVE = 5  # reserved number of task coins to cancel unsolvable tasks
GE_RECYCLING_THRESHOLD = 500  # gold you're willing to pay for recyclable parts
HEAL_LEEWAY_FACTOR = 0.4  # take consumable if provided_heal * factor < required_hp for event monsters
REST_THRESHOLD_SECONDS = 10  # for event monsters, rest at most this long, otherwise consume food to heal
ELEMENTS = ('air', 'fire', 'earth', 'water')
SUCCESS_POSITION_ID = 283  # (4, 0)
FAILURE_POSITION_ID = 280  # (3, 0)
RECYCLING_YIELD_FACTOR = 0.25  # This is the factor of how many parts are expected to be yielded upon recycling
WIN_RATE_THRESHOLD = 97  # The win_rate threshold in percent to determine whether a fight can be won or not
ALPHA = 1.4
ACTION_EMOJI_MAP = {
    'fight-lost': '☠️',
    LogType.BUY_GE: '🛒',
    LogType.BUY_NPC: '🛒',
    LogType.CRAFTING: '🛠',
    LogType.DEPOSIT_ITEM: '🛅',
    LogType.FIGHT: '👾',
    LogType.GATHERING: '⛏️',
    LogType.MOVEMENT: '👣',
    LogType.RECYCLING: '♻️',
    LogType.REST: '🧸',
    LogType.SELL_GE: '💰',
    LogType.SELL_NPC: '💰',
    LogType.SPAWN: '🐣',
    LogType.USE: '🥩',
    LogType.WITHDRAW_ITEM: '🛄',
}
DEFAULT_SLEEP_TTL = 7
SOLVE_TASK_TIMEOUT_PER_COIN = 20
INVENTORY_UTILIZATION_FACTOR_DEFAULT = 0.7
INVENTORY_UTILIZATION_FACTOR_BOSS = 0.8
ENABLE_APPLE_CONSUMPTION = False
ENABLE_COCONUT_CONSUMPTION = False
SALES_TAX = 0  # Season 6 was 0.03 = 3%
STATIC_RESERVATIONS = {
    #'Fox_1': {
    #    'lost_world_map': 1,
    #    'healing_rune': 1,
    # },
    #'Fox_5': {
    #    'perfect_pearl': 1,  # requires level 20
    # },
}
RESTART_COOK_UPON_EMPTY_HEALING_CAPACITY = True
RESTART_FISHER_UPON_EMPTY_HEALING_CAPACITY = True
SUPPRESS_DROP_CODES = ['lich_tomb_key', 'small_pearls']
EVENT_BOSS_PARTICIPANTS = [2, 3]  # non-zero-based numbering, i.e. 1 = 1st character
