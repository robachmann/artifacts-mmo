from collections import defaultdict
from datetime import datetime, timedelta, timezone, UTC
from math import ceil
import re
import time
from typing import Dict, Iterator, List, Optional, Tuple

from telegram.constants import ParseMode

from artifactsmmo import game_constants
from artifactsmmo.dynamodb.character_table import CharacterTable
from artifactsmmo.dynamodb.logs_table import LogLine, LogsTable
from artifactsmmo.dynamodb.skill_stats_table import SkillStat, SkillStatsTable
from artifactsmmo.dynamodb.task_progress_table import TaskProgress, TaskProgressTable
from artifactsmmo.extensions import CharacterSchemaExtension
from artifactsmmo.fights.combat_result import CombatResults
from artifactsmmo.fights.fight_bundle import self_round
from artifactsmmo.game_constants import ACTION_EMOJI_MAP, GATHERING_SKILLS, SKILLS
from artifactsmmo.log.logger import logger
from artifactsmmo.models import AchievementType, ActionType, LogType
from artifactsmmo.quests.quests import Quest
from artifactsmmo.service.fight_simulator import FightSimulator
from artifactsmmo.service.helpers import escape_string
from artifactsmmo.service.service import Service
from artifactsmmo.service.tasks import Task
from artifactsmmo.telegram.client import TelegramClient


class Report:
    def __init__(self, service: Service, fight_simulator: FightSimulator = None):
        self.service = service
        self.telegram = TelegramClient()
        self.logs_table = LogsTable()
        self.fight_simulator = fight_simulator or FightSimulator(service)
        self.character_table = CharacterTable()
        self.task_progress_table = TaskProgressTable()
        self.skill_stats_table = SkillStatsTable()

    def send_report(
        self, character: CharacterSchemaExtension, quest: Quest = None, cancelled: bool = False, include_task_report: bool = True
    ) -> bool:
        noop_task = True
        details: List[str] = []
        result = self.get_result(character, cancelled)
        if not quest:
            details.append(f'{character.name} {result}')
        else:
            creation_date = quest.created_at if quest.created_at else datetime.now(UTC)
            if not creation_date.tzinfo:
                creation_date = creation_date.replace(tzinfo=timezone.utc)
            now = datetime.now(UTC)
            delta = now - creation_date
            duration = f'{str(delta).split(".")[0]}'

            task_description = quest.description
            if task_description is not None:
                details.append(f'{character.name} {result} | {duration} | 🎯 {task_description}')
            else:
                details.append(f'{character.name} {result} | {duration}')

            logs: List[LogLine] = self.logs_table.get_logs(character.name, creation_date, now)
            long_report = len(logs) > 0

            xp_map = {}
            if include_task_report:
                noop_task, log_message, xp_map = self.create_summary_from_logs(logs)
                if log_message:
                    details.append('')
                    details.append(log_message)

            if long_report and len(xp_map) > 0:
                details.append('')

                if line := self.__format_character_fight_level(character, xp_map):
                    details.append(f'Level: {line}')

                for skill in game_constants.SKILLS:
                    if line := self.__format_character_levels(character, skill, xp_map):
                        details.append(f'{skill.capitalize()}: {line}')

        notification = '\n'.join(details)
        self.telegram.send_notification(notification)
        return noop_task

    @staticmethod
    def __format_character_fight_level(character: CharacterSchemaExtension, xp_map) -> str:
        level = character.level
        xp = character.xp
        max_xp = character.max_xp
        gained_xp = xp_map.get('fight', 0)
        if 0 < xp < gained_xp:
            return f'{level} ({xp}/{max_xp}) 🆙'
        elif gained_xp > 0 and xp > 0:
            return f'{level} ({xp}/{max_xp}) +{gained_xp}'
        else:
            return ''

    @staticmethod
    def __format_character_levels(character: CharacterSchemaExtension, param, xp_map) -> str:
        skill = character.skills[param]
        gained_xp = xp_map.get(param, 0)
        if 0 < skill.xp < gained_xp:
            return f'{skill.level} ({skill.xp}/{skill.max_xp}) 🆙 +{gained_xp}'
        elif gained_xp > 0 and skill.xp > 0:
            return f'{skill.level} ({skill.xp}/{skill.max_xp}) +{gained_xp}'
        else:
            return ''

    @staticmethod
    def create_summary_from_logs(logs: List[LogLine]):
        xp_summary: Dict[str, int] = defaultdict(int)
        noop_task = True

        stats: Dict[str, Dict[str, List[int]]] = defaultdict(lambda: defaultdict(lambda: [0, 0]))
        for log in logs:
            log_action = log.action
            subject = log.subject if log.subject else log_action

            if log_action in (
                'fight-lost',
                LogType.FIGHT,
                LogType.GATHERING,
                LogType.CRAFTING,
                LogType.SELL_GE,
                LogType.BUY_GE,
                LogType.RECYCLING,
                LogType.USE,
                LogType.REST,
                LogType.SPAWN,
                LogType.SELL_NPC,
                LogType.BUY_NPC,
            ):
                qty = 1 if log.quantity is None else log.quantity
                stats[log_action][subject][0] += qty
                cd = 0 if log.cooldown is None else log.cooldown
                stats[log_action][subject][1] += cd

            if log.xp_gained is not None:
                xp_key = 'fight' if log_action == 'fight' else log.skill
                xp_summary[xp_key] += log.xp_gained

        lines = []
        for action, s in stats.items():
            stat_lines = []
            if action != 'rest':
                noop_task = False
            for subject, (qty, cd) in s.items():
                if cd > 0:
                    stat_lines.append(f'{subject} ({qty}x, {timedelta(seconds=cd)})')
                else:
                    stat_lines.append(f'{subject} ({qty}x)')
            lines.append(f'{ACTION_EMOJI_MAP.get(action, action)} {", ".join(stat_lines)}')

        log_message = ' | '.join(sorted(lines))

        return noop_task, log_message, xp_summary

    @staticmethod
    def get_result(character: CharacterSchemaExtension, cancelled: bool) -> str:
        if cancelled:
            return '⚠️'
        else:
            if character.at_success_position():
                return '✅'
            else:
                return '❌'

    def create_report(self, characters: List[CharacterSchemaExtension]) -> str:
        now = datetime.now(UTC).replace(microsecond=0)

        msg_map: Dict[str, Tuple[List[str], List[str]]] = {}
        quests: List[Quest] = self.character_table.get_all_quests()
        quest_map: Dict[str, Quest] = {quest.character_name: quest for quest in quests}
        for character in characters:
            lines: List[str] = []

            quest = quest_map.get(character.name)
            if quest:
                if not quest.leader or quest.leader == character.name:
                    if character.name in msg_map:
                        msg_map[character.name][0].append(character.name)
                    else:
                        msg_map[character.name] = ([character.name], [])

                    if quest.status:
                        if quest.description == 'solve-event':
                            lines.append(f'🎯 {quest.description}')
                        else:
                            lines.append(f'🎯 {quest.status}')
                        if 'Task' in quest.status and character.task:
                            details_added = False

                            if character.current_task.task_remaining > 1:
                                logs = self.logs_table.get_logs(character.name, now - timedelta(minutes=15), now)

                                if len(logs) > 1:
                                    datetime_list: List[int] = []
                                    for log in logs:
                                        if log.subject == character.task:
                                            datetime_list.append(log.created_ts)
                                    datetime_list.sort()
                                    differences = [datetime_list[i + 1] - datetime_list[i] for i in range(len(datetime_list) - 1)]
                                    if len(differences) > 0:
                                        average_difference = sum(differences) / len(differences)
                                        etc = timedelta(seconds=int((character.task_total - character.task_progress) * average_difference))
                                        time = self.telegram.format_time_at_user_timezone(now + etc)
                                        lines.append(f' ∟ {character.task} ({character.task_progress}/{character.task_total}) ⏱️ {etc} @ {time}')
                                        details_added = True
                            if not details_added:
                                lines.append(f' ∟ {character.task} ({character.task_progress}/{character.task_total})')
                        elif 'Level' in quest.status:
                            self.__handle_level_skill_status(lines, character, quest, now)
                        elif 'Solving achievement' in quest.status:
                            self.__handle_solve_achievement_status(lines, character, quest, now)

                        elif quest.description == 'solve-event':
                            for task in quest.tasks:
                                if task.until and task.until.date_time:
                                    etc: timedelta = task.until.date_time.replace(microsecond=0) - now
                                    time = self.telegram.format_time_at_user_timezone(task.until.date_time)
                                    lines.append(f' ∟ {quest.status} ⏱️ {etc} @ {time}')
                                    break

                    quest_progress_list: List[TaskProgress] = self.task_progress_table.get_quest_progress(quest.quest_id)
                    first_unfinished_task_id = self.get_first_unfinished_task_id(quest.tasks)

                    quest_progress_list = sorted(quest_progress_list, key=lambda x: x.delete_at_ts)
                    for progress in quest_progress_list:
                        counter = progress.counter
                        target = progress.target
                        composite_key_parts = progress.drop_item.split('.')
                        task_id = composite_key_parts[0]
                        if not first_unfinished_task_id or first_unfinished_task_id == task_id:
                            drop_item = composite_key_parts[-1]
                            if target > counter > 1:
                                elapsed = progress.elapsed
                                etc = timedelta(seconds=int((target - counter - 1) * (elapsed / (counter - 1))))
                                time = self.telegram.format_time_at_user_timezone(now + etc)
                                lines.append(f' ∟ {drop_item} ({counter}/{target}) ⏱️ {etc} @ {time}')
                            else:
                                lines.append(f' ∟ {drop_item} ({counter}/{target})')
                    lines.append('')
                    lines.append('')
                    msg_map[character.name][1].extend(lines)
                else:
                    if quest.status:
                        if quest.leader in msg_map:
                            msg_map[quest.leader][0].append(character.name)
                        else:
                            msg_map[quest.leader] = ([character.name], [])

        result = ''
        for title, content in msg_map.values():
            content.insert(0, ', '.join(title))
            result += '\n'.join(content)

        return result

    def create_report_v2(self, characters: List[CharacterSchemaExtension]) -> str:
        now = datetime.now(UTC).replace(microsecond=0)

        quests: List[Quest] = self.character_table.get_all_quests()
        quest_map: Dict[str, Quest] = {quest.character_name: quest for quest in quests}
        lines: List[str] = []
        quest_progress_map: Dict[str, Dict[str, TaskProgress]] = {}
        for character in characters:
            quest = quest_map.get(character.name)

            if not quest:
                title = f'{character.name}'
                cooldown: timedelta = timedelta(seconds=int(character.get_remaining_cooldown()))
                if cooldown.total_seconds() > 0:
                    title += f' ⏱️ {cooldown}'
                lines.append(title)
                lines.append('No active quest.')
            else:
                add_cooldown = True
                if quest.leader and quest.leader != character.name:
                    title = f'{character.name} 🔗 {quest.leader}'
                    leader_quest_id = quest_map.get(quest.leader).quest_id if quest.leader in quest_map else None
                    if quest.quest_id != leader_quest_id:
                        title += f" ❗️ Quest IDs don't match ({quest.quest_id} != {leader_quest_id})"
                        add_cooldown = False
                else:
                    title = f'{character.name}'
                if add_cooldown:
                    cooldown: timedelta = timedelta(seconds=int(character.get_remaining_cooldown()))
                    if cooldown.total_seconds() > 0:
                        title += f' ⏱️ {cooldown}'
                lines.append(title)
                if quest.status:
                    if quest.description == 'solve-event':
                        lines.append(f'🎯 {quest.description}')
                    else:
                        lines.append(f'🎯 {quest.status}')

                task_id = None
                # previous_eta = datetime.now(UTC).replace(microsecond=0)
                for task in quest.tasks:
                    if not task_id:
                        task_id = task.task_id
                    elif not task.task_id or task_id != task.task_id:
                        break

                    if task.ttl and task.action not in [
                        'move',
                        'transition',
                        'rest',
                        'sleep',
                        'equip',
                        'unequip',
                        'unequip-all',
                        'verify-equipment',
                        'ensure-inventory',
                        'use-item',
                        'withdraw',
                        'deposit',
                        'deposit-all',
                        'complete-task',
                        'solve-task',
                        'finish-task',
                        'finish-quest',
                    ]:
                        target = ' '.join(task.extra[k] for k in ['resource', 'monster'] if k in task.extra)
                        if task.until:
                            if task.until.date_time:
                                end: datetime = task.until.date_time.replace(microsecond=0)
                                # previous_eta = end
                                etc: timedelta = end - now
                                date_time = self.telegram.format_time_at_user_timezone(task.until.date_time)
                                line = f' ∟ {task.action} {target} ⏱️ {etc} @ {date_time}'
                            else:
                                eta_str = ''
                                if task.until.drop_item and task.until.drop_count:
                                    item_code = task.until.drop_item

                                    if quest.quest_id not in quest_progress_map:
                                        progress_list: List[TaskProgress] = self.task_progress_table.get_quest_progress(quest.quest_id)
                                        progress_map: Dict[str, TaskProgress] = {}
                                        for progress_item in progress_list:
                                            composite_key_parts = progress_item.drop_item.split('.')
                                            drop_item = composite_key_parts[-1]
                                            progress_map[drop_item] = progress_item
                                        quest_progress_map[quest.quest_id] = progress_map

                                    if item_code in quest_progress_map[quest.quest_id]:
                                        progress: TaskProgress = quest_progress_map[quest.quest_id][item_code]

                                        counter = progress.counter
                                        total = progress.target
                                        if total > counter > 1:
                                            elapsed = progress.elapsed
                                            etc = timedelta(seconds=int((total - counter - 1) * (elapsed / (counter - 1))))
                                            time = self.telegram.format_time_at_user_timezone(now + etc)
                                            eta_str = f' ⏱️ {etc} @ {time}'

                                line = f' ∟ {task.action} {target} for {task.until.to_pretty_str()}{eta_str}'
                        else:
                            ttl = f' {task.ttl}x' if task.ttl > 1 else ''
                            line = f' ∟ {task.action} {target}{ttl}'
                        lines.append(line)

                # if not quest.leader or quest.leader == character.name:
                #     if character.name in msg_map:
                #         msg_map[character.name][0].append(character.name)
                #     else:
                #         msg_map[character.name] = ([character.name], [])
                #
                #     if quest.status:
                #         if quest.description == 'solve-event':
                #             lines.append(f'🎯 {quest.description}')
                #         else:
                #             lines.append(f'🎯 {quest.status}')
                #         if 'Task' in quest.status and character.task:
                #             details_added = False
                #
                #             if character.current_task.task_remaining > 1:
                #                 logs = self.logs_table.get_logs(character.name, now - timedelta(minutes=15), now)
                #
                #                 if len(logs) > 1:
                #                     datetime_list: List[int] = []
                #                     for log in logs:
                #                         if log.subject == character.task:
                #                             datetime_list.append(log.created_ts)
                #                     datetime_list.sort()
                #                     differences = [datetime_list[i + 1] - datetime_list[i] for i in range(len(datetime_list) - 1)]
                #                     if len(differences) > 0:
                #                         average_difference = sum(differences) / len(differences)
                #                         etc = timedelta(seconds=int((character.task_total - character.task_progress) * average_difference))
                #                         time = self.telegram.format_time_at_user_timezone(now + etc)
                #                         lines.append(f' ∟ {character.task} ({character.task_progress}/{character.task_total}) ⏱️ {etc} @ {time}')
                #                         details_added = True
                #             if not details_added:
                #                 lines.append(f' ∟ {character.task} ({character.task_progress}/{character.task_total})')
                #         elif 'Level' in quest.status:
                #             self.__handle_level_skill_status(lines, character, quest, now)
                #         elif 'Solving achievement' in quest.status:
                #             self.__handle_solve_achievement_status(lines, character, quest, now)
                #
                #         elif quest.description == 'solve-event':
                #             for task in quest.tasks:
                #                 if task.until and task.until.date_time:
                #                     etc: timedelta = task.until.date_time.replace(microsecond=0) - now
                #                     time = self.telegram.format_time_at_user_timezone(task.until.date_time)
                #                     lines.append(f' ∟ {quest.status} ⏱️ {etc} @ {time}')
                #                     break
                #
                #     quest_progress_list = self.task_progress_table.get_quest_progress(quest.quest_id)
                #     first_unfinished_task_id = self.get_first_unfinished_task_id(quest.tasks)
                #
                #     quest_progress_list = sorted(quest_progress_list, key=lambda x: x['delete_at_ts']['N'])
                #     for progress in quest_progress_list:
                #         counter = int(progress['counter']['N'])
                #         target = int(progress['target']['N'])
                #         composite_key_parts = str(progress['drop_item']['S']).split('.')
                #         task_id = composite_key_parts[0]
                #         if not first_unfinished_task_id or first_unfinished_task_id == task_id:
                #             drop_item = composite_key_parts[-1]
                #             if target > counter > 1:
                #                 elapsed = int(progress['elapsed']['N'])
                #                 etc = timedelta(seconds=int((target - counter - 1) * (elapsed / (counter - 1))))
                #                 time = self.telegram.format_time_at_user_timezone(now + etc)
                #                 lines.append(f' ∟ {drop_item} ({counter}/{target}) ⏱️ {etc} @ {time}')
                #             else:
                #                 lines.append(f' ∟ {drop_item} ({counter}/{target})')
                #     lines.append('')
                #     lines.append('')
                #     msg_map[character.name][1].extend(lines)
                # else:
                #     if quest.status:
                #         if quest.leader in msg_map:
                #             msg_map[quest.leader][0].append(character.name)
                #         else:
                #             msg_map[quest.leader] = ([character.name], [])
            lines.append('')
        # result = ''
        # for title, content in msg_map.values():
        #    content.insert(0, ', '.join(title))
        return '\n'.join(lines)

        # return result

    @staticmethod
    def get_first_unfinished_task_id(tasks: List[Task]) -> Optional[str]:
        for task in tasks:
            if task.ttl > 0 and task.task_id:
                return task.task_id
        return None

    def print_fight_matrix(
        self,
        min_monster_level: int = 1,
        print_console=True,
        send_message=False,
        skip_boss_monsters: bool = False,
    ):
        all_character_details = self.service.get_all_character_details()

        results: Dict[str, List[str]] = defaultdict(list)
        number_icons = ['1️⃣', '2️⃣', '3️⃣', '4️⃣', '5️⃣']
        results[''] = number_icons

        title = ''
        start = time.perf_counter()
        last_notification_at = time.perf_counter()
        character_list: List[str] = [f'{number_icons[idx]} {c.name} ({c.level})' for idx, c in enumerate(all_character_details)]
        for idx, character_str in enumerate(character_list):
            if idx > 0:
                if idx % 3 == 0:
                    title += '\n'
                else:
                    title += ' | '
            title += character_str
        title = escape_string(title)

        lines: List[str] = [f'Monster,{",".join([f"{c.name} ({c.level})" for c in all_character_details])}']
        message_id: Optional[str] = None
        top_n = 5
        all_characters_inventory_map = self.service.get_all_characters_inventory_map(all_character_details)
        global_quantity_map = self.service.get_global_quantity_map(all_characters_inventory_map=all_characters_inventory_map)
        for monster in self.service.get_monsters_by_level(min_level=min_monster_level):
            if skip_boss_monsters and monster.is_boss_monster and monster.level > 20:
                monster_results = []
                config_num = 0
                for _ in range(top_n):
                    config_num += 1
                    icon = '🐲'
                    monster_results.append(icon)
                    results[f'{monster.code} ({monster.level})'].append(icon)
                    now = time.perf_counter()
                    if send_message and (top_n == config_num or (now - last_notification_at) > 30):
                        footer = escape_string(f'Time: {timedelta(seconds=int(now - start))}')
                        message_id = self.notify_matrix_update(title, results, footer, message_id)
                        last_notification_at = time.perf_counter()
                lines.append(f'{monster.code} ({monster.level}),{",".join(monster_results)}')
            else:
                monster_results = []
                configs: Iterator[CombatResults] = self.fight_simulator.find_top_n_fight_configs(
                    characters=all_character_details,
                    monster=monster,
                    top_n=top_n,
                    bank_items_map=global_quantity_map,
                    return_first_config=True,
                )
                config_num = 0
                for config in configs:
                    config_num += 1
                    if config:
                        icon = config.format_win_rate_icons()
                    else:
                        icon = '❌'
                    monster_results.append(icon)
                    results[f'{monster.code} ({monster.level})'].append(icon)
                    now = time.perf_counter()
                    if send_message and (top_n == config_num or (now - last_notification_at) > 30):
                        footer = escape_string(f'Time: {timedelta(seconds=int(now - start))}')
                        message_id = self.notify_matrix_update(title, results, footer, message_id)
                        last_notification_at = time.perf_counter()
                lines.append(f'{monster.code} ({monster.level}),{",".join(monster_results)}')
        if print_console:
            logger.info('\n'.join(lines))

    def notify_matrix_update(self, title: str, monster_results: Dict[str, List[str]], footer: str, message_id: str = None) -> str:
        lines: List[str] = [title, '```']
        longest_monster_code = max(len(k) for k in monster_results.keys())

        for monster, results in monster_results.items():
            left_padded = monster.ljust(longest_monster_code)
            lines.append(f'{left_padded} {" ".join(results)}')
        lines.extend(['```', footer])
        if message_id:
            self.telegram.update_notification(message_id, ('\n'.join(lines)), parse_mode=ParseMode.MARKDOWN_V2)
            result = message_id
        else:
            result = self.telegram.send_notification(('\n'.join(lines)), parse_mode=ParseMode.MARKDOWN_V2)
        return result

    def __handle_level_skill_status(self, lines: List[str], character: CharacterSchemaExtension, quest: Quest, now: datetime):
        match = re.search(r'Level (\w+) to (\d+)', quest.status)
        if match:
            skill = match.group(1)
            target_level = int(match.group(2))
            if skill in SKILLS:
                missing_xp = 0
                first_task = next((task for task in quest.tasks if task.ttl > 0 and task.action not in ('use-item', 'rest')))
                first_task_ttl = first_task.ttl if first_task else 1
                if first_task.action == 'gather':
                    resource_code = first_task.extra.get('resource')
                    if resource_code:
                        if skill in GATHERING_SKILLS:
                            action = ActionType.GATHERING
                        else:
                            action = ActionType.CRAFTING
                        skill_stats: List[SkillStat] = self.skill_stats_table.get_skill_stats(
                            action=action,
                            skill=skill,
                            skill_level=character.skills[skill].level,
                            subject_filter=resource_code,
                        )
                        first_xp = 1
                        for skill_stat in skill_stats:
                            first_xp = skill_stat.gained_xp
                            break

                        expected_xp = self_round(first_xp * (1 + character.wisdom * 0.001))
                        missing_xp = self.service.get_missing_xp(character.skills[skill], target_level)
                        if expected_xp > 0:
                            first_task_ttl = ceil(missing_xp / expected_xp)
                        else:
                            first_task_ttl = 1

                        logger.info(
                            f'Skill stats for skill={skill}, level={character.skills[skill].level}, subject_filter={resource_code}, '
                            f'gained_xp={[a.gained_xp for a in skill_stats]}, first_xp={first_xp}, expected_xp={expected_xp}, '
                            f'missing_xp={missing_xp}, first_task_ttl={first_task_ttl}'
                        )

                etc, time = self.__calculate_remaining_time(character, skill, first_task_ttl, now)
                if missing_xp == 0:
                    missing_xp = character.skills[skill].max_xp - character.skills[skill].xp
                skill_xp = character.skills[skill].xp
                skill_max_xp = character.skills[skill].xp + missing_xp
                skill_percent = int(skill_xp / skill_max_xp * 100)
            else:
                first_task_ttl = sum(task.ttl for task in quest.tasks if task.action == 'fight')
                etc = timedelta(seconds=int(first_task_ttl * 55))
                time = self.telegram.format_time_at_user_timezone(now + etc)
                skill_xp = character.xp
                skill_max_xp = character.max_xp
                skill_percent = int(skill_xp / skill_max_xp * 100)
            lines.append(f' ∟ {skill_percent}% ({skill_xp}/{skill_max_xp}, {first_task_ttl} left) ⏱️ {etc} @ {time}')

    def __handle_solve_achievement_status(self, lines: List[str], character: CharacterSchemaExtension, quest: Quest, now: datetime):
        match = re.search(r'Solving achievement (\w+)', quest.status)
        if match:
            achievement_code = match.group(1)
            achievement = self.service.get_account_achievement(character.account, achievement_code)
            if achievement:
                achievement_percent = int(achievement.current / achievement.total * 100)
                first_task_ttl = max(0, achievement.total - achievement.current)

                if all(objective.type == AchievementType.COMBAT_KILL for objective in achievement.objectives):
                    monster = self.service.get_monster(achievement.target)  # FIXME: Adjust for multiple objectives per achievement
                    if monster:
                        etc = timedelta(seconds=first_task_ttl * 60)
                        time = self.telegram.format_time_at_user_timezone(now + etc)

                        lines.append(
                            f' ∟ {achievement.target}, {achievement_percent}% ({achievement.current}/{achievement.total}, {first_task_ttl} left) ⏱️ ~{etc} @ {time}'
                        )
                else:
                    item = self.service.get_item(achievement.target)  # FIXME: Adjust for multiple objectives per achievement
                    if item:
                        skill = item.subtype
                        if skill in SKILLS:
                            etc, time = self.__calculate_remaining_time(character, skill, first_task_ttl, now)

                            lines.append(
                                f' ∟ {achievement.target}, {achievement_percent}% ({achievement.current}/{achievement.total}, {first_task_ttl} left) ⏱️ {etc} @ {time}'
                            )

    def __calculate_remaining_time(self, character: CharacterSchemaExtension, skill: str, ttl: int, now: datetime):
        cooldown_reduction_factor = 1.0
        if character.weapon_slot:
            tool = self.service.get_item(character.weapon_slot)
            cooldown_improvement_percent = tool.item_effects.get(skill.lower(), 0)
            cooldown_reduction_factor = (100 + cooldown_improvement_percent) / 100

        cooldown_key: int = max(1, character.skills[skill].level // 5 * 5)
        cooldown_value = cooldown_key // 2 + 29
        seconds_per_action = round(cooldown_value * cooldown_reduction_factor)

        current_inventory_size = sum(character.inventory_map.values())
        deposit_runs = (ttl + current_inventory_size) // character.inventory_max_items
        deposit_move_seconds = deposit_runs * 60

        current_cooldown = ceil(character.get_remaining_cooldown())
        total_seconds = int((ttl - 1) * seconds_per_action) + deposit_move_seconds + current_cooldown

        etc = timedelta(seconds=total_seconds)
        time = self.telegram.format_time_at_user_timezone(now + etc)

        logger.info(
            f'Derived cooldown based on character_name={character.name}, '
            f'cooldown_key={cooldown_key}, cooldown_value={cooldown_value}, '
            f'cooldown_reduction_factor={cooldown_reduction_factor}, seconds_per_action={seconds_per_action}, '
            f'ttl={ttl}, deposit_runs={deposit_runs}, current_cooldown={current_cooldown}, '
            f'total_seconds={total_seconds}'
        )

        return etc, time
