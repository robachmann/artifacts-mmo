from collections import Counter, defaultdict
from copy import copy
import csv
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
from artifactsmmo.game_constants import GEAR_POSITIONS
from artifactsmmo.log.logger import logger
from artifactsmmo.models import CraftSkill, FakeCharacterSchema


class ReportFunction(LocalEnvironment):
    def handler(self):
        characters = {c.name: c for c in self.service.get_all_character_details()}
        skill_map = self.service.get_skill_map(characters=list(characters.values()))
        character = characters[self.character_1_name]
        # skill_map[CraftSkill.GEARCRAFTING] = 45
        # skill_map[CraftSkill.WEAPONCRAFTING] = 44
        # skill_map[CraftSkill.JEWELRYCRAFTING] = 45
        # character.level = 30

        monster = self.service.get_monster('sea_marauder')
        # exclude_monsters = [m.code for m in self.service.get_monsters_by_level(monster.level)]
        raw_results: List[CombatResults] = []
        best_result = self.fight_simulator.print_best_fight_config(
            monster=monster,
            character=character,
            exclude_drops_from_monsters=[],
            exclude_items_if_unavailable=[
                'sandwhisper_codex',
                'desert_wrap',
                ## sandwhisper_coin items ##
                'greater_healing_rune',
                'greater_lifesteal_rune',
                'greater_protection_rune',
                'vampiric_rune',
                ## utilities ##
                'diabolic_elixir',
            ],
            exclude_items=[],
            include_items=[],
            equipment_scope=EquipmentScope.CRAFTABLE_AND_MONSTER_DROPS,
            utility_scope=EquipmentScope.CRAFTABLE_AND_MONSTER_DROPS,
            skill_map=skill_map,
            raw_results=raw_results,
            force_utilities=False,
        )

        if any(r.character_wins for r in raw_results):
            win_results = [r for r in raw_results if r.character_wins]
            if any(r.rounded_result.win_rate == 100 for r in raw_results):
                all_wins = [r for r in raw_results if r.rounded_result.win_rate == 100]
                self.find_cheapest_option(all_wins, list(characters.values()))

            bank_items_map = self.service.get_bank_items_map()
            self.write_csv(monster.code, win_results, bank_items_map, 2)
        elif any(r.rounded_result.win_rate > 0 for r in raw_results):
            win_results = [r for r in raw_results if r.rounded_result.win_rate > 0]
        else:
            win_results = raw_results

        self.plot_raw_results(win_results, best_result, monster, y_axis='gather_time')  # use one of: win_rate, gather_time, cooldown
        # self.plot_raw_results(raw_results, best_result, monster, color_by='prospecting')

        # if best_result.character_wins:
        #    self.print_simulation(character, best_result, monster)

    def find_cheapest_option(self, all_wins: List[CombatResults], characters: List[CharacterSchemaExtension]):
        bank_items_map_orig = self.service.get_global_quantity_map()
        bank_items_map = copy(bank_items_map_orig)
        results = []
        for result in all_wins:
            recipe_map = defaultdict(int)
            for character_equipment in result.characters.values():
                if character_equipment.equipment:
                    for item_code in character_equipment.equipment.values():
                        recipe_map[item_code] += 1

            missing_items = {}
            for item_code, item_qty in recipe_map.items():
                missing_qty = max(0, item_qty - bank_items_map.get(item_code, 0))
                if missing_qty > 0:
                    missing_items[item_code] = missing_qty

            resolved_recipe, immediately_craftable_recipes = self.service.resolve_recipes(missing_items, bank_items_map)
            missing_parts = 0
            for item_code, item_qty in resolved_recipe.missing_items.items():
                missing_parts += item_qty

            results.append(
                dict(
                    equipment=recipe_map,
                    missing_parts=missing_parts,
                    gather_time=result.gather_time,
                    missing_recipes=missing_items,
                )
            )

        results.sort(key=lambda x: (x['missing_parts'], x['gather_time']))
        cheapest_result = results[0]
        logger.info(f'Cheapest result: {cheapest_result}')

    def process_100(self, combat_results: List[CombatResults], character: CharacterSchemaExtension):
        best_result = None
        best_drop_rate = None
        bank_items_map = self.service.get_bank_items_map(ignore_reservations=True)
        global_quantity_map = self.service.get_global_quantity_map(bank_items_map=bank_items_map)
        for result in combat_results:
            missing_parts: Dict[str, int] = self.get_missing_parts(
                list(list(result.characters.values())[0].equipment.values()), global_quantity_map
            )
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
        results: List['CombatResults'],
        best_result: 'CombatResults',
        monster: 'MonsterSchemaExtension',
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
            f'Win Rate: {best_result.raw_result.win_rate:.2f} % {"" if best_result.character_wins else " ⚠"}',
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
        for character_name, character_result in best_result.characters.items():
            character_dict: Dict[str, str | int] = {f'{k}_slot': v for k, v in character_result.equipment.items()}
            for idx, (k, v) in enumerate(character_result.used_utilities.items(), 1):
                character_dict[f'utility{idx}_slot'] = k
                character_dict[f'utility{idx}_slot_quantity'] = v
            character_dict['level'] = character.level

            characters = [FakeCharacterSchema.from_dict(character_dict)]
            result = self.client.simulate_fight(characters, monster.code)
            logger.info(f'Simulation Results: Winrate: {result.winrate}%, Wins: {result.wins}, Losses: {result.losses}')
            logger.info(f'Logs: {"\n".join(result.results[0].logs)}')

    def write_csv(self, monster_code: str, results: List[CombatResults], bank_items_map, sets: int):
        global_quantity_map = self.service.get_global_quantity_map()
        csv_rows = []
        for result in results:
            csv_row = {}
            for character in result.characters.values():
                csv_row = character.equipment.copy()
                if 'utility1' not in csv_row:
                    csv_row['utility1'] = ''
                if 'utility2' not in csv_row:
                    csv_row['utility2'] = ''
                csv_row['gather_time'] = result.gather_time
                csv_row['cooldown'] = result.raw_result.cooldown
                csv_row['win_rate'] = result.raw_result.win_rate
                csv_row['required_hp'] = result.raw_result.required_hp
                csv_row['n'] = str(result.sample_size)
                recipes = Counter(character.equipment.values())
                missing_recipes = self.service.get_missing_recipes(recipes, sets, global_quantity_map)
                resolved_recipes, _ = self.service.resolve_recipes(missing_recipes, bank_items_map.copy())
                missing_parts = ', '.join([f'{item_qty}x {item_code}' for item_code, item_qty in resolved_recipes.missing_items.items()])
                csv_row['missing_parts'] = missing_parts
                break
            csv_rows.append(csv_row)

        fieldnames = ['gather_time', 'cooldown', 'win_rate', 'required_hp', 'n', *GEAR_POSITIONS, 'utility1', 'utility2', 'missing_parts']
        csv_file = f'fight-config-{monster_code}.csv'
        with open(csv_file, mode='w', newline='') as file:
            # noinspection PyTypeChecker
            writer = csv.DictWriter(file, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(csv_rows)
        logger.info(f'Wrote fight config to {csv_file}')


report_function = ReportFunction()


if __name__ == '__main__':
    report_function.handler()
