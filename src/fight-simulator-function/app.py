import json
import os
import traceback

from aws_lambda_powertools.utilities.data_classes import event_source, SQSEvent
from aws_lambda_powertools.utilities.typing import LambdaContext
from dotenv import load_dotenv

from artifactsmmo.client.client import Client
from artifactsmmo.dynamodb.fight_simulator_table import FightSimulatorRecord, FightSimulatorStatus, FightSimulatorTable
from artifactsmmo.extensions import MonsterSchemaExtension
from artifactsmmo.fights.combat_result import minimize_cooldown
from artifactsmmo.log.logger import logger
from artifactsmmo.queue.worker_queue import WorkerQueue
from artifactsmmo.service.fight_simulator import FightSimulator
from artifactsmmo.service.service import Service


class FightSimulatorFunction:
    def __init__(self):
        if os.environ.get('AWS_LAMBDA_FUNCTION_NAME') is None:
            load_dotenv()

        self.service = Service(Client())
        self.fight_simulator = FightSimulator(self.service)
        self.fight_simulator_table = FightSimulatorTable()
        self.worker_queue = WorkerQueue()

    def handler(self, event: SQSEvent, context: LambdaContext):
        logger.debug('Received Event.')
        try:
            for record in event.records:
                fight_simulator_id = record.json_body['fight_simulator_id']
                fight_simulator_record = self.fight_simulator_table.get_record(fight_simulator_id)
                if fight_simulator_record and fight_simulator_record.status == FightSimulatorStatus.NEW:
                    logger.info(
                        f'fight_simulator_id: {fight_simulator_id}, character={fight_simulator_record.character_name}, '
                        f'monster={fight_simulator_record.monster_code},'
                    )
                    self.process_fight_simulator_record(fight_simulator_record)
                    logger.remove_keys(['character_name'])
                else:
                    logger.error(f'No pending fight_simulator_record found with fight_simulator_id: {fight_simulator_id}')
        except Exception:
            logger.error(traceback.format_exc())
        return {'statusCode': 200, 'body': json.dumps({'status': 'ok'})}

    def process_fight_simulator_record(self, record: FightSimulatorRecord):
        logger.append_keys(character_name=record.participants[0])
        self.fight_simulator_table.update_status(record, FightSimulatorStatus.RUNNING)

        if len(record.participants) > 1:
            sim_result = self._process_multi_character_fight_sim(record)
        else:
            sim_result = self._process_single_character_fight_sim(record)

        self.fight_simulator_table.submit_result(record, sim_result)

        if record.quest_id:
            character = self.service.get_character_details(record.participants[0])
            self.worker_queue.send_tasks(character, delay_seconds=0, quest_id=record.quest_id)

    def _process_multi_character_fight_sim(self, record: FightSimulatorRecord):
        monster = self.service.get_monster(record.monster_code)
        all_character_details = self.service.get_all_character_details()
        characters = [c for c in all_character_details if c.name in record.participants]
        bank_items_map = self.service.get_bank_items_map()
        force_utilities = record.force_utilities

        sim_result = self.fight_simulator.find_best_multi_character_fight_config(
            characters=characters,
            monster=monster,
            bank_items_map=bank_items_map,
            force_utilities=force_utilities,
        )

        return sim_result

    def _process_single_character_fight_sim(self, record: FightSimulatorRecord):
        character = self.service.get_character_details(record.participants[0])
        monster = self.service.get_monster(record.monster_code)

        force_utilities = False
        sim_result = self.fight_simulator.find_best_fight_config(
            character=character,
            monster=monster,
            exclude_items=record.exclude_items,
            winrate_threshold=50,
            force_utilities=force_utilities,
            add_character_inventory=True,
            sort_function=minimize_cooldown if record.sort_function == 'minimize_cooldown' else None,
        )

        if sim_result:
            equipment_map = {}
            utilities = []
            for c in sim_result.characters.values():
                equipment_map = c.equipment
                utilities = list(c.used_utilities.keys())
                break

            logger.info(
                f'Simulating fight yielded a result. Refining it with additional simulation rounds; '
                f'equipment_map={equipment_map}, utilities={utilities}'
            )
            sim_result = self.fight_simulator.test_exact_config(
                character=character,
                monster=monster,
                equipment_map=equipment_map,
                utilities_list=utilities,
                rounds=10_000,
            )
            sim_result.raw_result.required_hp = sim_result.raw_result.max_required_hp
            logger.info(
                f'CombatResult (Test) for character={character.name} ({character.level}), 👾 monster={monster.code} ({monster.level}), '
                f'{sim_result.to_string()}'
            )

        return sim_result


fight_simulator_function = FightSimulatorFunction()


@event_source(data_class=SQSEvent)
def handler(event: SQSEvent, context: LambdaContext):
    fight_simulator_function.handler(event, context)


if __name__ == '__main__':
    fight_simulator_function.handler(SQSEvent(data={}), LambdaContext())
