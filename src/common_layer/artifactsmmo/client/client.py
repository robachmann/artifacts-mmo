from functools import cache
import sys
from typing import List, Optional

from artifactsmmo.client.rest import RestClient
from artifactsmmo.log.logger import logger
from artifactsmmo.models import (
    AccountAchievementSchema,
    AccountLeaderboardSchema,
    ActiveEventSchema,
    BankResponseSchema,
    BankSchema,
    CharacterResponseSchema,
    CharacterSchema,
    CombatSimulationDataSchema,
    CombatSimulationResponseSchema,
    DataPageAccountAchievementSchema,
    DataPageAccountLeaderboardSchema,
    DataPageActiveEventSchema,
    DataPageDropRateSchema,
    DataPageEventSchema,
    DataPageGEOrderSchema,
    DataPageItemSchema,
    DataPageLogSchema,
    DataPageMapSchema,
    DataPageMonsterSchema,
    DataPageNPCItem,
    DataPageNPCSchema,
    DataPagePendingItemSchema,
    DataPageResourceSchema,
    DataPageSimpleItemSchema,
    DataPageTaskFullSchema,
    DropRateSchema,
    EventSchema,
    FakeCharacterSchema,
    GEOrderResponseSchema,
    GEOrderSchema,
    ItemSchema,
    LogSchema,
    MapResponseSchema,
    MapSchema,
    MonsterSchema,
    MyAccountDetails,
    MyAccountDetailsSchema,
    MyCharactersListSchema,
    NPCItem,
    NPCSchema,
    PendingItemSchema,
    ResourceSchema,
    SandboxResponseSchema,
    SimpleItemSchema,
    StatusResponseSchema,
    StatusSchema,
    TaskFullSchema,
)
from artifactsmmo.service.helpers import account_name
from artifactsmmo.static.static_files import StaticFiles


class Client:
    def __init__(self):
        self.rest_client = RestClient(retry_attempts=5, retry_wait=3)
        self.account_name = account_name()
        self.static_files = StaticFiles()

    def get_characters(self, account: str = None) -> List[CharacterSchema]:
        account = account or self.account_name
        response = self.rest_client.get(f'/accounts/{account}/characters')
        if response.status_code == 200:
            return MyCharactersListSchema.from_dict(response.json()).data
        else:
            logger.error(f'status_code: {response.status_code}, body={response.text}')
            return []

    def get_character(self, character_name: str) -> Optional[CharacterSchema]:
        url = f'/characters/{character_name}'
        response = self.rest_client.get(url)
        if response.status_code == 200:
            return CharacterResponseSchema.from_dict(response.json()).data
        else:
            logger.error(f'status_code: {response.status_code}, body={response.text}')
            return None

    def create_character(self, character_name: str, character_skin: str) -> Optional[CharacterSchema]:
        body = {'name': character_name, 'skin': character_skin}
        response = self.rest_client.post('/characters/create', json=body)
        if response.status_code == 200:
            return CharacterResponseSchema.from_dict(response.json()).data
        else:
            logger.error(f'status_code: {response.status_code}, body={response.text}')
            return None

    def sandbox_give_xp(self, character_name: str, amount: int, skill: str = 'combat') -> Optional[CharacterSchema]:
        body = {'character': character_name, 'type': skill, 'amount': amount}
        response = self.rest_client.post('/sandbox/give_xp', json=body)
        if response.status_code == 200:
            return SandboxResponseSchema.from_dict(response.json()).data.character
        else:
            logger.error(f'status_code: {response.status_code}, body={response.text}')
            return None

    def sandbox_give_item(self, character_name: str, item: str, quantity: int = 1) -> Optional[CharacterSchema]:
        body = {'character': character_name, 'code': item, 'quantity': quantity}
        response = self.rest_client.post('/sandbox/give_item', json=body)
        if response.status_code == 200:
            return SandboxResponseSchema.from_dict(response.json()).data.character
        else:
            logger.error(f'status_code: {response.status_code}, body={response.text}')
            return None

    def simulate_fight(self, characters: List[FakeCharacterSchema], monster: str, iterations: int = 1) -> Optional[CombatSimulationDataSchema]:
        body = {
            'characters': [character.to_dict() for character in characters],
            'monster': monster,
            'iterations': iterations,
        }

        response = self.rest_client.post('/simulation/fight_simulation', json=body)
        if response.status_code == 200:
            return CombatSimulationResponseSchema.from_dict(response.json()).data
        else:
            logger.error(f'status_code: {response.status_code}, body={response.text}')
            return None

    @cache
    def get_map(self, layer: str, x: int, y: int) -> MapSchema | None:
        url = f'/maps/{layer}/{x}/{y}'
        response = self.rest_client.get(url)
        if response.status_code == 200:
            return MapResponseSchema.from_dict(response.json()).data
        elif 500 <= response.status_code <= 599:
            logger.error(f'status_code: {response.status_code}, body={response.text}, exiting application.')
            sys.exit(1)
        else:
            logger.error(f'status_code: {response.status_code}, body={response.text}')
            return None

    def get_all_resources(self) -> List[ResourceSchema]:
        static_file = self.static_files.read_file('resources')
        page_data = DataPageResourceSchema.from_dict(static_file)
        return page_data.data

    def get_all_maps(self) -> List[MapSchema]:
        static_file = self.static_files.read_file('maps')
        page_data = DataPageMapSchema.from_dict(static_file)
        return page_data.data

    def get_all_monsters(self) -> List[MonsterSchema]:
        static_file = self.static_files.read_file('monsters')
        page_data = DataPageMonsterSchema.from_dict(static_file)
        return page_data.data

    def get_all_items(self) -> List[ItemSchema]:
        static_file = self.static_files.read_file('items')
        page_data = DataPageItemSchema.from_dict(static_file)
        return page_data.data

    def get_ge_order(self, order_id: str) -> Optional[GEOrderSchema]:
        url = f'/grandexchange/orders/{order_id}'
        response = self.rest_client.get(url)
        if response.status_code == 200:
            return GEOrderResponseSchema.from_dict(response.json()).data
        elif response.status_code != 404:
            logger.error(f'status_code: {response.status_code}, body={response.text}')
        return None

    def get_account_sell_orders(self) -> List[GEOrderSchema]:
        return self.get_account_ge_orders(order_type='sell')

    def get_account_buy_orders(self) -> List[GEOrderSchema]:
        return self.get_account_ge_orders(order_type='buy')

    def get_account_ge_orders(self, order_type: str = None) -> List[GEOrderSchema]:
        params = {}
        if order_type:
            params['type'] = order_type
        return self.get_pageable_resource_list('my/grandexchange/orders', params, DataPageGEOrderSchema, GEOrderSchema)

    def get_ge_sell_orders(self, item_code: str = None, account: str = None, order_type: str = None) -> List[GEOrderSchema]:
        params = {}
        if item_code:
            params['code'] = item_code
        if account:
            params['account'] = account
        if order_type:
            params['type'] = order_type
        return self.get_pageable_resource_list('grandexchange/orders', params, DataPageGEOrderSchema, GEOrderSchema)

    def get_all_npcs(self) -> List[NPCSchema]:
        return self.get_pageable_resource_list('npcs/details', {}, DataPageNPCSchema, NPCSchema)

    def get_all_npc_items(self) -> List[NPCItem]:
        return self.get_pageable_resource_list('npcs/items', {}, DataPageNPCItem, NPCItem)

    def get_bank_items(self) -> List[SimpleItemSchema]:
        params = {}
        return self.get_pageable_resource_list('my/bank/items', params, DataPageSimpleItemSchema, SimpleItemSchema)

    def get_pending_items(self) -> List[PendingItemSchema]:
        return self.get_pageable_resource_list('my/pending-items', {}, DataPagePendingItemSchema, PendingItemSchema)

    def get_bank_details(self) -> BankSchema | None:
        response = self.rest_client.get('/my/bank')
        if response.status_code == 200:
            return BankResponseSchema.from_dict(response.json()).data
        else:
            logger.error(f'status_code: {response.status_code}, body={response.text}')
            return None

    def get_active_events(self) -> List[ActiveEventSchema]:
        params = {}
        return self.get_pageable_resource_list('events/active', params, DataPageActiveEventSchema, ActiveEventSchema)

    @cache
    def get_all_events(self) -> List[EventSchema]:
        params = {}
        return self.get_pageable_resource_list('events', params, DataPageEventSchema, EventSchema)

    def get_account_achievements(self, account: str = None) -> List[AccountAchievementSchema]:
        account = account or self.account_name
        params = {}
        return self.get_pageable_resource_list(
            f'accounts/{account}/achievements', params, DataPageAccountAchievementSchema, AccountAchievementSchema
        )

    def get_account_leaderboard(self) -> List[AccountLeaderboardSchema]:
        params = {}
        return self.get_pageable_resource_list('leaderboard/accounts', params, DataPageAccountLeaderboardSchema, AccountLeaderboardSchema)

    def get_logs(self, size: int = 5, character_name: str = None) -> List[LogSchema]:
        params = {'size': size}
        if character_name:
            endpoint = f'/my/logs/{character_name}'
        else:
            endpoint = '/my/logs'
        response = self.rest_client.get(endpoint, params=params)
        if response.status_code == 200:
            return DataPageLogSchema.from_dict(response.json()).data
        else:
            logger.error(f'status_code: {response.status_code}, body={response.text}')
            return []

    def get_pageable_resource_list(self, resource_url: str, params: dict, page_schema, resource_schema, size: int = 100) -> list:
        return_list: List[resource_schema] = []
        params['size'] = size
        page = 1
        total_pages = 1
        use_local_fallback = False
        while page <= total_pages:
            params['page'] = page
            url = f'/{resource_url}'
            response = self.rest_client.get(url, params=params)
            if response.status_code == 200:
                page_data = page_schema.from_dict(response.json())
                return_list.extend(page_data.data)
                total_pages = page_data.pages
            elif response.status_code == 404:
                pass
            else:
                use_local_fallback = True
                logger.error(
                    f'resource_url={resource_url}, params={params}, page={page}, status_code={response.status_code}, body={response.text}'
                )
            page += 1

        if use_local_fallback:
            static_file = self.static_files.read_file(resource_url)
            page_data = page_schema.from_dict(static_file)
            return_list = page_data.data
            if not return_list:
                logger.error(f'Could not retrieve {resource_url} from local files.')
            else:
                logger.warning(f'Retrieved {len(return_list)} {resource_url} from local files.')

        return return_list

    @cache
    def get_all_tasks(self) -> List[TaskFullSchema]:
        params = {}
        return self.get_pageable_resource_list('tasks/list', params, DataPageTaskFullSchema, TaskFullSchema)

    @cache
    def get_all_task_rewards(self) -> List[DropRateSchema]:
        params = {}
        return self.get_pageable_resource_list('tasks/rewards', params, DataPageDropRateSchema, DropRateSchema)

    def get_account_details(self) -> Optional[MyAccountDetails]:
        response = self.rest_client.get('/my/details')
        if response.status_code == 200:
            return MyAccountDetailsSchema.from_dict(response.json()).data
        else:
            logger.error(f'status_code: {response.status_code}, body={response.text}')

    def get_server_status(self) -> Optional[StatusSchema]:
        response = self.rest_client.get('/')
        if response.status_code == 200:
            s = StatusResponseSchema.from_dict(response.json()).data
            return s
        else:
            logger.error(f'status_code: {response.status_code}, body={response.text}')
