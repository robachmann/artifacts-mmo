from artifactsmmo.service.helpers import format_number
from local_environment import LocalEnvironment


class ReportFunction(LocalEnvironment):
    def handler(self):
        all_npc_items = self.client.get_all_npc_items()

        file_name = 'npc_items.txt'
        with open(file_name, 'a') as file:
            for item in all_npc_items:
                text = f"#     '{item.code}': '{item.npc}',"
                if item.currency == 'gold':
                    if item.buy_price and not item.sell_price:
                        text += f' # 🛒 buy only for {format_number(item.buy_price)}{item.currency.replace("gold", "g")} each'
                    elif item.sell_price and not item.buy_price:
                        text += f' # 💰 sell only for {format_number(item.sell_price)}{item.currency.replace("gold", "g")} each'
                file.write(text + '\n')


report_function = ReportFunction()


if __name__ == '__main__':
    report_function.handler()
