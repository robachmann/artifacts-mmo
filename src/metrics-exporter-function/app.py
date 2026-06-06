from datetime import datetime, timedelta, UTC
import gzip
import io
import json
import os
from typing import Dict, List, Optional

import boto3
from prometheus_client import CollectorRegistry, Gauge, generate_latest

from artifactsmmo.client.client import Client
from artifactsmmo.dynamodb.counters_table import CountersTable
from artifactsmmo.extensions import CharacterSchemaExtension, ItemSchemaExtension
from artifactsmmo.log.logger import logger
from artifactsmmo.models import (
    AccountLeaderboardSchema,
    ActiveEventSchema,
    GEOrderSchema,
)
from artifactsmmo.service.helpers import account_name
from artifactsmmo.service.service import Service


class MetricsExporter:
    def __init__(self):
        if os.environ.get('AWS_LAMBDA_FUNCTION_NAME') is None:
            from dotenv import load_dotenv

            load_dotenv()
            self.is_cloud = False
        else:
            self.is_cloud = True

        self.service: Service = Service(Client())
        self.bucket_name = os.getenv('BUCKET_NAME')
        self.s3 = boto3.client('s3')
        self.all_character_details: List[CharacterSchemaExtension] = []
        self.counters_table = CountersTable()
        self.account_name = account_name()

    def handler(self, event, context):
        registry = CollectorRegistry()
        money_gauge = Gauge('money', 'Money', registry=registry, labelnames=['location', 'currency'])
        bank_slots_gauge = Gauge('bank_slots', 'Bank Slots', registry=registry, labelnames=['type'])
        try:
            self.all_character_details = self.service.get_all_character_details()
            self.character_metrics(registry, money_gauge)
            self.account_metrics(registry)
            self.ge_metrics(registry)
            self.event_metrics(registry)
            self.player_item_metrics(registry)
            self.achievement_metrics(registry)
            self.bank_metrics(money_gauge, bank_slots_gauge)
            self.accounts_leaderboard_metrics(registry)
            self.drop_rates_metrics(registry)
        except Exception as e:
            logger.error(e)

        if self.is_cloud:
            metrics_data = generate_latest(registry)
            buffer_compressed = io.BytesIO()
            with gzip.GzipFile(fileobj=buffer_compressed, mode='wb') as gz:
                gz.write(metrics_data)
            buffer_compressed.seek(0)

            self.s3.put_object(
                Bucket=self.bucket_name,
                Key='metrics.prom',
                Body=buffer_compressed,
                ContentType='text/plain',
                ContentEncoding='gzip',
                CacheControl='max-age=300, public',
            )

        return {'statusCode': 200, 'body': json.dumps({'status': 'ok'})}

    def character_metrics(self, registry: CollectorRegistry, money_gauge: Gauge):
        skill_level_gauge = Gauge('skill_level', "Character's skill level", registry=registry, labelnames=['skill', 'character_name'])
        skill_xp_gauge = Gauge('skill_xp', "Character's skill level XP", registry=registry, labelnames=['skill', 'character_name'])
        skill_max_xp_gauge = Gauge('skill_max_xp', "Character's skill level max XP", registry=registry, labelnames=['skill', 'character_name'])
        busy_characters_gauge = Gauge('busy_characters', 'Currently budy character', registry=registry, labelnames=['character_name'])

        now = datetime.now(UTC)
        for character in self.all_character_details:
            money_gauge.labels(currency='gold', location=character.name).set(character.gold)

            for skill_name, skill in character.skills.items():
                skill_level_gauge.labels(skill=skill_name, character_name=character.name).set(skill.level)
                skill_xp_gauge.labels(skill=skill_name, character_name=character.name).set(skill.xp)
                skill_max_xp_gauge.labels(skill=skill_name, character_name=character.name).set(skill.max_xp)

            skill_level_gauge.labels(skill='combat', character_name=character.name).set(character.level)
            skill_xp_gauge.labels(skill='combat', character_name=character.name).set(character.xp)
            skill_max_xp_gauge.labels(skill='combat', character_name=character.name).set(character.max_xp)

            is_active = int(character.cooldown_expiration + timedelta(seconds=60) >= now)
            busy_characters_gauge.labels(character_name=character.name).set(is_active)

    def ge_metrics(self, registry: CollectorRegistry):
        stock = Gauge('ge_item_stock', 'Grand Exchange Item Stock', registry=registry, labelnames=['item', 'type', 'subtype'])
        price = Gauge('ge_item_sell_price', 'Grand Exchange Item Sell Price', registry=registry, labelnames=['item', 'type', 'subtype'])

        ge_items_map: Dict[str, List[GEOrderSchema]] = self.service.get_ge_items_map()
        for item_code, sell_orders in ge_items_map.items():
            item: ItemSchemaExtension = self.service.get_item(item_code)
            if item:
                stock.labels(item=item.code, type=item.type, subtype=item.subtype).set(sum(o.quantity for o in sell_orders))
                price.labels(item=item.code, type=item.type, subtype=item.subtype).set(min(o.price for o in sell_orders))

    def account_metrics(self, registry: CollectorRegistry):
        account_details = self.service.get_account_details()
        event_tokens_gauge = Gauge('event_tokens', 'Event Tokens', registry=registry)
        event_tokens_gauge.set(account_details.event_token)

    def event_metrics(self, registry: CollectorRegistry):
        active_events: List[ActiveEventSchema] = self.service.get_active_events()
        active_events_gauge = Gauge('active_events', 'Currently active events', registry=registry, labelnames=['event'])
        for active_event in active_events:
            active_events_gauge.labels(event=active_event.name).set(1)

    def player_item_metrics(self, registry: CollectorRegistry):
        player_item_stock_gauge = Gauge('player_item_stock', 'Player Item Stock', registry=registry, labelnames=['item', 'type', 'subtype'])
        heal_capacity_gauge = Gauge('heal_capacity', 'Heal Capacity', registry=registry, labelnames=['item'])

        global_quantity_map = self.service.get_global_quantity_map()
        for item in self.service.get_all_items():
            quantity = global_quantity_map.get(item.code, 0)
            player_item_stock_gauge.labels(item=item.code, type=item.type, subtype=item.subtype).set(quantity)
            if item.item_effects and 'heal' in item.item_effects:
                heal_capacity_gauge.labels(item=item.code).set(item.item_effects['heal'] * quantity)

    def achievement_metrics(self, registry: CollectorRegistry):
        achievement_progress = Gauge(
            name='achievement_progress',
            documentation='Achievement Progress',
            registry=registry,
            labelnames=['name', 'type', 'total', 'points'],
        )

        achievement_points = Gauge(name='achievement_points', documentation='Achievement Points', registry=registry)

        achievement_points_total = 0
        for achievement in self.service.get_account_achievements(self.account_name):
            achievement_progress.labels(
                name=achievement.code,
                type=achievement.type,
                total=achievement.total,
                points=achievement.points,
            ).set(achievement.total_progress)
            achievement_points_total += achievement.points if achievement.completed_at else 0
        achievement_points.set(achievement_points_total)

    def bank_metrics(self, money_gauge: Gauge, bank_slots_gauge: Gauge):
        bank_details = self.service.get_bank_details()
        money_gauge.labels(currency='gold', location='bank').set(bank_details.gold)
        bank_slots_gauge.labels(type='slots').set(bank_details.slots)
        bank_items = self.service.get_bank_items_map(ignore_reservations=True)
        bank_slots_gauge.labels(type='items').set(len(bank_items.keys()))

    def accounts_leaderboard_metrics(self, registry: CollectorRegistry):
        leaderboard_positions = Gauge(
            'account_leaderboard_positions',
            'Account Leaderboard Positions',
            registry=registry,
            labelnames=['account', 'status', 'achievements_points'],
        )
        leaderboard_achievement_points = Gauge(
            'account_leaderboard_achievement_points',
            'Account Leaderboard Achievement Points',
            registry=registry,
            labelnames=['account', 'status'],
        )

        leaderboard: List[AccountLeaderboardSchema] = self.service.get_account_leaderboard()

        for position in leaderboard:
            if position.achievements_points > 0:
                leaderboard_positions.labels(
                    account=position.account, status=str(position.status), achievements_points=position.achievements_points
                ).set(position.position)
                leaderboard_achievement_points.labels(account=position.account, status=str(position.status)).set(position.achievements_points)

    def drop_rates_metrics(self, registry: CollectorRegistry):
        drop_rates = Gauge('drop_rates', 'Drop Rates of Items', registry=registry, labelnames=['item', 'source', 'type', 'avg_drop_rate'])

        list_of_drops = self.counters_table.get_all_drops()
        for db_item in list_of_drops:
            drop_key = str(db_item.get('type', {}).get('S'))
            drop_quantity = int(db_item.get('quantity', {}).get('N'))
            drop_code = str(db_item.get('code', {}).get('S'))
            splits = drop_key.split('.')
            source_type = splits[1]
            source_code = splits[2]
            item = self.service.get_item(drop_code)

            counter: Optional[dict] = None
            avg_drop_rate: Optional[int] = None
            match source_type:
                case 'monsters':
                    counter = self.counters_table.get_counter(code=source_code, type='monsters')
                    monster = self.service.get_monster(source_code)
                    if monster:
                        for drop in monster.drops:
                            if drop.code == drop_code:
                                avg_drop_rate = int(drop.rate / ((drop.min_quantity + drop.max_quantity) / 2))
                                break
                case 'resources':
                    counter = self.counters_table.get_counter(code=source_code, type='resources')
                    resource = self.service.get_resource(source_code)
                    if resource:
                        for drop in resource.drops:
                            if drop.code == drop_code:
                                avg_drop_rate = int(drop.rate / ((drop.min_quantity + drop.max_quantity) / 2))
                                break
                    else:
                        logger.error(f'Unknown resource: {source_code}')
                case _:
                    logger.warning(f'Unknown source type: {source_code} for drop_key={drop_key}')

            if counter and avg_drop_rate is not None and avg_drop_rate > 1:
                action_quantity = int(counter.get('quantity', {}).get('N'))
                drop_rate = action_quantity / drop_quantity
                if drop_rate > 1:
                    drop_rates.labels(item=drop_code, source=source_code, type=item.type, avg_drop_rate=avg_drop_rate).set(drop_rate)
                    logger.debug(f'Updated gauge: item={drop_code}, source={source_code}, type={item.type}, value={drop_rate}.')


metrics_exporter = MetricsExporter()


def handler(event, context):
    metrics_exporter.handler(event, context)


if __name__ == '__main__':
    metrics_exporter.handler({}, {})
