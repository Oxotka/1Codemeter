import datetime


def path_to_repo():
    # Путь до локального репозитория
    # Например '/Users/user/dt-demo-configuration/'
    # или 'C:/Repo/GitConverter'
    return ''


def name_of_src():
    # Путь до src
    # Например 'DemoConfDT/src' или 'GitConverter/src'
    return "name/src/"


def name_of_branch():
    return "master"


def date_since():
    # Дата, с которой начинаем поиск
    # По умолчанию с начала прошлого года
    # Можно задать любую дату с помощью datetime - datetime.datetime(2016, 1, 1)
    previous_year = datetime.datetime.now().year - 1
    return datetime.datetime(previous_year, 1, 1)


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
    # Чтобы сделать отбор по верхней подсистеме, то можно указать только "Финансы.",
    # чтобы указать отбор по подчиненной подсистеме лучше указывать полный путь "Финансы.Банк"
    subsystems = []
    return subsystems


def save_to_md():
    # Сохранять статистику в файл markdown
    return True


def save_to_html():
    # Сохранять статистику в файл html
    return True


def save_to_xsl():
    # Сохранять статистику в файл excel
    return True


def save_to_mongo():
    # Сохранять статистику в mongoDB
    # TODO - WIP - https://github.com/Oxotka/1Codemeter/issues/1
    return True

