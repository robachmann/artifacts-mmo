from enum import Enum

from artifactsmmo.extensions import CharacterSchemaExtension
from artifactsmmo.quests.quests import Quest


class QuestProcessStatus(Enum):
    Abort = 'abort'
    Cancel = 'cancel'
    Complete = 'complete'
    Continue = 'continue'
    Ignore = 'ignore'
    Hibernate = 'hibernate'


class QuestProcessResult:
    def __init__(self, character: CharacterSchemaExtension = None, quest: Quest = None, result: QuestProcessStatus = None):
        self.character = character
        self.quest = quest
        self.result = result

    @classmethod
    def abort(cls, character: CharacterSchemaExtension, quest: Quest):
        return cls(character, quest, QuestProcessStatus.Abort)

    @classmethod
    def cancel(cls, character: CharacterSchemaExtension, quest: Quest = None):
        return cls(character, quest, QuestProcessStatus.Cancel)

    @classmethod
    def complete(cls, character: CharacterSchemaExtension, quest: Quest):
        return cls(character, quest, QuestProcessStatus.Complete)

    @classmethod
    def finish(cls, character: CharacterSchemaExtension, quest: Quest, cancelled: bool):
        if cancelled:
            return cls.cancel(character, quest)
        else:
            return cls.complete(character, quest)

    @classmethod
    def continue_quest(cls):
        return cls(result=QuestProcessStatus.Continue)

    @classmethod
    def ignore_quest(cls):
        return cls(result=QuestProcessStatus.Ignore)

    @classmethod
    def hibernate_quest(cls):
        return cls(result=QuestProcessStatus.Hibernate)
