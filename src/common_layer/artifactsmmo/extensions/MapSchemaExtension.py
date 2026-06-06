from typing import Dict

from artifactsmmo.models import MapSchema


class MapSchemaExtension(MapSchema):
    def __init__(self, base_obj: MapSchema, cluster_id: str):
        super().__init__()
        self.__dict__.update(base_obj.__dict__)

        self.cluster_id = cluster_id
        self.event_content: Dict[str, str] = {}

    def __hash__(self):
        return hash(self.map_id)
