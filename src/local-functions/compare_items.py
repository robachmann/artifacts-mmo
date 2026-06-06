from artifactsmmo.fights.equipment_assembler import EquipmentAssembler
from artifactsmmo.models import Skill, GatheringSkill
from local_environment import LocalEnvironment
from artifactsmmo.log.logger import logger


class ReportFunction(LocalEnvironment):
    def handler(self):
        item_1 = self.service.get_item('lizard_skin_armor')
        item_2 = self.service.get_item('serpent_skin_armor')
        weapon = self.service.get_item('blade_of_hell')
        monster = self.service.get_monster('death_knight')

        equipment_assembler = EquipmentAssembler(self.service)
        compare_1 = equipment_assembler.is_this_item_better(item_1, item_2, weapon, monster)
        logger.info(f"Is '{item_1.code}' better than '{item_2.code}'? {compare_1}")
        compare_2 = equipment_assembler.is_this_item_better(item_2, item_1, weapon, monster)
        logger.info(f"Is '{item_2.code}' better than '{item_1.code}'? {compare_2}")


report_function = ReportFunction()


if __name__ == '__main__':
    report_function.handler()
