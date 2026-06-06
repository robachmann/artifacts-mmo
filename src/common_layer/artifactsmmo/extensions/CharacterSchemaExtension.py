from collections import Counter
from dataclasses import dataclass
from datetime import datetime, UTC
from typing import Any, Dict, List, Set

from artifactsmmo.extensions import ItemSchemaExtension
from artifactsmmo.game_constants import FAILURE_POSITION_ID, SUCCESS_POSITION_ID
from artifactsmmo.models import CharacterSchema, ConditionSchema, CraftSkill, Skill


@dataclass
class CharacterTask:
    task: str
    task_type: str
    task_progress: int
    task_total: int
    task_remaining: int


@dataclass
class CharacterSkill:
    level: int
    xp: int
    max_xp: int


class CharacterSchemaExtension(CharacterSchema):
    def __init__(self, base_obj: CharacterSchema):
        super().__init__()
        self.__dict__.update(base_obj.__dict__)

        self.attack_elem: Dict[str, int] = {
            'air': self.attack_air,
            'fire': self.attack_fire,
            'earth': self.attack_earth,
            'water': self.attack_water,
        }
        self.dmg_elem: Dict[str, int] = {
            'air': self.dmg_air + self.dmg,
            'fire': self.dmg_fire + self.dmg,
            'earth': self.dmg_earth + self.dmg,
            'water': self.dmg_water + self.dmg,
        }
        self.res_elem: Dict[str, int] = {
            'air': self.res_air,
            'fire': self.res_fire,
            'earth': self.res_earth,
            'water': self.res_water,
        }
        self.current_task: CharacterTask = CharacterTask(
            task=self.task,
            task_type=self.task_type,
            task_progress=self.task_progress,
            task_total=self.task_total,
            task_remaining=self.task_total - self.task_progress,
        )

        self.equipment: Dict[str, str] = {
            'weapon': self.weapon_slot,
            'shield': self.shield_slot,
            'helmet': self.helmet_slot,
            'body_armor': self.body_armor_slot,
            'leg_armor': self.leg_armor_slot,
            'boots': self.boots_slot,
            'amulet': self.amulet_slot,
            'ring1': self.ring1_slot,
            'ring2': self.ring2_slot,
            'artifact1': self.artifact1_slot,
            'artifact2': self.artifact2_slot,
            'artifact3': self.artifact3_slot,
            'rune': self.rune_slot,
            'bag': self.bag_slot,
            'utility1': self.utility1_slot,
            'utility2': self.utility2_slot,
        }
        self.utilities: Dict[str, int] = {}
        if self.utility1_slot:
            self.utilities[self.utility1_slot] = self.utility1_slot_quantity
        if self.utility2_slot:
            self.utilities[self.utility2_slot] = self.utility2_slot_quantity

        self.inventory_map: Counter[str] = Counter()
        for item in self.inventory:
            if item.code:
                self.inventory_map[item.code] = item.quantity

        self.equipped_items: Counter[str] = Counter(e for e in self.equipment.values() if e)
        self.equipped_items.update(self.utilities)

        self.skills: Dict[CraftSkill | Skill | str, CharacterSkill] = {
            Skill.WEAPONCRAFTING: CharacterSkill(self.weaponcrafting_level, self.weaponcrafting_xp, self.weaponcrafting_max_xp),
            Skill.GEARCRAFTING: CharacterSkill(self.gearcrafting_level, self.gearcrafting_xp, self.gearcrafting_max_xp),
            Skill.JEWELRYCRAFTING: CharacterSkill(self.jewelrycrafting_level, self.jewelrycrafting_xp, self.jewelrycrafting_max_xp),
            Skill.COOKING: CharacterSkill(self.cooking_level, self.cooking_xp, self.cooking_max_xp),
            Skill.WOODCUTTING: CharacterSkill(self.woodcutting_level, self.woodcutting_xp, self.woodcutting_max_xp),
            Skill.MINING: CharacterSkill(self.mining_level, self.mining_xp, self.mining_max_xp),
            Skill.ALCHEMY: CharacterSkill(self.alchemy_level, self.alchemy_xp, self.alchemy_max_xp),
            Skill.FISHING: CharacterSkill(self.fishing_level, self.fishing_xp, self.fishing_max_xp),
        }

        self.position = (self.layer, self.x, self.y)

    def get_remaining_cooldown(self):
        cooldown = (self.cooldown_expiration - datetime.now(UTC)).total_seconds()
        return cooldown if cooldown > 0 else 0

    def is_ready(self) -> bool:
        cooldown = (self.cooldown_expiration - datetime.now(UTC)).total_seconds()
        return cooldown <= 0

    def __hash__(self):
        return hash(self.name)

    def is_inventory_full(self, spacer: int = 0):
        return self.inventory_map.total() == self.inventory_max_items or (self.inventory_map.total() + spacer > self.inventory_max_items)

    def inventory_capacity(self, teleport_item_codes: List[str] = None, character_max_items: int = None):
        max_items = character_max_items or self.inventory_max_items
        if teleport_item_codes:
            teleport_item_count = sum(i_qty for i_code, i_qty in self.inventory_map.items() if i_code in teleport_item_codes)
            return max_items - teleport_item_count
        else:
            return max_items

    def is_task_complete(self):
        return self.current_task.task and self.current_task.task_remaining == 0

    def can_equip(self, item: ItemSchemaExtension) -> bool:
        if not item.conditions:
            return True

        def condition_satisfied(condition: ConditionSchema) -> bool:
            required_level = int(condition.value)
            skill = condition.code.removesuffix('_level')
            current_level = self.skills[skill].level if skill in self.skills else self.level
            return condition.operator == 'gt' and current_level > required_level

        return all(condition_satisfied(condition) for condition in item.conditions)

    def has_item(self, item_code: str, item_qty: int):
        return self.equipped_items.get(item_code, 0) + self.inventory_map.get(item_code, 0) >= item_qty

    @classmethod
    def empty(cls, level: int = 1):
        default_dict: Dict[str, Any] = {}
        for key, value in CharacterSchema().openapi_types.items():
            if value == int:
                default_dict[key] = 0
            elif value.__class__.__name__ == '_GenericAlias' and value.__origin__ is list:
                default_dict[key] = []

        c = CharacterSchema.from_dict(default_dict)
        c.level = level
        return cls(c)

    def at_success_position(self):
        return self.map_id == SUCCESS_POSITION_ID

    def at_failure_position(self):
        return self.map_id == FAILURE_POSITION_ID

    def is_full_hp(self):
        return self.hp >= self.max_hp

    def processed_food_count(self, processed_food_codes: Set[str]) -> int:
        total = 0
        for item_code, item_qty in self.inventory_map.items():
            if item_code in processed_food_codes:
                total += item_qty
        return total

    def get_base_hp(self) -> int:
        return self.level * 5 + 115
