import os
from collections import defaultdict
from typing import Dict, Set


from artifactsmmo.service.helpers import escape_string
from local_environment import LocalEnvironment


class ReportFunction(LocalEnvironment):
    def handler(self):
        all_items = list(self.service.get_items_by_type(item_type='resource'))

        lines = ['---', 'config:', '  layout: elk', '---', 'flowchart TD']
        draw_items = set()
        for item in all_items:
            if item.craft:
                draw_items.add(item.code)
                for craft in item.craft.items:
                    draw_items.add(craft.code)

        sub_graphs: Dict[str, Set[str]] = defaultdict(set)
        for item in all_items:
            if item.code in draw_items:
                lines.append(
                    f'  {item.code}@{{ img: "https://www.artifactsmmo.com/images/items/{item.code}.png", h: 60, w: 60, pos: "b", constraint: "on"}}'
                )
                #if item.craft:
                #    sub_graphs[str(item.craft.skill)].add(item.code)
                #elif item.subtype:
                sub_graphs[str(item.level)].add(item.code)

        lines.append('')
        lines.append('')

        for item in all_items:
            if item.craft:
                for craft in item.craft.items:
                    lines.append(
                        f'  {craft.code}["{escape_string(craft.code)}"] -- {craft.quantity}x --> {item.code}["{escape_string(item.code)}"]'
                    )

        lines.append('')
        lines.append('')

        for subtype, items in sub_graphs.items():
            lines.append(f' subgraph {subtype}["{subtype}"]')
            for subgraphitem in items:
                lines.append(f'        {subgraphitem}["{escape_string(subgraphitem)}"]')
            lines.append('  end')

        text = '\n'.join(lines)
        # logger.info(text)

        os.remove('mermaidchart.txt')
        with open('mermaidchart.txt', 'a') as file:
            file.write(text + '\n')


report_function = ReportFunction()


if __name__ == '__main__':
    report_function.handler()
