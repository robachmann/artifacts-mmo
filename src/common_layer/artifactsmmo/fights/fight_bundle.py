from typing import Dict, List, Optional

from artifactsmmo.extensions import MonsterSchemaExtension
from artifactsmmo.fights.character_fight_stats import CharacterFightStats

decay_factors = [0.9**t for t in range(50)]


def self_round(number) -> int:
    return int(float(number) + 0.5)


class GenericFightBundleParticipant:
    def __init__(
        self,
        initiative,
        max_hp,
        hp,
        healing_effect_value_per_instance,
        initial_burn_from_participant,
        burn_from_participant,
        lifesteal_effect_value,
        healing_aura_effect_value,
        shell_effect_value,
        critical_strike_chance,
        element_basic_attacks,
        element_basic_shelled_attacks,
        element_critical_attacks,
        element_critical_shelled_attacks,
        poison_effect_value=None,
        reconstitution_effect_value=None,
        reconstitution_effect_half_value=None,
        corrupted_effect_value=None,
        element_critical_attacks_corrupted_series=None,
        element_basic_attacks_corrupted_series=None,
        element_corrupted_series=None,
        total_attack_value=None,
        barrier_effect_value=None,
        frenzy_effect_value=None,
        vampiric_strike_effect_value=None,
        berserker_rage_effect_value=None,
        void_drain_effect_value=None,
        guard_effect_value=None,
        protective_bubble_effect_value=None,
        threat=None,
        haste_value=None,
        prospecting: int = None,
        display_name: str = '',
    ):
        self.name = display_name

        self.initiative = initiative
        self.prospecting = prospecting
        self.threat = threat
        self.max_hp = max_hp
        self.half_hp = max_hp * 0.5
        self.hp = hp
        self.haste_value = haste_value
        self.healing_effect_value_per_instance = healing_effect_value_per_instance
        self.initial_burn_from_participant = initial_burn_from_participant
        self.burn_from_participant: List[int] = burn_from_participant
        self.lifesteal_effect_value = lifesteal_effect_value
        self.healing_aura_effect_value = healing_aura_effect_value
        self.shell_effect_value = shell_effect_value
        self.critical_strike_chance: float = critical_strike_chance
        self.element_basic_attacks: Dict[str, int] = element_basic_attacks
        self.element_basic_shelled_attacks: Dict[str, int] = element_basic_shelled_attacks
        self.element_critical_attacks: Dict[str, int] = element_critical_attacks
        self.element_critical_shelled_attacks: Dict[str, int] = element_critical_shelled_attacks

        self.poison_effect_value = poison_effect_value
        self.reconstitution_effect_value: int = reconstitution_effect_value
        self.reconstitution_effect_half_value: int = int(reconstitution_effect_half_value) if reconstitution_effect_half_value else None
        self.corrupted_effect_value: int = corrupted_effect_value
        self.element_critical_attacks_corrupted_series = element_critical_attacks_corrupted_series
        self.element_basic_attacks_corrupted_series = element_basic_attacks_corrupted_series
        self.element_corrupted_series = element_corrupted_series
        self.total_attack_value = total_attack_value
        self.barrier_effect_value = barrier_effect_value
        self.frenzy_effect_value = frenzy_effect_value
        self.vampiric_strike_effect_value = vampiric_strike_effect_value
        self.berserker_rage_effect_value = berserker_rage_effect_value
        self.void_drain_effect_value = void_drain_effect_value
        self.guard_effect_value = guard_effect_value
        self.protective_bubble_effect_value = protective_bubble_effect_value

        self.attack_elem = {}
        self.dmg_elem = {}
        self.res_elem = {}
        self.level: Optional[int] = None


class GenericFightBundle:
    def __init__(
        self,
        character_initiative,
        character_prospecting,
        character_threat,
        character_max_hp,
        current_character_hp,
        character_haste_value,
        character_healing_effect_value_per_instance,
        initial_burn_from_character,
        burn_from_character,
        character_lifesteal_effect_value,
        character_healing_aura_effect_value,
        character_shell_effect_value,
        character_critical_strike_chance,
        character_element_basic_attacks,
        character_element_basic_shelled_attacks,
        character_element_critical_attacks,
        character_element_critical_shelled_attacks,
        monster_initiative,
        monster_max_hp,
        monster_healing_effect_value_per_instance,
        initial_burn_from_monster,
        burn_from_monster,
        monster_lifesteal_effect_value,
        monster_healing_aura_effect_value,
        monster_shell_effect_value,
        monster_poison_effect_value,
        monster_reconstitution_effect_value,
        monster_reconstitution_effect_half_value,
        monster_critical_strike_chance,
        monster_element_basic_attacks,
        monster_element_basic_shelled_attacks,
        monster_element_critical_attacks,
        monster_element_critical_shelled_attacks,
        monster_corrupted_effect_value,
        character_element_critical_attacks_corrupted_series,
        character_element_basic_attacks_corrupted_series,
        character_element_corrupted_series,
        character_total_attack_value,
        monster_total_attack_value,
        monster_barrier_effect_value,
        monster_protective_bubble_effect_value,
        est_character_turns: float,
        est_monster_turns: float,
        est_turns_ratio: float,
        character_name: str,
        monster_name: str,
        partially_initialized: bool = False,
    ):
        self.character = GenericFightBundleParticipant(
            display_name=character_name,
            initiative=character_initiative,
            prospecting=character_prospecting,
            threat=character_threat,
            max_hp=character_max_hp,
            hp=current_character_hp,
            haste_value=character_haste_value,
            healing_effect_value_per_instance=character_healing_effect_value_per_instance,
            initial_burn_from_participant=initial_burn_from_character,
            burn_from_participant=burn_from_character,
            lifesteal_effect_value=character_lifesteal_effect_value,
            healing_aura_effect_value=character_healing_aura_effect_value,
            shell_effect_value=character_shell_effect_value,
            critical_strike_chance=character_critical_strike_chance,
            element_basic_attacks=character_element_basic_attacks,
            element_basic_shelled_attacks=character_element_basic_shelled_attacks,
            element_critical_attacks=character_element_critical_attacks,
            element_critical_shelled_attacks=character_element_critical_shelled_attacks,
            poison_effect_value=None,
            reconstitution_effect_value=None,
            reconstitution_effect_half_value=None,
            corrupted_effect_value=None,
            element_critical_attacks_corrupted_series=character_element_critical_attacks_corrupted_series,
            element_basic_attacks_corrupted_series=character_element_basic_attacks_corrupted_series,
            element_corrupted_series=character_element_corrupted_series,
            total_attack_value=character_total_attack_value,
            barrier_effect_value=None,
        )
        self.monster = GenericFightBundleParticipant(
            display_name=monster_name,
            initiative=monster_initiative,
            max_hp=monster_max_hp,
            hp=monster_max_hp,
            healing_effect_value_per_instance=monster_healing_effect_value_per_instance,
            initial_burn_from_participant=initial_burn_from_monster,
            burn_from_participant=burn_from_monster,
            lifesteal_effect_value=monster_lifesteal_effect_value,
            healing_aura_effect_value=monster_healing_aura_effect_value,
            shell_effect_value=monster_shell_effect_value,
            poison_effect_value=monster_poison_effect_value,
            reconstitution_effect_value=monster_reconstitution_effect_value,
            reconstitution_effect_half_value=monster_reconstitution_effect_half_value,
            critical_strike_chance=monster_critical_strike_chance,
            element_basic_attacks=monster_element_basic_attacks,
            element_basic_shelled_attacks=monster_element_basic_shelled_attacks,
            element_critical_attacks=monster_element_critical_attacks,
            element_critical_shelled_attacks=monster_element_critical_shelled_attacks,
            corrupted_effect_value=monster_corrupted_effect_value,
            total_attack_value=monster_total_attack_value,
            barrier_effect_value=monster_barrier_effect_value,
            protective_bubble_effect_value=monster_protective_bubble_effect_value,
        )
        self.est_character_turns = est_character_turns
        self.est_monster_turns = est_monster_turns
        self.est_turns_ratio = est_turns_ratio
        self.partially_initialized = partially_initialized

    @classmethod
    def from_fight_stats(cls, character: CharacterFightStats, monster: MonsterSchemaExtension, character_name: str = 'Character'):
        c = cls.partial_from_fight_stats(character, monster, character_name)
        c.complete_initialization(character, monster)
        return c

    @classmethod
    def partial_from_fight_stats(cls, character: CharacterFightStats, monster: MonsterSchemaExtension, character_name: str = 'Character'):
        # Pre-calculate commonly used values
        has_monster_shell = 'shell' in monster.effect
        has_character_shell = 'shell' in character.effect
        character_critical_strike_chance = character.critical_strike * 0.01
        monster_critical_strike_chance = monster.critical_strike * 0.01

        # CHARACTER ATTACKS - vectorize if possible
        character_element_basic_attacks: Dict[str, int] = {}
        character_element_basic_shelled_attacks: Dict[str, int] = {}
        character_element_critical_attacks: Dict[str, int] = {}
        character_element_critical_shelled_attacks: Dict[str, int] = {}

        character_total_basic = 0
        character_total_crit = 0

        for element, attack in character.attack_elem.items():
            if attack <= 0:
                continue

            total_attack = self_round(attack * (1 + character.dmg_elem[element] * 0.01))
            elemental_resistance = monster.res_elem[element] * 0.01
            elemental_attack = self_round(total_attack * (1 - elemental_resistance))

            character_element_basic_attacks[element] = elemental_attack
            character_total_basic += elemental_attack

            crit_attack = self_round(1.5 * elemental_attack)
            character_element_critical_attacks[element] = crit_attack
            character_total_crit += crit_attack

            if has_monster_shell:
                elemental_resistance_shelled = (monster.res_elem[element] + monster.effect['shell']) * 0.01
                elemental_attack_shelled = self_round(total_attack * (1 - elemental_resistance_shelled))
                character_element_basic_shelled_attacks[element] = elemental_attack_shelled
                character_element_critical_shelled_attacks[element] = self_round(1.5 * elemental_attack_shelled)

        # MONSTER ATTACKS
        monster_element_basic_attacks: Dict[str, int] = {}
        monster_element_critical_attacks: Dict[str, int] = {}
        monster_element_basic_shelled_attacks: Dict[str, int] = {}
        monster_element_critical_shelled_attacks: Dict[str, int] = {}

        monster_total_basic = 0
        monster_total_crit = 0

        for element, attack in monster.attack_elem.items():
            if attack <= 0:
                continue

            elemental_resistance = character.res_elem[element] * 0.01
            elemental_attack = self_round(attack * (1 - elemental_resistance))

            monster_element_basic_attacks[element] = elemental_attack
            monster_total_basic += elemental_attack

            crit_attack = self_round(1.5 * elemental_attack)
            monster_element_critical_attacks[element] = crit_attack
            monster_total_crit += crit_attack

            if has_character_shell:
                elemental_resistance_shelled = (character.res_elem[element] + character.effect['shell']) * 0.01
                elemental_attack_shelled = self_round(attack * (1 - elemental_resistance_shelled))
                monster_element_basic_shelled_attacks[element] = elemental_attack_shelled
                monster_element_critical_shelled_attacks[element] = self_round(1.5 * elemental_attack_shelled)

        # Calculate total attack values using pre-computed sums
        character_total_attack_value = (character_critical_strike_chance * character_total_crit) + (
            (1 - character_critical_strike_chance) * character_total_basic
        )
        monster_total_attack_value = (monster_critical_strike_chance * monster_total_crit) + (
            (1 - monster_critical_strike_chance) * monster_total_basic
        )

        # Avoid division by zero
        character_total_attack_value = max(character_total_attack_value, 1)

        est_character_turns = monster.hp / character_total_attack_value
        est_monster_turns = character.max_hp / monster_total_attack_value
        est_turns_ratio = est_character_turns / est_monster_turns

        return cls(
            character_initiative=character.initiative,
            character_prospecting=character.prospecting,
            character_threat=character.threat,
            character_max_hp=character.max_hp,
            current_character_hp=character.hp,
            character_haste_value=None,
            character_healing_effect_value_per_instance=None,
            initial_burn_from_character=None,
            burn_from_character=None,
            character_lifesteal_effect_value=None,
            character_healing_aura_effect_value=None,
            character_shell_effect_value=None,
            character_critical_strike_chance=character_critical_strike_chance,
            character_element_basic_attacks=character_element_basic_attacks,
            character_element_basic_shelled_attacks=character_element_basic_shelled_attacks,
            character_element_critical_attacks=character_element_critical_attacks,
            character_element_critical_shelled_attacks=character_element_critical_shelled_attacks,
            monster_initiative=monster.initiative,
            monster_max_hp=monster.hp,
            monster_healing_effect_value_per_instance=None,
            initial_burn_from_monster=None,
            burn_from_monster=None,
            monster_lifesteal_effect_value=None,
            monster_healing_aura_effect_value=None,
            monster_shell_effect_value=None,
            monster_poison_effect_value=None,
            monster_reconstitution_effect_value=None,
            monster_reconstitution_effect_half_value=None,
            monster_critical_strike_chance=monster_critical_strike_chance,
            monster_element_basic_attacks=monster_element_basic_attacks,
            monster_element_basic_shelled_attacks=monster_element_basic_shelled_attacks,
            monster_element_critical_attacks=monster_element_critical_attacks,
            monster_element_critical_shelled_attacks=monster_element_critical_shelled_attacks,
            monster_corrupted_effect_value=None,
            character_element_critical_attacks_corrupted_series=None,
            character_element_basic_attacks_corrupted_series=None,
            character_element_corrupted_series=None,
            character_total_attack_value=character_total_attack_value,
            monster_total_attack_value=monster_total_attack_value,
            monster_barrier_effect_value=None,
            monster_protective_bubble_effect_value=None,
            est_character_turns=est_character_turns,
            est_monster_turns=est_monster_turns,
            est_turns_ratio=est_turns_ratio,
            character_name=character_name,
            monster_name=monster.name,
            partially_initialized=True,
        )

    def complete_initialization(self, character: CharacterFightStats, monster: MonsterSchemaExtension):
        # CHARACTER
        self.character.haste_value = character.haste * 0.01
        self.character.level = character.level
        character_healing_effect_value = character.effect['healing'] * 0.01 if 'healing' in character.effect else 0
        self.character.healing_effect_value_per_instance = self_round(self.character.max_hp * character_healing_effect_value)

        character_burn_effect_value = character.effect['burn'] * 0.01 if 'burn' in character.effect else 0
        self.character.initial_burn_from_participant = self_round(character_burn_effect_value * character.base_attack_sum)
        self.character.burn_from_participant = []
        if self.character.initial_burn_from_participant:
            for t in range(50):
                burn_damage = self.character.initial_burn_from_participant * decay_factors[t]
                if burn_damage >= 1:
                    self.character.burn_from_participant.append(int(burn_damage))
                else:
                    break

        self.character.lifesteal_effect_value = character.effect['lifesteal'] * 0.01 if 'lifesteal' in character.effect else 0
        self.character.healing_aura_effect_value = character.effect['healing_aura'] * 0.01 if 'healing_aura' in character.effect else 0
        self.character.shell_effect_value = character.effect['shell'] * 0.01 if 'shell' in character.effect else 0
        self.character.frenzy_effect_value = character.effect['frenzy'] * 0.01 if 'frenzy' in character.effect else 0
        self.character.vampiric_strike_effect_value = character.effect['vampiric_strike'] * 0.01 if 'vampiric_strike' in character.effect else 0
        self.character.berserker_rage_effect_value = character.effect['berserker_rage'] * 0.01 if 'berserker_rage' in character.effect else 0
        self.character.void_drain_effect_value = character.effect['void_drain'] * 0.01 if 'void_drain' in character.effect else 0
        self.character.guard_effect_value = character.effect['guard'] * 0.01 if 'guard' in character.effect else 0
        self.monster.corrupted_effect_value = monster.effect.get('corrupted', 0)

        self.character.element_critical_attacks_corrupted_series = []
        self.character.element_basic_attacks_corrupted_series = []
        self.character.element_corrupted_series = []
        if self.monster.corrupted_effect_value > 0:
            for i in range(50):
                character_element_basic_attacks_corrupted_values: Dict[str, int] = {}
                character_element_critical_attacks_corrupted_values: Dict[str, int] = {}
                character_element_corrupted_values: Dict[str, int] = {}
                for element, attack in character.attack_elem.items():
                    if attack > 0:
                        character_element_corrupted_values[element] = monster.res_elem[element] - i * self.monster.corrupted_effect_value
                        elemental_resistance = (monster.res_elem[element] - i * self.monster.corrupted_effect_value) * 0.01
                        total_attack = self_round(attack * (1 + character.dmg_elem[element] * 0.01))
                        elemental_attack = self_round(total_attack * (1 - elemental_resistance))
                        character_element_basic_attacks_corrupted_values[element] = elemental_attack
                        character_element_critical_attacks_corrupted_values[element] = self_round(1.5 * elemental_attack)
                self.character.element_basic_attacks_corrupted_series.append(character_element_basic_attacks_corrupted_values)
                self.character.element_critical_attacks_corrupted_series.append(character_element_critical_attacks_corrupted_values)
                self.character.element_corrupted_series.append(character_element_corrupted_values)

        # MONSTER
        monster_healing_effect_value = monster.effect['healing'] * 0.01 if 'healing' in monster.effect else 0
        self.monster.level = monster.level
        self.monster.healing_effect_value_per_instance = self_round(self.monster.max_hp * monster_healing_effect_value)
        self.monster.barrier_effect_value = monster.effect['barrier'] if 'barrier' in monster.effect else 0
        self.monster.frenzy_effect_value = monster.effect['frenzy'] * 0.01 if 'frenzy' in monster.effect else 0
        self.monster.vampiric_strike_effect_value = monster.effect['vampiric_strike'] * 0.01 if 'vampiric_strike' in monster.effect else 0
        self.monster.berserker_rage_effect_value = monster.effect['berserker_rage'] * 0.01 if 'berserker_rage' in monster.effect else 0
        self.monster.void_drain_effect_value = monster.effect['void_drain'] * 0.01 if 'void_drain' in monster.effect else 0
        self.monster.guard_effect_value = monster.effect['guard'] * 0.01 if 'guard' in monster.effect else 0

        monster_burn_effect_value = monster.effect['burn'] * 0.01 if 'burn' in monster.effect else 0
        self.monster.initial_burn_from_participant = self_round(monster_burn_effect_value * monster.base_attack_sum)
        self.monster.burn_from_participant = []
        if self.monster.initial_burn_from_participant:
            for t in range(50):
                burn_damage = self.monster.initial_burn_from_participant * decay_factors[t]
                if burn_damage >= 1:
                    self.monster.burn_from_participant.append(int(burn_damage))
                else:
                    break

        self.monster.lifesteal_effect_value = monster.effect['lifesteal'] * 0.01 if 'lifesteal' in monster.effect else 0
        self.monster.poison_effect_value = monster.effect.get('poison', 0)
        self.monster.reconstitution_effect_value = monster.effect.get('reconstitution', 0)
        if self.monster.reconstitution_effect_value > 0:
            self.monster.reconstitution_effect_half_value = int(self.monster.reconstitution_effect_value * 0.5)
        else:
            self.monster.reconstitution_effect_half_value = 0

        self.monster.protective_bubble_effect_value = monster.effect.get('protective_bubble', 0)

        self.character.attack_elem = character.attack_elem
        self.character.dmg_elem = character.dmg_elem
        self.character.res_elem = character.res_elem

        self.monster.attack_elem = monster.attack_elem
        self.monster.res_elem = monster.res_elem

        self.partially_initialized = False


def calculate_elemental_attacks(
    attack_elem: dict[str, float],
    dmg_bonus: dict[str, float],
    res_elem: dict[str, float],
) -> tuple[dict[str, int], dict[str, int]]:
    """
    Ultra-fast elemental attack calculation.
    Optimized for up to 4 elements — matches inline performance.
    """

    basic_attacks = {}
    critical_attacks = {}

    # Cache local vars for speed
    percent = 0.01
    crit_mult = 1.5
    round_fn = self_round

    # Precompute multiplier: if apply_dmg_bonus = True → 1 + dmg% * 0.01, else = 1
    for element, attack in attack_elem.items():
        if attack <= 0:
            continue

        dmg_mult = 1 + dmg_bonus[element] * percent  # if apply_dmg_bonus else 1
        total_attack = round_fn(attack * dmg_mult)

        # Apply resistance
        resistance = res_elem[element] * percent
        elemental_attack = round_fn(total_attack * (1 - resistance))

        # Store results
        basic_attacks[element] = elemental_attack
        critical_attacks[element] = round_fn(crit_mult * elemental_attack)

    return basic_attacks, critical_attacks
