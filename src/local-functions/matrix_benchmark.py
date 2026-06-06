from local_environment import LocalEnvironment


class ReportFunction(LocalEnvironment):
    def handler(self):
        self.report.print_fight_matrix(
            min_monster_level=1,
            print_console=False,
            send_message=True,
            skip_boss_monsters=True,
        )


report_function = ReportFunction()


if __name__ == '__main__':
    report_function.handler()
