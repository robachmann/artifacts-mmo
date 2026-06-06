from local_environment import LocalEnvironment

from artifactsmmo.fights.combat_calculator import CombatCalculatorMode
from artifactsmmo.log.logger import logger


class ReportFunction(LocalEnvironment):
    def handler(self):
        character = self.service.get_character_details(self.character_2_name)
        monster = self.service.get_monster('corrupted_owlbear')

        result = self.fight_simulator.test_exact_config(
            character=character,
            monster=monster,
            # equipment_map=equipment_map,
            utilities_list=[],
            print_log=True,
            rounds=10000,
        )

        logger.info(
            f'CombatResult for character={character.name} ({character.level}), monster={monster.code} ({monster.level}), {result.to_string()}'
        )


report_function = ReportFunction()


if __name__ == '__main__':
    report_function.handler()
