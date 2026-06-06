from artifactsmmo.models import ResourceSchema


class ResourceSchemaExtension(ResourceSchema):
    def __init__(self, base_obj: ResourceSchema):
        super().__init__()
        self.__dict__.update(base_obj.__dict__)
        self.is_event_drop = False

    def __hash__(self):
        return hash(self.code)
