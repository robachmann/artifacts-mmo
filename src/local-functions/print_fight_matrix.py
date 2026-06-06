from local_environment import LocalEnvironment


class ReportFunction(LocalEnvironment):
    def handler(self):
        self.report.print_fight_matrix(send_message=True)


report_function = ReportFunction()


if __name__ == '__main__':
    report_function.handler()
