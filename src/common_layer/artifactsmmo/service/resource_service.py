from collections import defaultdict
from itertools import chain
from typing import Dict, List, Optional

from artifactsmmo.client.client import Client
from artifactsmmo.extensions.resource_schema_extension import ResourceSchemaExtension
from artifactsmmo.models import EventSchema, ResourceSchema, GatheringSkill
from artifactsmmo.singleton import SingletonMeta


class ResourceService(metaclass=SingletonMeta):
    def __init__(self, client: Client):
        self.client = client
        self.__resources_map: Dict[str, ResourceSchemaExtension] = {}
        self.__resource_levels_map: Dict[int, List[ResourceSchemaExtension]] = defaultdict(list)
        self.__resource_drops_map: Dict[str, List[ResourceSchemaExtension]] = defaultdict(list)
        self.__resource_skills_map: Dict[str, List[ResourceSchemaExtension]] = defaultdict(list)

    def init_resources(self):
        all_resources: List[ResourceSchema] = self.client.get_all_resources()
        all_events: List[EventSchema] = self.client.get_all_events()
        event_resources: List[str] = [event.content.code for event in all_events if event.content.type == 'resource']

        for resource in all_resources:
            resource_ext = ResourceSchemaExtension(resource)
            resource_ext.is_event_drop = resource_ext.code in event_resources
            self.__resources_map[resource_ext.code] = resource_ext
            self.__resource_levels_map[resource_ext.level].append(resource_ext)
            self.__resource_skills_map[str(resource_ext.skill)].append(resource_ext)
            for drop in resource_ext.drops:
                self.__resource_drops_map[drop.code].append(resource_ext)

    def get_resource(self, code: str) -> Optional[ResourceSchemaExtension]:
        if not self.__resources_map:
            self.init_resources()
        return self.__resources_map.get(code)

    def get_resources_by_drop(self, drop_code: str) -> List[ResourceSchemaExtension]:
        if not self.__resource_drops_map:
            self.init_resources()
        return self.__resource_drops_map.get(drop_code, [])

    def get_resources_by_skill(self, skill: GatheringSkill | str) -> List[ResourceSchemaExtension]:
        if not self.__resource_skills_map:
            self.init_resources()
        return self.__resource_skills_map.get(str(skill), [])

    def get_resources_by_level(self, min_level: int, max_level: int) -> List[ResourceSchemaExtension]:
        if not self.__resource_levels_map:
            self.init_resources()
        return list(
            chain.from_iterable(
                self.__resource_levels_map[level] for level in range(min_level, max_level + 1) if level in self.__resource_levels_map
            )
        )
