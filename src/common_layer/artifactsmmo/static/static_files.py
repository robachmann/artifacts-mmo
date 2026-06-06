import json
import os


class StaticFiles:
    def __init__(self):
        self.current_dir = os.path.dirname(__file__)

    def read_file(self, resource_name: str) -> dict:
        file_name = f'all_{resource_name}.json'
        file_path = os.path.join(self.current_dir, file_name)

        try:
            with open(file_path) as file:
                return json.load(file)
        except:
            return {}
