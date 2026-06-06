import json
import os


class XpMaps:
    def __init__(self):
        self.current_dir = os.path.dirname(__file__)

    def read_file(self, map_name: str) -> dict:
        file_name = f'xp_map_{map_name}.json'
        file_path = os.path.join(self.current_dir, file_name)

        try:
            with open(file_path) as file:
                return json.load(file)
        except:
            return {}
