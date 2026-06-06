import json
from typing import Any, Dict, List, Optional, Tuple

from artifactsmmo.client.rest import RestClient
from artifactsmmo.extensions import CharacterSchemaExtension
from artifactsmmo.log.logger import logger
from artifactsmmo.models import (
    BankExtensionTransactionSchema,
    BankGoldTransactionSchema,
    BankItemTransactionSchema,
    CharacterFightDataSchema,
    CharacterMovementDataSchema,
    CharacterRestDataSchema,
    CharacterTransitionDataSchema,
    ClaimPendingItemDataSchema,
    DeleteItemSchema,
    EquipRequestSchema,
    GEOrderTransactionSchema,
    GETransactionListSchema,
    GiveItemDataSchema,
    NpcMerchantTransactionSchema,
    RecyclingDataSchema,
    RewardDataSchema,
    SkillDataSchema,
    TaskCancelledSchema,
    TaskDataSchema,
    TaskTradeDataSchema,
    UseItemSchema,
)


class ActionsClient:
    def __init__(self):
        self.rest_client = RestClient(retry_attempts=5, retry_wait=3)

    def move(self, character: CharacterSchemaExtension, map_id: int) -> Tuple[int, Optional[CharacterMovementDataSchema], Optional[dict]]:
        url = f'/my/{character.name}/action/move'
        body = {'map_id': map_id}
        response = self.rest_client.post(url, json=body, delay_until=character.cooldown_expiration)
        if response.status_code == 200:
            return response.status_code, extract_response(response, CharacterMovementDataSchema), None
        else:
            logger.error(f'status_code: {response.status_code}, body={response.text}')
            return response.status_code, None, json.loads(response.text).get('error', {})

    def transition(self, character: CharacterSchemaExtension) -> Tuple[int, Optional[CharacterTransitionDataSchema], Optional[dict]]:
        url = f'/my/{character.name}/action/transition'
        response = self.rest_client.post(url, delay_until=character.cooldown_expiration)
        if response.status_code == 200:
            return response.status_code, extract_response(response, CharacterTransitionDataSchema), None
        else:
            logger.error(f'status_code: {response.status_code}, body={response.text}')
            return response.status_code, None, json.loads(response.text).get('error', {})

    def equip(self, character: CharacterSchemaExtension, item, slot, quantity) -> Tuple[int, Optional[EquipRequestSchema], Optional[dict]]:
        url = f'/my/{character.name}/action/equip'
        body = {'code': item, 'slot': slot, 'quantity': quantity}
        response = self.rest_client.post(url, json=body, delay_until=character.cooldown_expiration)
        if response.status_code == 200:
            return response.status_code, extract_response(response, EquipRequestSchema), None
        else:
            logger.error(f'status_code: {response.status_code}, body={response.text}')
            return response.status_code, None, json.loads(response.text).get('error', {})

    def unequip(self, character: CharacterSchemaExtension, slot, quantity) -> Tuple[int, Optional[EquipRequestSchema], Optional[dict]]:
        url = f'/my/{character.name}/action/unequip'
        body = {'slot': slot, 'quantity': quantity}
        response = self.rest_client.post(url, json=body, delay_until=character.cooldown_expiration)
        if response.status_code == 200:
            return response.status_code, extract_response(response, EquipRequestSchema), None
        elif response.status_code == 483:
            return response.status_code, None, json.loads(response.text).get('error', {})
        else:
            logger.error(f'status_code: {response.status_code}, body={response.text}')
            return response.status_code, None, json.loads(response.text).get('error', {})

    def fight(
        self, character: CharacterSchemaExtension, participants: List[CharacterSchemaExtension] = None
    ) -> Tuple[int, Optional[CharacterFightDataSchema], Optional[dict]]:
        url = f'/my/{character.name}/action/fight'

        if participants:
            body = {'participants': [p.name for p in participants]}
            response = self.rest_client.post(url, json=body, delay_until=max(c.cooldown_expiration for c in [character, *participants]))
        else:
            response = self.rest_client.post(url, delay_until=character.cooldown_expiration)
        if response.status_code == 200:
            return response.status_code, extract_response(response, CharacterFightDataSchema), None
        elif response.status_code == 497:
            return response.status_code, None, json.loads(response.text).get('error', {})
        else:
            logger.error(f'status_code: {response.status_code}, body={response.text}')
            return response.status_code, None, json.loads(response.text).get('error', {})

    def gather(self, character: CharacterSchemaExtension) -> Tuple[int, Optional[SkillDataSchema], Optional[dict]]:
        url = f'/my/{character.name}/action/gathering'
        response = self.rest_client.post(url, delay_until=character.cooldown_expiration)
        if response.status_code == 200:
            return response.status_code, extract_response(response, SkillDataSchema), None
        else:
            if response.status_code != 497:
                logger.error(f'status_code: {response.status_code}, body={response.text}')
            return response.status_code, None, json.loads(response.text).get('error', {})

    def craft(self, character: CharacterSchemaExtension, item: str, quantity: int = 1) -> Tuple[int, Optional[SkillDataSchema], Optional[dict]]:
        url = f'/my/{character.name}/action/crafting'
        body = {'code': item, 'quantity': quantity}
        response = self.rest_client.post(url, json=body, delay_until=character.cooldown_expiration)

        match response.status_code:
            case 200:
                return response.status_code, extract_response(response, SkillDataSchema), None
            case 478:
                return response.status_code, None, json.loads(response.text).get('error', {})
            case _:
                logger.error(f'status_code: {response.status_code}, body={response.text}')
                return response.status_code, None, json.loads(response.text).get('error', {})

    def deposit(
        self, character: CharacterSchemaExtension, item_list: List[Dict[str, Any]]
    ) -> Tuple[int, Optional[BankItemTransactionSchema], Optional[dict]]:
        url = f'/my/{character.name}/action/bank/deposit/item'
        response = self.rest_client.post(url, json=item_list, delay_until=character.cooldown_expiration)
        if response.status_code == 200:
            return response.status_code, extract_response(response, BankItemTransactionSchema), None
        elif response.status_code == 462 or response.status_code == 598:
            return response.status_code, None, json.loads(response.text).get('error', {})
        else:
            logger.error(f'status_code: {response.status_code}, body={response.text}')
            return response.status_code, None, json.loads(response.text).get('error', {})

    def deposit_gold(self, character: CharacterSchemaExtension, quantity) -> Tuple[int, Optional[BankGoldTransactionSchema], Optional[dict]]:
        url = f'/my/{character.name}/action/bank/deposit/gold'
        body = {'quantity': quantity}
        response = self.rest_client.post(url, json=body, delay_until=character.cooldown_expiration)
        if response.status_code == 200:
            return response.status_code, extract_response(response, BankGoldTransactionSchema), None
        else:
            logger.error(f'status_code: {response.status_code}, body={response.text}')
            return response.status_code, None, json.loads(response.text).get('error', {})

    def recycle(self, character: CharacterSchemaExtension, item, quantity) -> Tuple[int, Optional[RecyclingDataSchema], Optional[dict]]:
        url = f'/my/{character.name}/action/recycling'
        body = {'code': item, 'quantity': quantity}
        response = self.rest_client.post(url, json=body, delay_until=character.cooldown_expiration)
        if response.status_code == 200:
            return response.status_code, extract_response(response, RecyclingDataSchema), None
        else:
            if response.status_code != 598:
                logger.error(f'status_code: {response.status_code}, body={response.text}')
            return response.status_code, None, json.loads(response.text).get('error', {})

    def withdraw(
        self, character: CharacterSchemaExtension, item_list: List[Dict[str, Any]]
    ) -> Tuple[int, Optional[BankItemTransactionSchema], Optional[dict]]:
        url = f'/my/{character.name}/action/bank/withdraw/item'

        response = self.rest_client.post(url, json=item_list, delay_until=character.cooldown_expiration)
        if response.status_code == 200:
            return response.status_code, extract_response(response, BankItemTransactionSchema), None
        else:
            if response.status_code != 598:
                logger.error(f'status_code: {response.status_code}, body={response.text}, request={item_list}')
            return response.status_code, None, json.loads(response.text).get('error', {})

    def withdraw_gold(self, character: CharacterSchemaExtension, quantity) -> Tuple[int, Optional[BankGoldTransactionSchema], Optional[dict]]:
        url = f'/my/{character.name}/action/bank/withdraw/gold'
        body = {'quantity': quantity}
        response = self.rest_client.post(url, json=body, delay_until=character.cooldown_expiration)
        if response.status_code == 200:
            return response.status_code, extract_response(response, BankGoldTransactionSchema), None
        else:
            logger.error(f'status_code: {response.status_code}, body={response.text}')
            return response.status_code, None, json.loads(response.text).get('error', {})

    def buy_bank_expansion(self, character: CharacterSchemaExtension) -> Tuple[int, Optional[BankExtensionTransactionSchema], Optional[dict]]:
        url = f'/my/{character.name}/action/bank/buy_expansion'
        response = self.rest_client.post(url, delay_until=character.cooldown_expiration)
        if response.status_code == 200:
            return response.status_code, extract_response(response, BankExtensionTransactionSchema), None
        else:
            logger.error(f'status_code: {response.status_code}, body={response.text}')
            return response.status_code, None, json.loads(response.text).get('error', {})

    def cancel_order(self, character: CharacterSchemaExtension, order_id: str) -> Tuple[int, Optional[GETransactionListSchema], Optional[dict]]:
        url = f'/my/{character.name}/action/grandexchange/cancel'
        body = {'id': order_id}
        response = self.rest_client.post(url, json=body, delay_until=character.cooldown_expiration)
        if response.status_code == 200:
            return response.status_code, extract_response(response, GETransactionListSchema), None
        else:
            logger.error(f'status_code: {response.status_code}, body={response.text}')
            return response.status_code, None, json.loads(response.text).get('error', {})

    def buy_item(self, character: CharacterSchemaExtension, order_id, quantity) -> Tuple[int, Optional[GETransactionListSchema], Optional[dict]]:
        url = f'/my/{character.name}/action/grandexchange/buy'
        body = {
            'id': order_id,
            'quantity': quantity,
        }
        response = self.rest_client.post(url, json=body, delay_until=character.cooldown_expiration)
        if response.status_code == 200:
            return response.status_code, extract_response(response, GETransactionListSchema), None
        else:
            logger.error(f'status_code: {response.status_code}, body={response.text}')
            return response.status_code, None, json.loads(response.text).get('error', {})

    def fill_order(self, character: CharacterSchemaExtension, order_id, quantity) -> Tuple[int, Optional[GETransactionListSchema], Optional[dict]]:
        url = f'/my/{character.name}/action/grandexchange/fill'
        body = {
            'id': order_id,
            'quantity': quantity,
        }
        response = self.rest_client.post(url, json=body, delay_until=character.cooldown_expiration)
        if response.status_code == 200:
            return response.status_code, extract_response(response, GETransactionListSchema), None
        else:
            logger.error(f'status_code: {response.status_code}, body={response.text}')
            return response.status_code, None, json.loads(response.text).get('error', {})

    def sell_item(
        self, character: CharacterSchemaExtension, item_code: str, quantity: int, unit_price: int
    ) -> Tuple[int, Optional[GEOrderTransactionSchema], Optional[dict]]:
        url = f'/my/{character.name}/action/grandexchange/create-sell-order'
        body = {'code': item_code, 'quantity': quantity, 'price': unit_price}
        response = self.rest_client.post(url, json=body, delay_until=character.cooldown_expiration)
        if response.status_code == 200:
            return response.status_code, extract_response(response, GEOrderTransactionSchema), None
        else:
            logger.error(f'status_code: {response.status_code}, body={response.text}')
            return response.status_code, None, json.loads(response.text).get('error', {})

    def buy_npc(
        self, character: CharacterSchemaExtension, item_code, quantity
    ) -> Tuple[int, Optional[NpcMerchantTransactionSchema], Optional[dict]]:
        url = f'/my/{character.name}/action/npc/buy'
        body = {
            'code': item_code,
            'quantity': quantity,
        }
        response = self.rest_client.post(url, json=body, delay_until=character.cooldown_expiration)
        if response.status_code == 200:
            return response.status_code, extract_response(response, NpcMerchantTransactionSchema), None
        else:
            logger.error(f'status_code: {response.status_code}, body={response.text}')
            return response.status_code, None, json.loads(response.text).get('error', {})

    def sell_npc(
        self, character: CharacterSchemaExtension, item_code, quantity
    ) -> Tuple[int, Optional[NpcMerchantTransactionSchema], Optional[dict]]:
        url = f'/my/{character.name}/action/npc/sell'
        body = {
            'code': item_code,
            'quantity': quantity,
        }
        response = self.rest_client.post(url, json=body, delay_until=character.cooldown_expiration)
        if response.status_code == 200:
            return response.status_code, extract_response(response, NpcMerchantTransactionSchema), None
        else:
            logger.error(f'status_code: {response.status_code}, body={response.text}')
            return response.status_code, None, json.loads(response.text).get('error', {})

    def accept_task(self, character: CharacterSchemaExtension) -> Tuple[int, Optional[TaskDataSchema], Optional[dict]]:
        url = f'/my/{character.name}/action/task/new'
        response = self.rest_client.post(url, delay_until=character.cooldown_expiration)
        if response.status_code == 200:
            return response.status_code, extract_response(response, TaskDataSchema), None
        else:
            logger.error(f'status_code: {response.status_code}, body={response.text}')
            return response.status_code, None, json.loads(response.text).get('error', {})

    def complete_task(self, character: CharacterSchemaExtension) -> Tuple[int, Optional[RewardDataSchema], Optional[dict]]:
        url = f'/my/{character.name}/action/task/complete'
        response = self.rest_client.post(url, delay_until=character.cooldown_expiration)
        if response.status_code == 200:
            return response.status_code, extract_response(response, RewardDataSchema), None
        else:
            logger.error(f'status_code: {response.status_code}, body={response.text}')
            return response.status_code, None, json.loads(response.text).get('error', {})

    def cancel_task(self, character: CharacterSchemaExtension) -> Tuple[int, Optional[TaskCancelledSchema], Optional[dict]]:
        url = f'/my/{character.name}/action/task/cancel'
        response = self.rest_client.post(url, delay_until=character.cooldown_expiration)
        if response.status_code == 200:
            return response.status_code, extract_response(response, TaskCancelledSchema), None
        else:
            logger.error(f'status_code: {response.status_code}, body={response.text}')
            return response.status_code, None, json.loads(response.text).get('error', {})

    def use_item(self, character: CharacterSchemaExtension, item: str, quantity: int) -> Tuple[int, Optional[UseItemSchema], Optional[dict]]:
        url = f'/my/{character.name}/action/use'
        body = {'code': item, 'quantity': quantity}
        response = self.rest_client.post(url, json=body, delay_until=character.cooldown_expiration)
        if response.status_code == 200:
            return response.status_code, extract_response(response, UseItemSchema), None
        else:
            logger.error(f'status_code: {response.status_code}, body={response.text}')
            return response.status_code, None, json.loads(response.text).get('error', {})

    def claim_pending_item(
        self, character: CharacterSchemaExtension, _id: str
    ) -> Tuple[int, Optional[ClaimPendingItemDataSchema], Optional[dict]]:
        url = f'/my/{character.name}/action/claim_item/{_id}'
        response = self.rest_client.post(url, delay_until=character.cooldown_expiration)
        if response.status_code == 200:
            return response.status_code, extract_response(response, ClaimPendingItemDataSchema), None
        else:
            logger.error(f'status_code: {response.status_code}, body={response.text}')
            return response.status_code, None, json.loads(response.text).get('error', {})

    def trade(self, character: CharacterSchemaExtension, item: str, quantity: int) -> Tuple[int, Optional[TaskTradeDataSchema], Optional[dict]]:
        url = f'/my/{character.name}/action/task/trade'
        body = {'code': item, 'quantity': quantity}
        response = self.rest_client.post(url, json=body, delay_until=character.cooldown_expiration)
        if response.status_code == 200:
            return response.status_code, extract_response(response, TaskTradeDataSchema), None
        else:
            logger.error(f'status_code: {response.status_code}, body={response.text}')
            return response.status_code, None, json.loads(response.text).get('error', {})

    def exchange(self, character: CharacterSchemaExtension) -> Tuple[int, Optional[RewardDataSchema], Optional[dict]]:
        url = f'/my/{character.name}/action/task/exchange'
        response = self.rest_client.post(url, delay_until=character.cooldown_expiration)
        if response.status_code == 200:
            return response.status_code, extract_response(response, RewardDataSchema), None
        else:
            logger.error(f'status_code: {response.status_code}, body={response.text}')
            return response.status_code, None, json.loads(response.text).get('error', {})

    def christmas_exchange(self, character: CharacterSchemaExtension) -> Tuple[int, Optional[RewardDataSchema], Optional[dict]]:
        url = f'/my/{character.name}/action/christmas/exchange'
        response = self.rest_client.post(url, delay_until=character.cooldown_expiration)
        if response.status_code == 200:
            return response.status_code, extract_response(response, RewardDataSchema), None
        else:
            logger.error(f'status_code: {response.status_code}, body={response.text}')
            return response.status_code, None, json.loads(response.text).get('error', {})

    def delete_item(
        self, character: CharacterSchemaExtension, item: str, quantity: int = 1
    ) -> Tuple[int, Optional[DeleteItemSchema], Optional[dict]]:
        url = f'/my/{character.name}/action/delete'
        body = {'code': item, 'quantity': quantity}
        response = self.rest_client.post(url, json=body, delay_until=character.cooldown_expiration)

        match response.status_code:
            case 200:
                return response.status_code, extract_response(response, DeleteItemSchema), None
            case 478:
                return response.status_code, None, json.loads(response.text).get('error', {})
            case _:
                logger.error(f'status_code: {response.status_code}, body={response.text}')
                return response.status_code, None, json.loads(response.text).get('error', {})

    def rest(self, character: CharacterSchemaExtension) -> Tuple[int, Optional[CharacterRestDataSchema], Optional[dict]]:
        url = f'/my/{character.name}/action/rest'
        response = self.rest_client.post(url, delay_until=character.cooldown_expiration)
        if response.status_code == 200:
            return response.status_code, extract_response(response, CharacterRestDataSchema), None
        else:
            logger.error(f'status_code: {response.status_code}, body={response.text}')
            return response.status_code, None, json.loads(response.text).get('error', {})

    def give(
        self,
        giver: CharacterSchemaExtension,
        receiver: CharacterSchemaExtension,
        item_map: Dict[str, int],
    ) -> Tuple[int, Optional[GiveItemDataSchema], Optional[dict]]:
        url = f'/my/{giver.name}/action/give/item'
        item_list = [{'code': code, 'quantity': qty} for code, qty in item_map.items()]
        body = {'items': item_list, 'character': receiver.name}
        response = self.rest_client.post(url, json=body, delay_until=max(giver.cooldown_expiration, receiver.cooldown_expiration))
        if response.status_code == 200:
            return response.status_code, extract_response(response, GiveItemDataSchema), None
        else:
            logger.error(f'status_code: {response.status_code}, body={response.text}')
            return response.status_code, None, json.loads(response.text).get('error', {})


def extract_response(response, cls):
    return cls.from_dict(response.json().get('data', {}))
