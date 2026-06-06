from dotenv import load_dotenv

from artifactsmmo.actions.action_processor import ActionProcessor
from artifactsmmo.client.actions import ActionsClient
from artifactsmmo.client.client import Client
from artifactsmmo.dynamodb.character_table import CharacterTable
from artifactsmmo.dynamodb.counters_table import CountersTable
from artifactsmmo.dynamodb.skill_stats_table import SkillStatsTable
from artifactsmmo.dynamodb.task_progress_table import TaskProgressTable
from artifactsmmo.fights.equipment_assembler import EquipmentAssembler
from artifactsmmo.service.fight_simulator import FightSimulator
from artifactsmmo.service.food_service import FoodService
from artifactsmmo.service.helpers import (
    character_1_name,
    character_2_name,
    character_3_name,
    character_4_name,
    character_5_name,
)
from artifactsmmo.service.report import Report
from artifactsmmo.service.service import Service
from artifactsmmo.service.task_processor import TaskProcessor
from artifactsmmo.telegram.client import TelegramClient
from artifactsmmo.templates.template_processor import TemplateProcessor


class LocalEnvironment:
    def __init__(self):
        load_dotenv()
        self.character_1_name = character_1_name()
        self.character_2_name = character_2_name()
        self.character_3_name = character_3_name()
        self.character_4_name = character_4_name()
        self.character_5_name = character_5_name()
        self.client: Client = Client()
        self.service: Service = Service(self.client)
        self.food_service: FoodService = FoodService(self.service)
        self.fight_simulator = FightSimulator(self.service)
        self.equipment_assembler = EquipmentAssembler(self.service)
        self.report = Report(self.service)
        telegram_client: TelegramClient = TelegramClient()
        task_progress_table: TaskProgressTable = TaskProgressTable()
        self.actions_client = ActionsClient()
        skill_stats_table = SkillStatsTable()
        counters_table = CountersTable()
        character_table = CharacterTable()
        actions_processor: ActionProcessor = ActionProcessor(
            self.actions_client,
            self.service,
            counters_table,
            telegram_client,
            task_progress_table,
            skill_stats_table,
            self.food_service,
            character_table,
        )
        template_processor: TemplateProcessor = TemplateProcessor(self.client, self.service, telegram_client, self.food_service)
        self.task_processor = TaskProcessor(actions_processor, template_processor, telegram_client, task_progress_table, self.service)
