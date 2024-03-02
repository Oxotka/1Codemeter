import datetime


def path_to_repo():
    # Путь до локального репозитория
    # Например '/Users/user/dt-demo-configuration/'
    # или 'C:/Repo/GitConverter'
    return '/Users/nikitaaripov/Documents/GitConverter/'


def name_of_src():
    # Путь до src
    # Например 'DemoConfDT/' или 'GitConverter/'
    return "GitConverter/"


def date_since():
    # Дата, с которой начинаем поиск
    # По умолчанию с начала текущего года
    # Можно задать любую дату с помощью datetime - datetime.datetime(2016, 1, 1)
    current_year = datetime.datetime.now().year
    return datetime.datetime(current_year, 1, 1)


def date_before():
    # Дата, до которой ведем поиск
    # По умолчанию до текущего момента
    # Можно задать любую дату с помощью datetime - datetime.datetime(2024, 12, 31)
    return datetime.datetime.now()


def include_subsystems():
    # Включаемые подсистемы
    # Отбор будет выполнен только по этим подсистемам. Остальные объекты не попадут в статистику
    subsystems = []
    return subsystems


def exclude_subsystems():
    # Если есть включаемые подсистемы, то исключаемые не нужны совсем
    if len(include_subsystems()) > 0:
        return []
    # Исключаемые подсистемы
    # Эти подсистемы не попадут в статистику. Подсистемы могут быть иерархические. В этом случае они указываются так:
    # "Финансы.Банк".
    # Чтобы сделать отбор по верхней подсистеме, то можно указать только "Финансы",
    # чтобы указать отбор по подчиненной подсистеме лучше указывать полный путь "Финансы.Банк"
    subsystems = ["Финансы.Банк"]
    return subsystems


def save_to_md():
    # Сохранять статистику в файл markdown
    return True


def save_to_excel():
    # Сохранять статистику в файл excel
    return True
