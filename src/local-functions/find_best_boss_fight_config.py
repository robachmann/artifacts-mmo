from collections import Counter, defaultdict
import json
from typing import Dict, List

from local_environment import LocalEnvironment
from matplotlib.offsetbox import AnchoredText
import matplotlib.pyplot as plt
import numpy as np

from artifactsmmo import game_constants
from artifactsmmo.extensions import CharacterSchemaExtension, MonsterSchemaExtension
from artifactsmmo.fights.combat_result import CombatResults
from artifactsmmo.fights.equipment_assembler import EquipmentScope
from artifactsmmo.log.logger import logger
from artifactsmmo.models import CraftSkill, FakeCharacterSchema


class ReportFunction(LocalEnvironment):
    def handler(self):
        characters = {c.name: c for c in self.service.get_all_character_details()}
        leader = self.character_1_name
        participants = [self.character_2_name, self.character_3_name]
        fight_characters: List[CharacterSchemaExtension] = [characters[leader]]
        for participant in participants:
            fight_characters.append(characters[participant])
        skill_map = self.service.get_skill_map(characters=list(characters.values()))
        # for character in fight_characters:
        #    character.level = 35

        # skill_map[CraftSkill.GEARCRAFTING] = 35
        # skill_map[CraftSkill.WEAPONCRAFTING] = 35
        # skill_map[CraftSkill.JEWELRYCRAFTING] = 35

        # bank_items_map = self.service.get_bank_items_map()
        # bank_items_map.update({'hork_helmet': 1, 'obsidian_armor': 1, 'white_knight_armor': 1, 'wrathsword': 1, 'malefic_armor': 1})

        monster = self.service.get_monster('rosenblood')
        raw_results: List[CombatResults] = []

        best_result = self.fight_simulator.find_best_multi_character_fight_config(
            # bank_items_map=bank_items_map,
            monster=monster,
            characters=fight_characters,
            exclude_drops_from_monsters=[ ],
            exclude_items_if_unavailable=[
                # 'sapphire_book',
                # 'ruby_book',
                # 'greater_healing_rune',
                'corrupted_skull',
                'corrupted_crown',
                'diamond',
                'diamond_stone',
                # 'diamond_sword',
                # 'cursed_sceptre',
                # 'diamond_amulet',
                'malefic_crystal',
                # 'rosenblood_elixir',
                'greater_healing_rune',
                'greater_protection_rune',
                #'sandwhisper_coin',
                # 'topaz_book',
                # # 'mithril_bar',
                'life_crystal',
                # 'magical_cure',
                # 'astralyte_crystal',
                'sapphire_book',
                'topaz_book',
                'ruby_book',
            ],
            exclude_items=[
                'enchanted_boost_potion',
                # 'greater_health_potion',
                'earth_res_potion',
                'air_res_potion',
                'fire_res_potion',
                'water_res_potion',
                'health_boost_potion',
                'diabolic_elixir',
            ],
            include_items=[],
            equipment_scope=EquipmentScope.CRAFTABLE_AND_MONSTER_DROPS,
            utility_scope=EquipmentScope.AVAILABLE,
            skill_map=skill_map,
            raw_results=raw_results,
            force_utilities=False,
            # include_runes=False,
        )

        if best_result.character_wins:
            for idx, resu in best_result.characters.items():
                res = self.food_service.get_best_food_to_withdraw(
                    character=characters[idx],
                    required_hp=resu.required_hp_median,
                    lost_hps_per_fight=list(resu.required_hp_map.keys()),
                    fight_times=100,
                    is_event_monster=monster.is_event_monster,
                    is_boss_monster=monster.is_boss_monster,
                    # task_id=task.task_id,
                    # context=context,
                )

        # win_results = [r for r in raw_results if r.character_wins]
        # self.plot_raw_results(win_results, fight_configs, monster, y_axis='gather_time')  # use one of: win_rate, gather_time, cooldown

        self.fight_simulator.print_fight_config(best_result, {})

        simulator_json = best_result.format_simulator_json()
        logger.info(f'Use this json at https://simulator.artifactsmmo.com/: {simulator_json}')

        self.plot_raw_results(raw_results, best_result, monster, color_by='prospecting')
        # if best_result.character_wins:
        #    self.print_simulation(fight_characters, best_result, monster)

    def process_100(self, combat_results: List[CombatResults], character: CharacterSchemaExtension):
        best_result = None
        best_drop_rate = None
        bank_items_map = self.service.get_bank_items_map()
        global_quantity_map = self.service.get_global_quantity_map(bank_items_map=bank_items_map)
        for result in combat_results:
            for c in result.characters.values():
                missing_parts: Dict[str, int] = self.get_missing_parts(list(c.equipment.values()), global_quantity_map)
                resolved_recipe, immediately_craftable = self.service.resolve_recipes(recipe_map=missing_parts, bank_items_map=bank_items_map)

                drop_rate = 0
                for item_code, item_qty in resolved_recipe.missing_items.items():
                    drop_rates = self.service.get_drop_rates(item_code=item_code)
                    for rate in drop_rates:
                        drop_rate += rate.drop_rate_avg * item_qty
                        break

                if not best_drop_rate or drop_rate < best_drop_rate:
                    best_drop_rate = drop_rate
                    best_result = result
                    if best_drop_rate == 0:
                        break

        character_equipment = defaultdict(int)
        for gear_position in game_constants.GEAR_POSITIONS:
            slot_item = character.equipment.get(gear_position)
            if slot_item:
                character_equipment[slot_item] += 1

        logger.info(f'Best result with drop_rate={best_drop_rate}')
        self.fight_simulator.print_fight_config(best_result, character_equipment, character_name=character.name)

    @staticmethod
    def get_missing_parts(param: List[str], global_quantity_map: Dict[str, int]) -> Dict[str, int]:
        counter_map = Counter(param)
        missing_parts: Dict[str, int] = {}
        for key, value in counter_map.items():
            missing_count = value - global_quantity_map.get(key, 0)
            if missing_count > 0:
                missing_parts[key] = missing_count
        return missing_parts

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

    def print_simulation(self, character: CharacterSchemaExtension, best_result: CombatResults, monster: MonsterSchemaExtension):
        characters: List[FakeCharacterSchema] = []
        for character_name, character_result in best_result.characters.items():
            character_dict: Dict[str, str | int] = {f'{k}_slot': v for k, v in character_result.equipment.items()}
            for idx, k, v in enumerate(character_result.used_utilities.items(), 1):
                character_dict[f'utility{idx}_slot'] = k
                character_dict[f'utility{idx}_slot_quantity'] = v
            character_dict['level'] = character.level
            characters.append(FakeCharacterSchema.from_dict(character_dict))
        result = self.client.simulate_fight(characters, monster.code)
        logger.info(f'Simulation Results: Winrate: {result.winrate}%, Wins: {result.wins}, Losses: {result.losses}')
        logger.info(f'Logs: {"\n".join(result.results[0].logs)}')


report_function = ReportFunction()


if __name__ == '__main__':
    report_function.handler()
