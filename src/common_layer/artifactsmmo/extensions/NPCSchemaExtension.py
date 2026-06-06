from typing import Dict

from artifactsmmo.models import NPCItem, NPCSchema


class NPCSchemaExtension(NPCSchema):
    def __init__(self, base_obj: NPCSchema):
        super().__init__()
        self.__dict__.update(base_obj.__dict__)
        self.items: Dict[str, NPCItem] = {}
        self.is_event_npc = False

    def __hash__(self):
        return hash(self.code)
