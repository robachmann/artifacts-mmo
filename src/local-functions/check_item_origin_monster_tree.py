from artifactsmmo.service.item_origin_service import ItemOrigin
from local_environment import LocalEnvironment
from artifactsmmo.log.logger import logger


class ReportFunction(LocalEnvironment):
    def handler(self):
        iron_legs_armor: ItemOrigin = self.service.get_item_origin('iron_legs_armor')
        # ([cow])
        if iron_legs_armor.monster_tree == [['cow']]:
            logger.info('OK')
        else:
            logger.error('Not OK')

        corrupted_skull: ItemOrigin = self.service.get_item_origin('corrupted_skull')
        # ([corrupted_ogre, corrupted_owlbear, grimlet])
        if corrupted_skull.monster_tree == [['corrupted_ogre', 'corrupted_owlbear', 'grimlet']]:
            logger.info('OK')
        else:
            logger.error('Not OK')

        obsidian_legs_armor = self.service.get_item_origin('obsidian_legs_armor')
        # ([imp, demon], [owlbear, corrupted_owlbear], [bandit_lizard], [death_knight])
        if obsidian_legs_armor.monster_tree == [['imp', 'demon'], ['owlbear', 'corrupted_owlbear'], ['bandit_lizard'], ['death_knight']]:
            logger.info('OK')
        else:
            logger.error('Not OK')

        dreadful_staff = self.service.get_item_origin('dreadful_staff')
        # ([cyclops], [vampire])
        if dreadful_staff.monster_tree == [['cyclops'], ['vampire']]:
            logger.info('OK')
        else:
            logger.error('Not OK')

        greater_dreadful_staff = self.service.get_item_origin('greater_dreadful_staff')
        # ([ogre, corrupted_ogre], [cyclops], [death_knight], [vampire])
        if sorted(greater_dreadful_staff.monster_tree) == sorted([['ogre', 'corrupted_ogre'], ['cyclops'], ['death_knight'], ['vampire']]):
            logger.info('OK')
        else:
            logger.error('Not OK')

        death_knight_sword = self.service.get_item_origin('death_knight_sword')
        # ([death_knight])
        if death_knight_sword.monster_tree == [['death_knight']]:
            logger.info('OK')
        else:
            logger.error('Not OK')

        logger.info('OK')


report_function = ReportFunction()


if __name__ == '__main__':
    report_function.handler()
