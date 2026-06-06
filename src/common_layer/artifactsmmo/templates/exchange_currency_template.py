from artifactsmmo.extensions import CharacterSchemaExtension
from artifactsmmo.log.logger import logger
from artifactsmmo.service.execution_context import ExecutionContext
from artifactsmmo.service.tasks import Task
from artifactsmmo.templates.template_result import TemplateResult
from artifactsmmo.templates.template_strategy import TemplateStrategy


class ExchangeCurrencyTemplate(TemplateStrategy):
    def template(self) -> str:
        return 'exchange-currency'

    @staticmethod
    def describe_task(task: Task) -> str:
        return f'for {task.extra.get("item")}'

    def render(self, character: CharacterSchemaExtension, task: Task, quest_id: str = None, context: ExecutionContext = None) -> TemplateResult:
        template_result: TemplateResult = TemplateResult()

        item_code = task.extra['item']
        currency = task.extra['currency']
        keep_currency = int(task.extra.get('keep_currency', 0))

        bank_item_map = self.service.get_bank_items_map(task_id=task.task_id, character_name=character.name, context=context)
        currency_amount = bank_item_map.get(currency, 0) - keep_currency

        if currency_amount > 0:
            origin = self.service.get_item_origin(item_code)
            for npc_code, npc_offer in origin.npcs.items():
                if npc_offer.currency == currency and not npc_offer.is_event:
                    quantity = currency_amount // npc_offer.price
                    template_result.append(Task.buy_from_npc(item=item_code, npc=npc_code, quantity=quantity))
                    logger.info(f'Plan to buy {quantity}x {item_code} from {npc_code} for {quantity * npc_offer.price} {npc_offer.currency}')
                    break

        return template_result
