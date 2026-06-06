from time import sleep

from local_environment import LocalEnvironment

from artifactsmmo.service.execution_context import ExecutionContext
from artifactsmmo.service.helpers import character_4_name
from artifactsmmo.service.tasks import Task


class ReportFunction(LocalEnvironment):
    def handler(self):
        character = self.service.get_character_details(character_4_name())
        context = ExecutionContext(character.name)
        bank = self.service.get_bank_items_map()
        item_codes = [
            'wool',
            'gold_ore',
            'skeleton_skull',
            'cowhide',
            'snake_hide',
            'green_cloth',
            'flying_wing',
            'skeleton_bone',
        ]

        for item_code in item_codes:
            qty = bank.get(item_code, 0)
            mod = 200

            ttl, remainder = divmod(qty, mod)
            for _ in range(ttl):
                r = self.task_processor.process_task(Task.withdraw(item_code, mod), character, context=context)
                sleep(r.character.get_remaining_cooldown())
                r = self.task_processor.process_task(Task.delete_inventory(item_code, mod), character, context=context)
                sleep(r.character.get_remaining_cooldown())
            r = self.task_processor.process_task(Task.withdraw(item_code, remainder), character, context=context)
            sleep(r.character.get_remaining_cooldown())
            r = self.task_processor.process_task(Task.delete_inventory(item_code, remainder), character, context=context)
            sleep(r.character.get_remaining_cooldown())
        #
        # for order in ge:
        #     if order.quantity == 100 and order.price < 1000:
        #         r = self.task_processor.process_task(Task.cancel_order(order.id), character, context=context)
        #         sleep(r.character.get_remaining_cooldown())
        #         r = self.task_processor.process_task(Task.delete_inventory(order.code, order.quantity), character, context=context)
        #         sleep(r.character.get_remaining_cooldown())


report_function = ReportFunction()

if __name__ == '__main__':
    report_function.handler()
