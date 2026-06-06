from local_environment import LocalEnvironment

from artifactsmmo.log.logger import logger


class ReportFunction(LocalEnvironment):
    def handler(self):

        for character in self.service.get_all_character_details():
            map_ = self.service.get_map_by_id(character.map_id)
            if map_.interactions and map_.interactions.content and map_.interactions.content.type == 'resource':
                resource_code = map_.interactions.content.code
                res_ = self.service.get_resource(resource_code)
                tools = self.service.get_tools(str(res_.skill), character=character)
                best_tool = next(tools, None)
                if best_tool and best_tool.code != character.weapon_slot:
                    logger.warning(f'Character {character.name} should equip {best_tool.code} to gather {resource_code} more efficiently.')
                else:
                    logger.info(
                        f'Character {character.name} has already the most efficient tool equipped ({character.weapon_slot}) to gather '
                        f'{resource_code} ({res_.level}) (skill level: {character.skills[res_.skill].level}).'
                    )


report_function = ReportFunction()

if __name__ == '__main__':
    report_function.handler()
