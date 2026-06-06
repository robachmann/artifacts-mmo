from datetime import datetime
from time import sleep
from typing import Dict, Optional

from local_environment import LocalEnvironment

from artifactsmmo.game_constants import MAX_LEVEL
from artifactsmmo.log.logger import logger
from artifactsmmo.models import CharacterSchema, CraftSkill
from artifactsmmo.service.helpers import character_5_name


class ReportFunction(LocalEnvironment):
    def handler(self):
        skill_name = CraftSkill.WOODCUTTING
        xp_map: Dict[str, Dict[str, int]] = {}
        all_items = self.service.get_all_items()
        candidate_items = [item for item in all_items if item.craft and item.craft.skill == skill_name]
        skill_items = []
        for item in candidate_items:
            if item.level not in xp_map:
                xp_map[str(item.level)] = {}
                skill_items.append(item)

        character: Optional[CharacterSchema] = self.client.get_character(character_5_name())
        for level in range(1, MAX_LEVEL + 1):
            skill_level = level
            craft_items = sorted([item for item in skill_items if level - 10 <= item.level <= level], key=lambda item: item.level)
            for craft in craft_items:
                skill_level = getattr(character, f'{skill_name}_level')
                if str(skill_level) not in xp_map[str(craft.level)]:
                    for part in craft.craft.items:
                        self.client.sandbox_give_item(character.name, part.code, part.quantity)

                    sleep_ts = character.cooldown_expiration.timestamp() - datetime.now().timestamp()
                    if sleep_ts > 0:
                        sleep(int(sleep_ts))
                    status_code, result, error = self.actions_client.craft(character, craft.code)
                    character = result.character
                    received_xp = result.details.xp
                    for inventory_item in result.character.inventory:
                        if inventory_item.code:
                            _, delete_response, _ = self.actions_client.delete_item(character, inventory_item.code, inventory_item.quantity)
                            character = delete_response.character

                    xp_map[str(craft.level)][str(skill_level)] = received_xp
                    logger.info(f'Crafting level {craft.level} item {craft.code} @ skill_level={skill_level}, yielded {received_xp} xp.')

            if skill_level < level + 1:
                required_xp = getattr(character, f'{skill_name}_max_xp') - getattr(character, f'{skill_name}_xp')
                character = self.client.sandbox_give_xp(character.name, required_xp, skill_name)

        logger.info(xp_map)


report_function = ReportFunction()


if __name__ == '__main__':
    report_function.handler()
