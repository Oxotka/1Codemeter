"""
Скрипт полного/инкрементального обновления MongoDB из Git-репозитория.

Использует логику StructureOfCodemeter.sync_to_mongo:
- первый запуск: обрабатывает всю историю коммитов,
- следующие запуски: только новые коммиты после last_processed_sha,
- подсистемы рассчитываются по состоянию соответствующего коммита.
"""

import os

from src import settings
from src.codemeter import StructureOfCodemeter


def main():
    print('=' * 60)
    print('Синхронизация репозитория в MongoDB')
    print('=' * 60)

    if not settings.save_to_mongo():
        print('MongoDB выключен. Укажите CODEMETER_MONGO_URI или настройте mongo_uri() в settings.py')
        return

    structure = StructureOfCodemeter()

    if not structure.path_to_repo or not os.path.isdir(structure.path_to_repo):
        print(f'Ошибка: путь к репозиторию неверен: {structure.path_to_repo}')
        print('Проверьте настройки в src/settings.py -> path_to_repo()')
        return

    path_to_src = os.path.join(structure.path_to_repo, structure.name_of_src)
    if not os.path.isdir(path_to_src):
        print(f'Ошибка: путь к src неверен: {path_to_src}')
        print('Проверьте настройки в src/settings.py -> name_of_src()')
        return

    print('Параметры:')
    print(f'- repo: {structure.path_to_repo}')
    print(f'- src: {structure.name_of_src}')
    print(f'- branch: {settings.name_of_branch()}')
    print('')

    structure.sync_to_mongo()

    print('')
    print('Синхронизация завершена')


if __name__ == '__main__':
    main()
