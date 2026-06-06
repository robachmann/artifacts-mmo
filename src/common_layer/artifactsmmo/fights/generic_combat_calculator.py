from collections import Counter, defaultdict
from itertools import cycle
import math
import random
import statistics
from typing import Dict, Iterator, List, Optional, Set, Tuple

import numpy as np

from artifactsmmo.extensions import ItemSchemaExtension, MonsterSchemaExtension
from artifactsmmo.fights.character_fight_stats import CharacterFightStats
from artifactsmmo.fights.combat_calculator import CombatCalculator
from artifactsmmo.fights.combat_result import CharacterResult, CombatResults, RoundResult
from artifactsmmo.fights.fight_bundle import GenericFightBundle, GenericFightBundleParticipant, self_round
from artifactsmmo.fights.simulation_result import LiveStats, SimulationResult
from artifactsmmo.game_constants import ELEMENTS
from artifactsmmo.log.logger import logger
from artifactsmmo.service.helpers import stats_iterator


class GenericCombatCalculator(CombatCalculator):
    def __init__(self):
        super().__init__()
        self.rng = random.Random()

    def calculate_win_rate(
        self,
        character_fight_stats: CharacterFightStats,
        monster: MonsterSchemaExtension,
        utilities: Set[ItemSchemaExtension] = None,
        fight_bundle: GenericFightBundle = None,
        print_log: bool = False,
        min_rounds: int = 0,
        force_simulation: bool = False,
    ) -> Optional[CombatResults]:
        if not fight_bundle:
            fight_bundle = GenericFightBundle.from_fight_stats(character_fight_stats, monster, 'Character')
        multi_fight_bundle_map: Dict[str, GenericFightBundle] = {fight_bundle.character.name: fight_bundle}
        result = self.calculate_multi_character_win_rate(
            multi_fight_bundle_map=multi_fight_bundle_map,
            monster=monster,
            utilities_map={fight_bundle.character.name: utilities},
            print_log=print_log,
            min_rounds=min_rounds,
            force_simulation=force_simulation,
        )
        if 'Character' in result.characters:
            result.characters['Character'].level = character_fight_stats.level
        return result

    def calculate_multi_character_win_rate(
        self,
        multi_fight_bundle_map: Dict[str, GenericFightBundle],
        monster: MonsterSchemaExtension,
        utilities_map: Dict[str, Set[ItemSchemaExtension]] = None,
        print_log: bool = False,
        min_rounds: int = 0,
        force_simulation: bool = False,
    ) -> Optional[CombatResults]:

        utilities_map = utilities_map or {}
        turns_to_win: List[int] = []
        turns_to_lose: List[int] = []
        cooldown: List[int] = []
        character_results: Dict[str, RoundResult] = {}
        for bundle in multi_fight_bundle_map.values():
            character_results[bundle.character.name] = RoundResult(
                bundle.character.max_hp,
                bundle.character.hp,
                0.5 * bundle.character.hp,
                [],
                Counter(),
                Counter(),
                Counter(),
                1.0,
            )

        used_utilities_map: Dict[str, Dict[str, int]] = {}
        restore_utilities_map: Dict[str, Set[ItemSchemaExtension]] = {}  # everything except boost utilities

        for character_name, utilities in utilities_map.items():
            if utilities:
                used_utilities_map[character_name] = Counter([u.code for u in utilities if u.is_boost_utility])
                restore_utilities_map[character_name] = {u for u in utilities if not u.is_boost_utility}

        characters_max_hp_sum = 0
        characters_prospecting_sum = 0
        monster_bundle: Optional[GenericFightBundleParticipant] = None
        for fight_bundle in multi_fight_bundle_map.values():
            if not monster_bundle:
                monster_bundle = fight_bundle.monster
            characters_max_hp_sum += fight_bundle.character.max_hp
            characters_prospecting_sum += fight_bundle.character.prospecting

        multi_character_fight = len(multi_fight_bundle_map) > 1

        win_rate_above_0, win_rate_below_100, _, _ = self.should_simulate_fight(multi_fight_bundle_map)
        if (
            not force_simulation
            and not multi_character_fight
            and win_rate_below_100
            and not win_rate_above_0
            and not monster_bundle.corrupted_effect_value
        ):
            return CombatResults.empty_win_rate(
                required_hp=sum(b.character.hp for b in multi_fight_bundle_map.values()),
                fight_bundle=next(iter(multi_fight_bundle_map.values()), None),
            )

        total_rounds = 0
        wins = 0
        losses = 0
        # if force_simulation or (win_rate_below_100 and win_rate_above_0) or monster_bundle.corrupted_effect_value:
        max_rounds = max(min_rounds, 100)
        # else:
        #    max_rounds = 50

        used_restore_utilities: Dict[str, List[Counter[str]]] = defaultdict(list)
        while total_rounds < min_rounds or total_rounds < max_rounds:
            total_rounds += 1
            turn_config = self.__create_turn_config(multi_fight_bundle_map)

            simulation_result = self.__simulate_round(
                multi_fight_bundle_map,
                turn_config,
                restore_utilities_map,
                print_log and total_rounds == 1,
                monster.is_boss_monster,
                multi_character_fight,
            )
            cooldown.append(simulation_result.cooldown)

            for idx, stats in simulation_result.character_stats.items():
                character_results[stats.name].required_hp_list.append(stats.required_hp)
                character_results[stats.name].required_hp_map[stats.required_hp] += 1
                character_results[stats.name].remaining_hp_map[stats.current_hp] += 1
                if simulation_result.characters_win or force_simulation:
                    stats.used_utilities.update(used_utilities_map.get(stats.name, []))
                    used_restore_utilities[stats.name].append(stats.used_utilities)

            if simulation_result.characters_win:
                wins += 1
                turns_to_win.append(simulation_result.turns)
            else:
                losses += 1
                turns_to_lose.append(simulation_result.turns)

            if simulation_result.cooldown <= 5 and total_rounds > 4:
                break

            if not force_simulation and total_rounds > min_rounds and losses > 6:
                break

        win_rate = (wins / total_rounds) * 100

        if print_log:
            logger.info(f'Won {wins} fights out of {total_rounds} rounds ({win_rate:.2f}%).')

        avg_turns_to_win = statistics.mean(turns_to_win) if turns_to_win else 1e6
        avg_turns_to_lose = statistics.mean(turns_to_lose) if turns_to_lose else 1e6
        avg_cooldown = float(np.percentile(cooldown, 90))

        percentiles = []
        required_hp_percent_list = []
        min_required_hp_list: List[int] = []
        max_required_hp_list: List[int] = []
        characters: Dict[str, CharacterResult] = {}
        for character_name, round_result in character_results.items():
            percentile = np.percentile(round_result.required_hp_list, 90)  # 90th percentile of all required hps
            round_result.required_hp_median = math.ceil(percentile)
            percentiles.append(percentile)
            min_required_hp_list.append(min(round_result.required_hp_list))
            max_required_hp_list.append(max(round_result.required_hp_list))
            required_hp_percent_list.append((percentile / round_result.max_hp) * 100)

            character_restore_utilities = Counter()
            if character_name in used_restore_utilities:
                for utilities_round in used_restore_utilities[character_name]:
                    for util_code, util_count in utilities_round.items():
                        character_restore_utilities[util_code] = max(character_restore_utilities[util_code], util_count)

            characters[character_name] = CharacterResult(
                max_hp=round_result.start_hp,
                required_hp_map=round_result.required_hp_map,
                remaining_hp_map=round_result.remaining_hp_map,
                used_utilities=character_restore_utilities,
                required_hp_median=round_result.required_hp_median,
                equipment={},
                equipment_changes=0,
                level=None,
            )
        required_hp_sum = sum(percentiles)
        min_required_hp_sum = sum(min_required_hp_list)
        max_required_hp_sum = sum(max_required_hp_list)
        required_hp_percent_max = max(required_hp_percent_list)

        result = CombatResults(
            win_rate=win_rate,
            turns_to_win=avg_turns_to_win,
            turns_to_lose=avg_turns_to_lose,
            cooldown=avg_cooldown,
            required_hp=required_hp_sum,
            required_hp_percent=required_hp_percent_max,
            min_required_hp=min_required_hp_sum,
            max_required_hp=max_required_hp_sum,
            sample_size=total_rounds,
            monster=monster,
            characters=characters,
            prospecting=characters_prospecting_sum,
            fight_bundle=next(iter(multi_fight_bundle_map.values()), None),
        )
        return result

    def __simulate_round(
        self,
        multi_fight_bundle_map: Dict[str, GenericFightBundle],
        turn_config: Iterator[Tuple[int, str, List[str]]],
        restore_utilities_map: Dict[str, Set[ItemSchemaExtension]] = None,
        print_log: bool = True,
        boss_fight: bool = True,
        multi_character_fight: bool = False,
    ) -> SimulationResult:
        monster_bundle: Optional[GenericFightBundleParticipant] = None
        for b in multi_fight_bundle_map.values():
            monster_bundle = b.monster
            break
        live_stats_map: Dict[str, LiveStats] = {}
        for character_name, character_fight_bundle in multi_fight_bundle_map.items():
            live_stats_map[character_name] = LiveStats(
                character_fight_bundle.character.name,
                character_fight_bundle.character.max_hp,
                character_fight_bundle.character.half_hp,
                character_fight_bundle.character.hp,
            )
            if restore_utilities_map:
                live_stats_map[character_name].restore_utilities = restore_utilities_map.get(character_name, {})
        monster_live_stats = LiveStats(monster_bundle.name, monster_bundle.max_hp)

        character_turns_map = Counter()

        if print_log:
            character_strings = []
            for character_name, character_stats in live_stats_map.items():
                character_strings.append(
                    f'Character {character_name} (Initiative: {multi_fight_bundle_map[character_name].character.initiative}) '
                    f'HP: {character_stats.current_hp}/{character_stats.max_hp}'
                )
            characters_string = ', '.join(character_strings)
            logger.info(
                f'Fight start: {characters_string} vs {monster_live_stats.name} (Initiative: {monster_bundle.initiative}) '
                f'HP: {monster_live_stats.max_hp}/{monster_live_stats.max_hp}'
            )

        # APPLY BARRIER
        # At the start of the fight and every 5 played turns, gain a protective barrier of xHP.
        # All attacks are redirected to this barrier until it is destroyed.
        for character_name, fight_bundle in multi_fight_bundle_map.items():
            if fight_bundle.character.barrier_effect_value:
                live_stats_map[character_name].barrier = fight_bundle.character.barrier_effect_value
                if print_log:
                    logger.info(
                        f'Fight start: {fight_bundle.character.name} raises a barrier of {fight_bundle.character.barrier_effect_value} HP.'
                    )

        if monster_bundle.barrier_effect_value:
            monster_live_stats.barrier = monster_bundle.barrier_effect_value
            if print_log:
                logger.info(f'Fight start: {monster_bundle.name} raises a barrier of {monster_live_stats.barrier} HP.')

        total_turns = 0
        total_character_turns = 0
        total_monster_turns = 0
        character_win: Optional[bool] = None
        for turn, fighter_name, character_opponents in turn_config:
            if total_turns > 100:
                character_win = False
                break

            if fighter_name != '-1':  # character(s) against monster
                if live_stats_map[fighter_name].current_hp > 0:
                    ally_live_stats: Dict[str, LiveStats] = {}
                    for ally_name, ally_stats in live_stats_map.items():
                        if ally_name != fighter_name and ally_stats.current_hp > 0:
                            ally_live_stats[ally_name] = ally_stats
                    total_turns += 1
                    total_character_turns += 1
                    character_turns_map[fighter_name] += 1
                    self.__handle_turn(
                        total_turns=total_turns,
                        attacker_turns=character_turns_map[fighter_name],
                        attacker=multi_fight_bundle_map[fighter_name].character,
                        attacker_live_stats=live_stats_map[fighter_name],
                        ally_live_stats=ally_live_stats,
                        defender=multi_fight_bundle_map[fighter_name].monster,
                        defender_live_stats=monster_live_stats,
                        defenders_ally_live_stats={},
                        multi_character_fight=multi_character_fight,
                        boss_fight=boss_fight,
                        print_log=print_log,
                    )
            else:  # monster
                total_turns += 1
                total_monster_turns += 1
                for defender_name in character_opponents:
                    if live_stats_map[defender_name].current_hp > 0:
                        defenders_ally_live_stats: Dict[str, LiveStats] = {}
                        for ally_name, ally_stats in live_stats_map.items():
                            if ally_name != defender_name and ally_stats.current_hp > 0:
                                defenders_ally_live_stats[ally_name] = ally_stats
                        self.__handle_turn(
                            total_turns=total_turns,
                            attacker_turns=total_monster_turns,
                            attacker=multi_fight_bundle_map[defender_name].monster,
                            attacker_live_stats=monster_live_stats,
                            ally_live_stats={},
                            defender=multi_fight_bundle_map[defender_name].character,
                            defender_live_stats=live_stats_map[defender_name],
                            defenders_ally_live_stats=defenders_ally_live_stats,
                            multi_character_fight=multi_character_fight,
                            boss_fight=boss_fight,
                            print_log=print_log,
                        )
                        break

            if monster_live_stats.current_hp <= 0:
                character_win = True
                break

            if all(c.current_hp <= 0 for c in live_stats_map.values()):
                character_win = False
                break

        if character_win is None:
            character_win = False

        if print_log:
            character_strings = []
            for character_name, character_stats in live_stats_map.items():
                character_strings.append(f'Character {character_name} HP: {character_stats.current_hp}/{character_stats.max_hp}')
            characters_string = ', '.join(character_strings)
            logger.info(
                f'Fight result: {"win" if character_win else "lose"}. '
                f'{characters_string} vs {monster_bundle.name} '
                f'HP: {monster_live_stats.current_hp}/{monster_live_stats.max_hp}'
            )

        min_haste_value = max(fight_bundle.character.haste_value for fight_bundle in multi_fight_bundle_map.values())
        cooldown = max(round(total_turns * 2 - min_haste_value * (total_turns * 2)), 5)

        for character_name, live_stats in live_stats_map.items():
            required_hp = min(live_stats.max_hp, live_stats.start_hp - min(live_stats.lowest_hp, live_stats.current_hp))

            if required_hp < 1 and len(multi_fight_bundle_map) == 1:
                if monster_bundle.critical_strike_chance > 0:
                    required_hp = sum(multi_fight_bundle_map[character_name].monster.element_critical_attacks.values())
                else:
                    required_hp = sum(multi_fight_bundle_map[character_name].monster.element_basic_attacks.values())
            live_stats.required_hp = required_hp

        return SimulationResult(
            character_win,
            total_turns,
            cooldown,
            live_stats_map,
            monster_live_stats.critical_hits,
            monster_live_stats.standard_hits,
        )

    def __handle_turn(
        self,
        attacker: GenericFightBundleParticipant,
        attacker_live_stats: LiveStats,
        ally_live_stats: Dict[str, LiveStats],
        defender: GenericFightBundleParticipant,
        defender_live_stats: LiveStats,
        defenders_ally_live_stats: Dict[str, LiveStats],
        attacker_turns: int,
        total_turns: int,
        multi_character_fight: bool,
        boss_fight: bool,
        print_log: bool,
    ):
        rand = self.rng.random
        attacker_crit_chance = attacker.critical_strike_chance

        # Handle effect 'protective_bubble'
        if attacker.protective_bubble_effect_value:
            current_element = next(iter(attacker_live_stats.res_modifiers.keys()), 'None')
            res_elements = [e for e in ELEMENTS if e != current_element]
            res_element = random.choice(res_elements)
            attacker_live_stats.res_modifiers = {res_element: attacker.protective_bubble_effect_value}
            if print_log:
                logger.info(
                    f"Turn {total_turns}: {attacker.name}'s Protective Bubble shifts from {current_element} to {res_element}, "
                    f'gaining {attacker.protective_bubble_effect_value}% {res_element} resistance until the end of the round.'
                )

        # Suffer from effect 'poison'
        if attacker_live_stats.poisoned > 0:
            for utility in attacker_live_stats.restore_utilities:
                antipoison = utility.item_effects.get('antipoison', 0)
                if antipoison:
                    attacker_live_stats.poisoned = max(0, attacker_live_stats.poisoned - antipoison)
                    attacker_live_stats.used_utilities[utility.code] += 1

                    if print_log:
                        logger.info(
                            f'Turn {total_turns}: {attacker.name} used {utility.name} and removed {antipoison} poison. '
                            f'({attacker.name} poison: {attacker_live_stats.poisoned})'
                        )

            if attacker_live_stats.poisoned:
                attacker_live_stats.current_hp -= attacker_live_stats.poisoned
                if print_log:
                    logger.info(
                        f'Turn {total_turns}: {attacker.name} suffers from poison and loses {attacker_live_stats.poisoned} HP. '
                        f'({attacker.name} HP: {attacker_live_stats.current_hp}/{attacker_live_stats.max_hp})'
                    )
                if attacker_live_stats.current_hp <= 0:
                    if print_log:
                        logger.info(f'Turn {total_turns}: {attacker.name} has been defeated!')
                    return

        # Consume utilities below 50% hp
        if attacker_live_stats.restore_utilities:
            if attacker_live_stats.current_hp < attacker.half_hp:
                for utility in attacker_live_stats.restore_utilities:
                    if utility.item_effects.get('restore', 0) > 0:
                        attacker_live_stats.lowest_hp = min(attacker_live_stats.lowest_hp, attacker_live_stats.current_hp)
                        restore_value = utility.item_effects.get('restore')
                        attacker_live_stats.current_hp = min(attacker_live_stats.max_hp, attacker_live_stats.current_hp + restore_value)
                        attacker_live_stats.used_utilities[utility.code] += 1
                        if print_log:
                            logger.info(
                                f'Turn {total_turns}: {attacker.name} uses {utility.code} and restores {restore_value} HP. '
                                f'({attacker.name} HP: {attacker_live_stats.current_hp}/{attacker_live_stats.max_hp})'
                            )

            # Process splash_restore utilities
            # if multicharacter fight and item is splash_restore and ally (not self) is below 50%
            if multi_character_fight:
                if any(ally.current_hp < ally.half_hp for ally in ally_live_stats.values()):
                    for utility in attacker_live_stats.restore_utilities:
                        if utility.item_effects.get('splash_restore', 0) > 0:
                            for ally in ally_live_stats.values():
                                if ally.current_hp < ally.half_hp:
                                    ally.lowest_hp = min(ally.lowest_hp, ally.current_hp)
                                    restore_value = utility.item_effects.get('splash_restore')
                                    ally.current_hp = min(ally.max_hp, ally.current_hp + restore_value)
                                    attacker_live_stats.used_utilities[utility.code] += 1
                                    if print_log:
                                        logger.info(
                                            f'Turn {total_turns}: {attacker.name} uses {utility.code} and splash restores '
                                            f'{restore_value} HP of {ally.name}. '
                                            f'({ally.name} HP: {ally.current_hp}/{ally.max_hp})'
                                        )
                                    break

        # Suffer from effect 'burn'
        if attacker_live_stats.burned and len(attacker_live_stats.burned) >= attacker_turns:
            burn_damage = attacker_live_stats.burned[attacker_turns - 1]
            attacker_live_stats.current_hp -= burn_damage
            if print_log:
                logger.info(
                    f'Turn {total_turns}: {attacker.name} suffers from burn and loses {burn_damage} HP. '
                    f'({attacker.name} HP: {attacker_live_stats.current_hp}/{attacker_live_stats.max_hp})'
                )
            if attacker_live_stats.current_hp <= 0:
                if print_log:
                    logger.info(f'Turn {total_turns}: {attacker.name} has been defeated!')
                return

        # Process 'healing' effect
        if attacker.healing_effect_value_per_instance > 0 and attacker_turns % 3 == 0:
            attacker_live_stats.lowest_hp = min(attacker_live_stats.lowest_hp, attacker_live_stats.current_hp)
            healed_hp = attacker.healing_effect_value_per_instance
            attacker_live_stats.current_hp = min(attacker_live_stats.max_hp, attacker_live_stats.current_hp + healed_hp)

            if print_log:
                logger.info(
                    f'Turn {total_turns}: {attacker.name} heals {healed_hp} HP. '
                    f'({attacker.name} HP: {attacker_live_stats.current_hp}/{attacker_live_stats.max_hp})'
                )

        # Process 'barrier' effect
        if attacker.barrier_effect_value and attacker_turns % 5 == 0:
            attacker_live_stats.barrier = attacker.barrier_effect_value
            if print_log:
                logger.info(f'Turn {total_turns}: {attacker.name} refreshes its barrier to {attacker.barrier_effect_value} HP.')

        # Process 'burn' effect / apply to opponent
        if attacker_turns == 1:
            if attacker.initial_burn_from_participant:
                defender_live_stats.burned = attacker.burn_from_participant
                if print_log:
                    logger.info(
                        f'Turn {total_turns}: {attacker.name} applies a burn of {attacker.burn_from_participant[0]} on {defender.name}. '
                        f'({defender.name} burn: {defender_live_stats.burned[0]})'
                    )

            # APPLY POISON
            if attacker.poison_effect_value:
                defender_live_stats.poisoned = attacker.poison_effect_value
                if print_log:
                    logger.info(
                        f'Turn {total_turns}: {attacker.name} applies a poison of {attacker.poison_effect_value} on {defender.name}. '
                        f'({defender.name} poison: {attacker.poison_effect_value})'
                    )

        # RECONSTITUTION
        if attacker.reconstitution_effect_value and attacker.reconstitution_effect_value == attacker_turns:
            attacker_live_stats.current_hp = attacker_live_stats.max_hp

            if print_log:
                logger.warning(
                    f'Turn {total_turns}: {attacker.name} use reconstitution to heals to max HP. '
                    f'({attacker.name} HP: {attacker_live_stats.current_hp}/{attacker_live_stats.max_hp})'
                )

        # APPLY BERSERKER RAGE (only sandwhisper_empress, lvl 50)
        # When they drop below 25% HP, they gain x% damage permanently. Applies once per combat.
        if (
            attacker.berserker_rage_effect_value
            and attacker_live_stats.current_hp < 0.25 * attacker_live_stats.max_hp
            and not attacker_live_stats.berserked
        ):
            attacker_live_stats.berserked = True
            attacker_live_stats.dmg_modifiers['berserker_rage'] = stats_iterator(attacker.berserker_rage_effect_value)
            if print_log:
                logger.info('Attacker entered berserker rage!')

        # CRITICAL STRIKE
        is_critical_attack = rand() < attacker_crit_chance
        is_shell_active = defender_live_stats.shell_turns_left
        if is_shell_active:
            defender_live_stats.shell_turns_left -= 1
        dealt_critical_damage = 0

        total_dmg_modifier = 0
        for dmg_modifier in attacker_live_stats.dmg_modifiers.values():
            total_dmg_modifier += next(dmg_modifier)

        if total_dmg_modifier != 0 or defender_live_stats.res_modifiers:
            attack_map = {}

            for element, attack in attacker.attack_elem.items():
                if attack > 0:
                    gross_attack = self_round(attack * (1 + attacker.dmg_elem.get(element, 0) * 0.01 + total_dmg_modifier))
                    net_attack = self_round(
                        gross_attack * (1 - (defender.res_elem.get(element, 0) + defender_live_stats.res_modifiers.get(element, 0)) * 0.01)
                    )
                    if is_critical_attack:
                        attack_map[element] = self_round(1.5 * net_attack)
                    else:
                        attack_map[element] = net_attack
        else:
            if is_critical_attack:
                attack_map = attacker.element_critical_shelled_attacks if is_shell_active else attacker.element_critical_attacks
            else:
                attack_map = attacker.element_basic_shelled_attacks if is_shell_active else attacker.element_basic_attacks
        if is_critical_attack:
            attacker_live_stats.critical_hits += 1
        else:
            attacker_live_stats.standard_hits += 1

        # ATTACK
        for element, attack in attack_map.items():
            if defender_live_stats.barrier > 0:
                applied_damage = min(attack, defender_live_stats.barrier)
                defender_live_stats.barrier -= applied_damage
                if print_log:
                    if attack == applied_damage:
                        logger.info(
                            f'Turn {total_turns}: {attacker.name} used {element} attack and dealt {attack} damage, fully '
                            f'absorbed by the barrier. {defender.name} HP: {defender_live_stats.current_hp}/{defender_live_stats.max_hp}'
                        )
                    else:
                        logger.info(
                            f'Turn {total_turns}: {attacker.name} used {element} attack and dealt {attack} damage ({applied_damage} absorbed, '
                            f'{attack - applied_damage} through). '
                            f'{defender.name} HP: {defender_live_stats.current_hp}/{defender_live_stats.max_hp}'
                        )

                    logger.info(
                        f"Turn {total_turns}: {defender.name}'s barrier absorbs {applied_damage} damage. "
                        f'Barrier HP: {defender_live_stats.barrier}'
                    )
                    if defender_live_stats.barrier == 0:
                        logger.info(f"Turn {total_turns}: {defender.name}'s barrier is destroyed!")

                attack -= applied_damage

            if attack > 0:
                if defender_live_stats.redirect_guard_name:
                    if defender_live_stats.redirect_guard_name not in defenders_ally_live_stats:
                        logger.error(
                            f'Expected key {defender_live_stats.redirect_guard_name} in defenders_ally_live_stats '
                            f'but got {defenders_ally_live_stats.keys()}'
                        )
                    ally_live_stat = defenders_ally_live_stats[defender_live_stats.redirect_guard_name]
                    redirect_attack = self_round(defender_live_stats.redirect_factor * attack)
                    attack -= redirect_attack
                    ally_live_stat.current_hp -= redirect_attack
                    if print_log:
                        logger.info(
                            f'Turn {total_turns}: {attacker.name} redirected {element} attack and dealt {attack} damage'
                            f'{" (Critical strike)" if is_critical_attack else ""}. '
                            f'(Guard: {defender_live_stats.redirect_guard_name} HP: {ally_live_stat.current_hp}/{ally_live_stat.max_hp})'
                        )

                defender_live_stats.current_hp -= attack
                if is_critical_attack:
                    dealt_critical_damage += attack
                if print_log:
                    logger.info(
                        f'Turn {total_turns}: {attacker.name} used {element} attack and dealt {attack} damage'
                        f'{" (Critical strike)" if is_critical_attack else ""}. '
                        f'({defender.name} HP: {defender_live_stats.current_hp}/{defender_live_stats.max_hp})'
                    )

                if attack > 0 and defender.corrupted_effect_value:
                    attacker.element_critical_attacks[element] = attacker.element_critical_attacks_corrupted_series[attacker_turns][element]
                    attacker.element_basic_attacks[element] = attacker.element_basic_attacks_corrupted_series[attacker_turns][element]

                    if print_log:
                        logger.info(
                            f"Turn {total_turns}: {defender.name}'s {element} resistance is corrupted and decreases by "
                            f'{defender.corrupted_effect_value}%. New resistance: {attacker.element_corrupted_series[attacker_turns][element]}%',
                        )

        if defender_live_stats.current_hp <= 0:
            if print_log:
                logger.info(f'Turn {total_turns}: {defender.name} has been defeated!')
            return

        # APPLY LIFESTEAL
        if attacker.lifesteal_effect_value and is_critical_attack:
            attacker_live_stats.lowest_hp = min(attacker_live_stats.lowest_hp, attacker_live_stats.current_hp)
            lifesteal_hp = self_round(attacker.lifesteal_effect_value * dealt_critical_damage)
            attacker_live_stats.current_hp = min(attacker_live_stats.max_hp, attacker_live_stats.current_hp + lifesteal_hp)
            if print_log:
                logger.info(
                    f'Turn {total_turns}: {attacker.name} used lifesteal and healed {lifesteal_hp} HP. '
                    f'({attacker.name} HP: {attacker_live_stats.current_hp}/{attacker_live_stats.max_hp})'
                )

        # APPLY FRENZY (lvl 40, greater_lifesteal_rune and vampiric_rune)
        # Each time they land a critical hit, they give x% damage to themselves and their allies until the end of their next turn.
        if attacker.frenzy_effect_value and is_critical_attack:
            attacker_live_stats.dmg_modifiers['frenzy'] = stats_iterator(attacker.frenzy_effect_value, 1)
            for live_stats in ally_live_stats.values():
                live_stats.dmg_modifiers['frenzy'] = stats_iterator(attacker.frenzy_effect_value, 1)

            if print_log:
                logger.info(
                    f"Turn {total_turns}: {attacker.name}'s Frenzy triggers on critical. +{int(attacker.frenzy_effect_value * 100)}% "
                    f"damage will apply on each ally's next turn, active until the end of {attacker.name}'s next turn."
                )

        # APPLY VOID DRAIN (duskworm, lvl 48)
        # Every 4 turns, Drains x% HP from each enemy to heal themselves.
        if attacker.void_drain_effect_value and attacker_turns % 4 == 0:
            attacker_live_stats.lowest_hp = min(attacker_live_stats.lowest_hp, attacker_live_stats.current_hp)
            healed_hp = 0
            for opponent in [defender_live_stats]:
                drained_hp = min(opponent.max_hp * attacker.void_drain_effect_value, opponent.current_hp)
                opponent.current_hp -= drained_hp
                opponent.lowest_hp = min(opponent.lowest_hp, opponent.current_hp)
                healed_hp += drained_hp

            attacker_live_stats.current_hp = min(attacker_live_stats.max_hp, attacker_live_stats.current_hp + healed_hp)

            if print_log:
                logger.info(f'Turn {total_turns}: {attacker.name} used void_drain to heal {healed_hp} HP.')

        if boss_fight:
            # Shell effect
            # When they drop below 40% of their HP, they gain x% resistance to all elements for 3 turns.
            # Activates once per combat. This effect is only active during boss fights.
            if (
                attacker.shell_effect_value
                and (attacker_live_stats.current_hp < 0.4 * attacker_live_stats.max_hp)
                and not attacker_live_stats.shelled
            ):
                attacker_live_stats.shelled = True
                attacker_live_stats.shell_turns_left = 3
                if print_log:
                    logger.info(
                        f'Turn {total_turns}: {attacker.name} activated shell. '
                        f'({attacker.name} HP: {attacker_live_stats.current_hp}/{attacker_live_stats.max_hp})'
                    )

        if multi_character_fight:
            if attacker.healing_aura_effect_value and ally_live_stats and attacker_turns % 2 == 0:
                for ally_name, live_stats in ally_live_stats.items():
                    if live_stats.current_hp < live_stats.max_hp:
                        healing_aura_hp = self_round(attacker.healing_aura_effect_value * live_stats.max_hp)
                        live_stats.current_hp = min(live_stats.max_hp, live_stats.current_hp + healing_aura_hp)
                        if print_log:
                            logger.info(
                                f'Turn {total_turns}: {attacker.name} used healing aura and healed {ally_name} for {healing_aura_hp} HP. '
                                f'({ally_name} HP: {live_stats.current_hp}/{live_stats.max_hp})'
                            )

            # APPLY VAMPIRIC STRIKE (lvl 40, only vampiric_rune)
            # After landing a critical hit, they heal the ally with the lowest HP for x% of the damage dealt.
            # Can only trigger once every 3 turns.
            # This effect does not heal the caster.
            if (
                attacker.vampiric_strike_effect_value
                and dealt_critical_damage
                and ally_live_stats
                and attacker_turns > attacker_live_stats.last_vampiric_strike_turn + 2
            ):
                lowest_hp_ally = min(ally_live_stats.values(), key=lambda x: x.current_hp)
                if lowest_hp_ally.current_hp < lowest_hp_ally.max_hp:
                    healing_hp = self_round(attacker.vampiric_strike_effect_value * dealt_critical_damage)
                    lowest_hp_ally.current_hp = min(lowest_hp_ally.max_hp, lowest_hp_ally.current_hp + healing_hp)
                    attacker_live_stats.last_vampiric_strike_turn = attacker_turns
                    if print_log:
                        logger.info(
                            f"Turn {total_turns}: {attacker.name}'s vampiric_strike heals {lowest_hp_ally.name} for {healing_hp} HP. "
                            f'({lowest_hp_ally.name} HP: {lowest_hp_ally.current_hp}/{lowest_hp_ally.max_hp})'
                        )

            # APPLY GUARD (lvl 40, only greater_protection_rune)
            # If one or more allies have less than 50% of their HP, protects the ally with the lowest HP percentage,
            # redirecting x% of their damage to this character until the start of my next turn.
            # Activates a maximum of 3 times per combat.
            if attacker.guard_effect_value and ally_live_stats and attacker_live_stats.guard_charges:
                lowest_percentage = 1.0
                lowest_name = ''
                for ally in ally_live_stats.values():
                    percentage = ally.current_hp / ally.max_hp
                    if 0 < percentage < lowest_percentage:
                        lowest_percentage = percentage
                        lowest_name = ally.name
                if lowest_percentage < 0.5:
                    ally = ally_live_stats[lowest_name]
                    if not ally.redirect_guard_name:
                        ally.redirect_guard_name = attacker.name
                        ally.redirect_factor = attacker.guard_effect_value
                        attacker_live_stats.guard_charges -= 1
                        if print_log:
                            logger.info(
                                f"Turn {total_turns}: {attacker.name}'s guard directs {attacker.guard_effect_value * 100}% "
                                f'of damage applied to {ally.name} until the next turn. '
                                f'({ally.name} HP: {ally.current_hp}/{ally.max_hp})'
                            )
        if defender_live_stats.redirect_guard_name:
            defender_live_stats.redirect_guard_name = ''

    @staticmethod
    def __create_turn_config(fight_bundles: Dict[str, GenericFightBundle]) -> Iterator[Tuple[int, str, List[str]]]:
        # Build attacker and defender lists
        attackers = [
            {
                'index': '-1',
                'initiative': next(iter(fight_bundles.values())).monster.initiative,
                'current_hp': next(iter(fight_bundles.values())).monster.max_hp,
            }
        ]
        defenders = []

        for character_name, bundle in fight_bundles.items():
            attackers.append({'index': character_name, 'initiative': bundle.character.initiative, 'current_hp': bundle.character.hp})
            defenders.append({'index': character_name, 'threat': bundle.character.threat, 'current_hp': bundle.character.hp})

        # Randomize and sort
        random.shuffle(attackers)
        random.shuffle(defenders)

        sorted_attackers = [char['index'] for char in sorted(attackers, key=lambda c: (-c['initiative'], -c['current_hp']))]
        sorted_defenders = [char['index'] for char in sorted(defenders, key=lambda c: (-c['threat'], c['current_hp']))]

        # Cycle through attackers
        attacker_cycle = cycle(sorted_attackers)

        for turn_number, attacker_name in enumerate(attacker_cycle, start=1):
            targets = sorted_defenders if attacker_name == '-1' else []
            yield turn_number, attacker_name, targets

    @staticmethod
    def should_simulate_fight(multi_fight_bundle: Dict[str, GenericFightBundle]):
        crit_chance_multiplier: float = 2

        c_hp = 0
        c_total_crit_dmg = 0
        c_total_basic_dmg = 0
        c_crit_chance = 0

        m_hp = 0
        m_total_crit_dmg = 0
        m_total_basic_dmg = 0
        m_crit_chance = 0
        monster_bundle: Optional[GenericFightBundleParticipant] = None
        for fight_bundle in multi_fight_bundle.values():
            if monster_bundle is None:
                monster_bundle = fight_bundle.monster
            c_hp += fight_bundle.character.hp
            c_total_crit_dmg += sum(fight_bundle.character.element_critical_attacks.values())
            c_total_basic_dmg += sum(fight_bundle.character.element_basic_attacks.values())
            c_crit_chance += min(1.0, crit_chance_multiplier * fight_bundle.character.critical_strike_chance)

            m_hp += fight_bundle.monster.hp
            m_total_crit_dmg += sum(fight_bundle.monster.element_critical_attacks.values())
            m_total_basic_dmg += sum(fight_bundle.monster.element_basic_attacks.values())
            m_crit_chance += min(1.0, crit_chance_multiplier * fight_bundle.monster.critical_strike_chance)

        c_crit_chance /= len(multi_fight_bundle)
        c_avg_dmg = max(5, c_crit_chance * c_total_crit_dmg + (1 - c_crit_chance) * c_total_basic_dmg)
        if monster_bundle.barrier_effect_value:
            c_avg_dmg = max(1, c_avg_dmg - monster_bundle.barrier_effect_value * 0.2)

        m_crit_chance /= len(multi_fight_bundle)
        m_avg_dmg = max(1, m_crit_chance * m_total_crit_dmg + (1 - m_crit_chance) * m_total_basic_dmg)

        if monster_bundle.poison_effect_value:
            m_avg_dmg += monster_bundle.poison_effect_value

        rounds_to_win = (m_hp // c_avg_dmg) - 3
        rounds_to_lose = c_hp // m_avg_dmg

        for fight_bundle in multi_fight_bundle.values():
            if fight_bundle.character.initial_burn_from_participant:
                rounds_to_win -= 2
            if fight_bundle.monster.initial_burn_from_participant:
                rounds_to_lose -= 2

        if rounds_to_lose > monster_bundle.reconstitution_effect_value > 0:
            rounds_to_lose = monster_bundle.reconstitution_effect_value

        return rounds_to_win <= rounds_to_lose, rounds_to_win + 10 > rounds_to_lose, rounds_to_win, rounds_to_lose

    @staticmethod
    def __log_round_result(simulation_result: SimulationResult):
        text = (
            f'{simulation_result.character_stats["Character"].critical_hits},'
            f'{simulation_result.character_stats["Character"].critical_hits + simulation_result.character_stats["Character"].standard_hits},'
            f'{simulation_result.monster_critical_hits},'
            f'{simulation_result.monster_critical_hits + simulation_result.monster_standard_hits},'
            f'{simulation_result.characters_win}'
        )
        file_name = 'fight.csv'

        with open(file_name, 'a') as file:
            file.write(text + '\n')
