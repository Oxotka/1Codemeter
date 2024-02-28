import datetime


def path_to_repo():
    return '/Users/nikitaaripov/Documents/dt-demo-configuration/'
    # return '/Users/nikitaaripov/Documents/GitConverter/'


def name_of_configuration():

    return "DemoConfDT/"
    # return 'GitConverter/'


def date_since():
    return datetime.datetime(2016, 1, 1)


def date_before():
    return datetime.datetime.now()


def include_subsystems():
    subsystems = []
    return subsystems


def exclude_subsystems():
    # Если есть включаемые подсистемы, то исключаемые не нужны совсем
    if len(include_subsystems()) > 0:
        return []
    subsystems = ["BlaBla"]
    return subsystems


def save_to_md():
    return True


def save_to_excel():
    return True
