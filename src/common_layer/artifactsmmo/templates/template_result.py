from typing import List

from artifactsmmo.service.tasks import Task
from artifactsmmo.service.until import Until


class TemplateResult:
    def __init__(self):
        self.status = None
        self.repeat_task = False
        self.hibernate_quest = False
        self.repeat_task_until: Until | None = None
        self.new_tasks: List[Task] = []
        self.should_clear_until = False

    def append(self, task: Task):
        self.new_tasks.append(task)

    def extend(self, tasks: List[Task]):
        for task in tasks:
            self.append(task)

    def repeat(self, until: Until = None):
        self.repeat_task = True
        self.repeat_task_until = until

    def hibernate(self):
        self.hibernate_quest = True

    def quest_status(self, quest_status: str):
        self.status = quest_status

    def clear_until(self):
        self.should_clear_until = True
