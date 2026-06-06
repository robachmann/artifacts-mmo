from artifactsmmo.log.logger import logger
from artifactsmmo.service.tasks import Task
from local_environment import LocalEnvironment


class ReportFunction(LocalEnvironment):
    def handler(self):
        character = self.service.get_character_details(self.character_1_name)
        task = Task.equip_wisdom_gear('abc')
        result = self.task_processor.process_task(task, character)
        for idx, t in enumerate(result.new_tasks, 1):
            logger.info(f'{idx}/{len(result.new_tasks)}: {t.to_dict()}')


report_function = ReportFunction()


if __name__ == '__main__':
    report_function.handler()
