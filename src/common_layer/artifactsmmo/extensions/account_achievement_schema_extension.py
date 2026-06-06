from artifactsmmo.models import AccountAchievementSchema


class AccountAchievementSchemaExtension(AccountAchievementSchema):
    def __init__(self, base_obj: AccountAchievementSchema):
        super().__init__()
        self.__dict__.update(base_obj.__dict__)

        progress = total = 0
        types = set()
        targets = set()
        total_progress = []
        for o in self.objectives:
            progress += o.progress
            total += o.total
            total_progress.append(o.progress / o.total)
            if o.type:
                types.add(o.type)
            if o.target:
                targets.add(o.target)

        self.current = progress
        self.progress = progress
        self.total = total
        self.total_progress = (sum(total_progress) / len(total_progress)) if len(total_progress) > 1 else total_progress[0]

        self.type = ','.join(types) if types else None
        self.target = ','.join(targets) if targets else None

    def __hash__(self):
        return hash(self.name)
