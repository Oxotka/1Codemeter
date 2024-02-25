
def path_to_repo():
    return '/Users/nikitaaripov/Documents/dt-demo-configuration/'
    # return '/Users/nikitaaripov/Documents/GitConverter/'


def name_of_configuration():

    return "DemoConfDT/"
    # return 'GitConverter/'


def include_subsystems():

    # subsystems = ["Финансы", "Закупки"]
    subsystems = []
    return subsystems


def exclude_subsystems():

    # Если есть включаемые подсистемы, то исключаемые не нужны совсем
    if len(include_subsystems()) > 0:
        return []

    # subsystems = ["Предприятие"]
    subsystems = []
    return subsystems



