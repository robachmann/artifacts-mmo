import math
from typing import List

from artifactsmmo.dynamodb.skill_stats_table import SkillStat
from artifactsmmo.extensions import CharacterSchemaExtension
from artifactsmmo.game_constants import MAX_LEVEL
from artifactsmmo.log.logger import logger
from artifactsmmo.service.execution_context import ExecutionContext
from artifactsmmo.service.tasks import Task
from artifactsmmo.templates.template_result import TemplateResult
from artifactsmmo.templates.template_strategy import TemplateStrategy


class LevelFightTemplate(TemplateStrategy):
    def template(self) -> str:
        return 'level-fight'

    @staticmethod
    def describe_task(task: Task) -> str:
        if task.extra.get('monster'):
            return f'to {task.extra.get("level")} against {task.extra.get("monster")}'
        else:
            return f'to {task.extra.get("level")}'

    def render(self, character: CharacterSchemaExtension, task: Task, quest_id: str = None, context: ExecutionContext = None) -> TemplateResult:
        template_result: TemplateResult = TemplateResult()
        extra = task.extra
        target_level = extra.get('level')
        monster_code = extra.get('monster')

        current_level = character.level
        if target_level is None:
            target_level = min(current_level + 1, MAX_LEVEL)

        if current_level < target_level:
            if current_level + 1 == target_level:
                if monster_code:
                    skill_stats: List[SkillStat] = self.skill_stats_table.get_skill_stats(
                        action='fight',
                        skill='fight',
                        skill_level=current_level,
                        subject_filter=monster_code,
                    )
                    skill_stats = [
                        stats for stats in skill_stats if stats.gained_xp > 25 and not self.service.get_monster(stats.subject).is_event_monster
                    ]

                    if skill_stats:
                        for stats in sorted(skill_stats, key=lambda s: s.gained_xp, reverse=True):
                            gained_xp = stats.gained_xp
                            required_xp = character.max_xp - character.xp
                            ttl = math.ceil(required_xp / gained_xp)

                            template_result.append(Task.fight_monster(monster=stats.subject, ttl=ttl))
                            template_result.quest_status(f'Level fight to {target_level} against {stats.subject}')
                            logger.info(
                                f'Added tasks to fight {stats.subject} {ttl} times to level '
                                f'from current level={current_level} to target level={target_level}'
                            )
                            break
                    else:
                        template_result.append(Task.fight_monster(monster=monster_code))
                        template_result.quest_status(f'Level fight to {target_level} against {monster_code}')
                        template_result.append(Task.level_fight(target_level=target_level))
                # else:
                #     template_result.append(Task.fight_strongest_monster(target_level=target_level))
                #     template_result.quest_status(f'Level fight to {target_level}')
                # logger.info(f'Added tasks to fight strongest monster to find out gained xp on level={current_level}')
                else:
                    template_result.append(Task.solve_task(priority='xp'))
                    template_result.append(Task.level_fight(target_level=target_level))
            else:
                for level_steps in iter(range(current_level + 1, target_level + 1)):
                    template_result.append(Task.level_fight(target_level=level_steps, monster=monster_code))
        else:
            logger.info(f"Character's fight level is already reached: current_level={current_level}, target_level={target_level}")

        return template_result
