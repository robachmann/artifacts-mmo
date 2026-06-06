from collections import Counter
import math
from typing import Optional, Set

import numpy as np
from numpy import ndarray
from scipy.optimize import fsolve

from artifactsmmo import game_constants
from artifactsmmo.extensions import ItemSchemaExtension, MonsterSchemaExtension
from artifactsmmo.fights.character_fight_stats import CharacterFightStats
from artifactsmmo.fights.combat_calculator import CombatCalculator
from artifactsmmo.fights.combat_result import CombatResults
from artifactsmmo.fights.defeat_calculations import DefeatCalculations
from artifactsmmo.fights.fight_bundle import GenericFightBundle
from artifactsmmo.log.logger import logger


class CombatCalculatorApproximation(CombatCalculator):
    def __init__(self):
        super().__init__()
        self.__total_burn_rate_factor = sum(0.9**x for x in range(10))

    def calculate_win_rate(
        self,
        character: CharacterFightStats,
        monster: MonsterSchemaExtension,
        utilities: Set[ItemSchemaExtension] = None,
        fight_bundle: GenericFightBundle = None,
        print_log: bool = False,
        min_rounds: int = 0,
        force_simulation: bool = False,
    ) -> Optional[CombatResults]:
        utilities = utilities or set()
        character_attack: float = self.__get_character_attack(character, monster)
        monster_attack: float = self.__get_monster_attack(monster)
        turns_to_win = self.__calculate_turns_to_win(character, character_attack, monster, monster_attack)

        defeat_calculations: DefeatCalculations = self.__calculate_turns_to_lose(
            character,
            character_attack,
            monster,
            monster_attack,
            turns_to_win,
            utilities,
        )
        win_rate = self.__calculate_win_probability(turns_to_win, defeat_calculations.turns_to_lose) * 100
        total_turns = turns_to_win * 2 - 1
        cooldown = max(round(total_turns * 2 - (character.haste * 0.01) * (total_turns * 2)), 5)

        required_hp = character.hp if character.hp < defeat_calculations.required_hp else defeat_calculations.required_hp
        required_hp_percent = (required_hp / character.max_hp) * 100
        return CombatResults(
            win_rate=win_rate,
            turns_to_win=turns_to_win,
            turns_to_lose=defeat_calculations.turns_to_lose,
            cooldown=cooldown,
            required_hp=required_hp,
            required_hp_percent=required_hp_percent,
            min_required_hp=required_hp,
            max_required_hp=required_hp,
            monster=monster,
            prospecting=character.prospecting,
        )

    @staticmethod
    def __calculate_win_probability(turns_to_win: float, turns_to_lose: float) -> float:
        if turns_to_lose > 1000:
            return 1
        elif turns_to_win > 100:
            return 0

        try:
            win_prob = 1 / (1 + math.exp(game_constants.ALPHA * (turns_to_win - turns_to_lose)))
        except OverflowError:
            logger.error(f'OverflowError for turns_to_win={turns_to_win}, turns_to_lose={turns_to_lose}')
            win_prob = 0
        return win_prob

    def __calculate_turns_to_win(
        self, character: CharacterFightStats, character_attack_sum: float, monster: MonsterSchemaExtension, monster_attack_sum: float
    ) -> float:
        # effects that impact the character's attack:
        # boost_dmg_fire, boost_dmg_water, boost_dmg_air, boost_dmg_earth (combat_buff) -> ☑️️ expected to be applied before
        # critical_strike (equipment_stat) -> ✅
        # poison (combat_special) -> ☑️ no items applying poison exist
        # burn (combat_special) -> ✅

        # effects that impact the monster's hp
        # healing (combat_special) -> ✅
        ## antipoison (combat_other) -> ☑️ no monsters with antipoison exist
        # lifesteal (combat_special) -> ✅

        if character.critical_strike > 0:
            character_critical_damage = 0.5 * character_attack_sum * 0.01 * character.critical_strike
        else:
            character_critical_damage = 0

        monster_healing_effect_value = monster.effect.get('healing')
        if monster_healing_effect_value and monster_healing_effect_value > 0:
            # Every 3 played turns, regains x% of life.
            monster_heal_amount = monster_healing_effect_value * monster.hp * 0.01 / 3
        else:
            monster_heal_amount = 0

        monster_lifesteal_effect_value = monster.effect.get('lifesteal')
        if monster_lifesteal_effect_value and monster_lifesteal_effect_value > 0:
            # For each critical hit, the character heals x% of your attack damage of all elements.
            monster_lifesteal_amount = 1.5 * monster_attack_sum * 0.01 * monster.critical_strike * 0.01 * monster_lifesteal_effect_value
        else:
            monster_lifesteal_amount = 0

        total_character_attack = (
            round(character_attack_sum) + round(character_critical_damage) - round(monster_heal_amount) - round(monster_lifesteal_amount)
        )
        base_damage_per_turn = total_character_attack if total_character_attack > 0 else 1

        character_burn_effect_value = character.effect.get('burn')
        if character_burn_effect_value and character_burn_effect_value > 0:
            # On your first turn, apply a burn effect of x% of your attack of all elements.
            # The damage is applied each turn and decreases by 10% each time. It is impossible to block.
            character_base_attack_sum: float = self.__get_character_base_attack(character)
            initial_burn_damage = 0.01 * character_burn_effect_value * character_base_attack_sum
            max_burn_damage = initial_burn_damage * self.__total_burn_rate_factor
            turns_to_win = self.__solve_for_burn_turns(initial_burn_damage, base_damage_per_turn, monster.hp, max_burn_damage)
        else:
            turns_to_win = monster.hp / base_damage_per_turn
        return turns_to_win

    def __calculate_turns_to_lose(
        self,
        character: CharacterFightStats,
        character_attack_sum: float,
        monster: MonsterSchemaExtension,
        monster_attack_sum: float,
        turns_to_win: float,
        # monster_block_chance: float,
        utilities: Set[ItemSchemaExtension] = None,
    ) -> DefeatCalculations:
        turns_to_lose = 1e6
        required_hp = 0
        used_utilities = Counter({utility.code: 1 for utility in utilities if utility.is_boost_utility})

        # if turns_to_win > 0.6 and monster_block_chance > 0:
        if (turns_to_win > 0.6 and turns_to_win > 1) or (turns_to_win <= 1 and character.critical_strike > 0):
            ceil_turns_to_win = math.ceil(turns_to_win)

            # effects that impact the character's hp
            # boost_hp (combat_buff) -> ☑️️ expected to be applied before
            # restore (combat_heal) -> ✅
            # healing (combat_special) -> ✅
            # antipoison (combat_other) -> ✅
            # lifesteal (combat_special) -> ✅

            # effects that impact the monster's attack:
            # poison (combat_special) -> ✅
            # reconstitution (combat_special) -> ✅
            # burn (combat_special) -> ✅
            # critical_strike (equipment_stat) -> ✅

            if monster.critical_strike > 0:
                monster_critical_damage = 0.5 * monster_attack_sum * 0.01 * monster.critical_strike
            else:
                monster_critical_damage = 0

            character_lifesteal_effect_value = character.effect.get('lifesteal')
            if character_lifesteal_effect_value and character_lifesteal_effect_value > 0:
                # For each critical hit, the character heals x% of your attack damage of all elements.
                character_lifesteal_amount = (
                    1.5 * character_attack_sum * 0.01 * character.critical_strike * 0.01 * character_lifesteal_effect_value
                )
            else:
                character_lifesteal_amount = 0

            # character_heal_amount only kicks in after 3 rounds, add it to total_monster_attack again for fights with fewer rounds.
            character_healing_effect_value = character.effect.get('healing')
            if character_healing_effect_value and character_healing_effect_value > 0 and ceil_turns_to_win > 3:
                # Every 3 played turns, regains x% of life.
                character_heal_amount = character_healing_effect_value * character.max_hp * 0.01 / 3
            else:
                character_heal_amount = 0

            monster_poison_damage = 0
            monster_poison_effect_value = monster.effect.get('poison')
            if monster_poison_effect_value and monster_poison_effect_value > 0:
                # At the start of his first turn, apply a poison of x on one of your opponents. Loses x lives per turn, damage cannot be dodged.
                utility_count = 0
                for utility in utilities or []:
                    if (antipoison := utility.item_effects.get('antipoison', 0)) > 0:
                        utility_count = math.ceil(monster_poison_effect_value / antipoison)
                        used_utilities[utility.code] = utility_count
                        break

                if utility_count == 0:
                    monster_poison_damage = monster_poison_effect_value

            base_damage_per_turn = (
                math.ceil(monster_attack_sum)
                + math.ceil(monster_critical_damage)
                + math.ceil(monster_poison_damage)
                - math.ceil(character_heal_amount)
                - math.ceil(character_lifesteal_amount)
            )
            base_damage_per_turn = 1 if base_damage_per_turn < 1 else base_damage_per_turn

            required_hp = 0
            monster_burn_effect_value = monster.effect.get('burn')
            if monster_burn_effect_value and monster_burn_effect_value > 0:
                # On your first turn, apply a burn effect of x% of your attack of all elements.
                # The damage is applied each turn and decreases by 10% each time. It is impossible to block.
                monster_base_attack_sum: float = self.__get_monster_base_attack(monster)
                initial_burn_damage = 0.01 * monster_burn_effect_value * monster_base_attack_sum
                max_burn_damage = initial_burn_damage * self.__total_burn_rate_factor
                total_suffered_burn_damage = self.__burn_damage_function(ceil_turns_to_win, initial_burn_damage, max_burn_damage)

                if utilities and (restore_per_turn := sum(u.item_effects.get('restore', 0) for u in utilities)) > 0:
                    half_hp_char = 0.5 * character.max_hp

                    if character.hp > half_hp_char:
                        turns_above_50 = max(
                            0,
                            math.ceil(
                                self.__solve_for_burn_turns(
                                    initial_burn_damage, base_damage_per_turn, character.hp - half_hp_char, max_burn_damage
                                )
                            ),
                        )
                    else:
                        turns_above_50 = 0

                    effective_hp_below = (
                        character.hp
                        - (turns_above_50 * base_damage_per_turn)
                        - (self.__burn_damage_function(turns_above_50, initial_burn_damage, max_burn_damage))
                        + restore_per_turn
                    )

                    turns_below_50 = math.ceil(
                        self.__solve_for_burn_turns(
                            initial_burn_damage,
                            base_damage_per_turn - restore_per_turn,
                            effective_hp_below,
                            max_burn_damage,
                            offset=turns_above_50,
                        )
                    )

                    restore_total = (ceil_turns_to_win - turns_above_50) * restore_per_turn
                    turns_to_lose = turns_above_50 + turns_below_50

                    required_hp = max(0, (ceil_turns_to_win - 1) * base_damage_per_turn - restore_total + total_suffered_burn_damage)

                    usage_count = max(0, ceil_turns_to_win - turns_above_50)
                    for utility_code in (u.code for u in utilities if u.item_effects.get('restore', 0) > 0):
                        used_utilities[utility_code] = usage_count
                else:
                    turns_to_lose = self.__solve_for_burn_turns(initial_burn_damage, base_damage_per_turn, character.hp, max_burn_damage)

            else:
                total_suffered_burn_damage = 0
                if utilities and (restore_per_turn := sum(u.item_effects.get('restore', 0) for u in utilities)) > 0:
                    half_hp_char = 0.5 * character.max_hp
                    turns_above_50 = max(0, math.ceil((character.hp - half_hp_char) / base_damage_per_turn))
                    remaining_hp_after_above = character.hp - (turns_above_50 * base_damage_per_turn)

                    effective_hp_below = remaining_hp_after_above + restore_per_turn

                    if base_damage_per_turn > restore_per_turn:
                        turns_below_50 = math.ceil(effective_hp_below / (base_damage_per_turn - restore_per_turn))
                    else:
                        turns_below_50 = 1e6

                    restore_total = (ceil_turns_to_win - turns_above_50) * restore_per_turn
                    turns_to_lose = turns_below_50 + turns_above_50

                    required_hp = max(0, (ceil_turns_to_win - 1) * base_damage_per_turn - restore_total)

                    usage_count = max(0, ceil_turns_to_win - turns_above_50)
                    for utility_code in (u.code for u in utilities if u.item_effects.get('restore', 0) > 0):
                        used_utilities[utility_code] = usage_count
                else:
                    turns_to_lose = character.hp / base_damage_per_turn

            if required_hp == 0:
                required_hp = ceil_turns_to_win * base_damage_per_turn + total_suffered_burn_damage

            monster_reconstitution = monster.effect.get('reconstitution')
            if monster_reconstitution and 0 < (monster_reconstitution / 2) < turns_to_lose:
                turns_to_lose = monster_reconstitution / 2

            if monster.critical_strike:
                one_critical_hit = monster_attack_sum * 1.5
                if one_critical_hit > required_hp:
                    required_hp = one_critical_hit

        return DefeatCalculations(turns_to_lose=turns_to_lose, required_hp=required_hp, used_utilities=used_utilities)

    @staticmethod
    def __get_character_base_attack(character: CharacterFightStats) -> float:
        attack_sum: float = 0
        for element, attack in character.attack_elem.items():
            if attack > 0:
                damage = character.dmg_elem[element]
                total_attack = attack * (1 + damage * 0.01)
                attack_sum += total_attack
        return attack_sum

    @staticmethod
    def __get_character_attack(character: CharacterFightStats, monster: MonsterSchemaExtension) -> float:
        attack_sum: float = 0
        for element, attack in character.attack_elem.items():
            if attack > 0:
                damage = character.dmg_elem[element]
                total_attack = attack * (1 + damage * 0.01)
                monster_resistance = 1 - monster.res_elem[element] * 0.01
                attack_sum += total_attack * monster_resistance
        return attack_sum

    @staticmethod
    def __get_monster_base_attack(monster: MonsterSchemaExtension) -> float:
        attack_sum: float = 0
        for element, attack in monster.attack_elem.items():
            if attack > 0:
                attack_sum += attack
        return attack_sum

    @staticmethod
    def __get_monster_attack(monster: MonsterSchemaExtension) -> float:
        attack_sum: float = 0
        for element, attack in monster.attack_elem.items():
            if attack > 0:
                # block_chance = 1 - character.res_elem[element] * 0.01
                attack_sum += attack  # * block_chance
        return attack_sum

    def __solve_for_burn_turns(
        self, initial_burn_damage: float, base_damage_per_turn: float, hp: float, max_burn_damage: float, offset: float = 0
    ) -> float:
        def equation(t):
            return (t * base_damage_per_turn) + self.__burn_damage_function(t, initial_burn_damage, max_burn_damage, offset) - hp

        base_damage_per_turn = base_damage_per_turn if base_damage_per_turn > 0 else 1
        turns_if_no_burns = hp / base_damage_per_turn
        t_initial_guess = turns_if_no_burns - 1 if turns_if_no_burns > 1 else turns_if_no_burns
        input_array: ndarray = np.array([t_initial_guess])
        solved_array, info, ier, msg = fsolve(equation, input_array, xtol=1e-2, maxfev=50, full_output=True)
        if ier > 1:
            logger.warning(f'ier={ier}: {msg.replace(" \n", "")} info={info}')
        solved: ndarray = solved_array
        return float(solved.item())

    @staticmethod
    def __burn_damage_function(turns: float, initial_burn_damage: float, total_burn_if_10_turns: float, offset: float = 0) -> float:
        if turns + offset < 10:
            return initial_burn_damage * (-0.00016 * turns**5 + 0.00352 * turns**4 - 0.02797 * turns**3 + 0.1064 * turns**2 + 0.917 * turns)
        return total_burn_if_10_turns
