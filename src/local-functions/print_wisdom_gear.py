from local_environment import LocalEnvironment

from artifactsmmo.log.logger import logger


class ReportFunction(LocalEnvironment):
    def handler(self):
        for x, y in self.service.get_best_wisdom_gear_by_level(30).items():
            logger.info(f'{x}: {[z.code for z in y]}')


report_function = ReportFunction()


if __name__ == '__main__':
    report_function.handler()
