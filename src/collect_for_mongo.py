"""
Модуль для сбора данных коммитов из репозитория для сохранения в MongoDB.

Собирает всю информацию без агрегации и без фильтрации по подсистемам:
- Строит структуру подсистем (тип → объект → подсистемы) из Configuration.mdo
- Итерирует все коммиты в репозитории
- Для каждого изменения .bsl файла формирует запись, готовую для MongoDB

Использует только path_to_repo, name_of_src, name_of_branch из settings.
"""

import os
import git
from src import settings
from src.codemeter import StructureOfCodemeter


def build_subsystem_structure(path_to_repo, name_of_src):
    """
    Строит структуру подсистем: тип → объект → [подсистемы].

    Args:
        path_to_repo: Путь к репозиторию
        name_of_src: Имя папки с конфигурацией (например, 'src' или 'DemoConfDT/src')

    Returns:
        dict: {type_name: {object_name: [subsystem1, subsystem2, ...]}}
        Пустой словарь, если Configuration.mdo не найден.
    """
    path = os.path.join(path_to_repo, name_of_src)
    configuration = os.path.normpath('Configuration/Configuration.mdo')
    path_to_configuration = os.path.join(path, configuration)

    if not os.path.isfile(path_to_configuration):
        return {}

    structure = StructureOfCodemeter()
    structure.path_to_repo = os.path.normpath(path_to_repo)
    structure.name_of_src = os.path.normpath(name_of_src)
    structure.get_configuration_name(path_to_configuration)
    structure.get_subsystems_info(path_to_configuration, path)
    return structure.subsystem_by_object


def _extract_type_object_content(file_path, name_of_src):
    """
    Извлекает тип, объект и content из пути к файлу.

    Returns:
        tuple: (type_name, object_name, content_path) или (None, None, None)
    """
    norm_path = os.path.normpath(file_path)
    prefix = os.path.join(os.path.normpath(name_of_src), '')
    if norm_path.startswith(prefix):
        relative = norm_path[len(prefix):]
    else:
        return None, None, None

    parts = relative.split(os.path.sep)
    if len(parts) < 2:
        return None, None, None

    type_name = parts[0]
    object_name = parts[1]
    content_path = os.path.sep.join(parts[2:]) if len(parts) > 2 else None
    return type_name, object_name, content_path


def build_record(commit, file_path, file_stats, subsystem_by_object, name_of_src):
    """
    Формирует одну запись для MongoDB по коммиту и файлу.

    Удобно для поштучной обработки (например, с проверкой на дубликаты
    и возобновлением после прерывания).

    Args:
        commit: Объект коммита GitPython
        file_path: Путь к файлу (как в commit.stats.files)
        file_stats: Статистика файла (insertions, deletions)
        subsystem_by_object: Структура подсистем из build_subsystem_structure
        name_of_src: Папка конфигурации

    Returns:
        dict: Запись для save_commit или None, если файл не .bsl или вне конфигурации
    """
    norm_path = os.path.normpath(file_path)
    name_of_src = os.path.normpath(name_of_src)
    if not norm_path.startswith(os.path.join(name_of_src, '')):
        return None
    if not norm_path.endswith('.bsl'):
        return None

    type_name, object_name, content_path = _extract_type_object_content(
        file_path, name_of_src
    )
    if type_name is None or object_name is None:
        return None

    subsystem_type = subsystem_by_object.get(type_name, {})
    subsystems = subsystem_type.get(object_name, [])

    insertions = file_stats.get('insertions', 0)
    deletions = file_stats.get('deletions', 0)

    return {
        'sha': commit.hexsha,
        'date': commit.committed_datetime,
        'file': norm_path,
        'type': type_name,
        'object': object_name,
        'content': content_path,
        'subsystems': subsystems,
        'insert': insertions,
        'delete': deletions,
        'email': commit.author.email,
        'name': commit.author.name,
        'message': (commit.message or '')[:500],
        'committed_date': commit.committed_datetime,
        'authored_date': commit.authored_datetime,
    }


def iter_commit_records(path_to_repo=None, name_of_src=None, name_of_branch=None):
    """
    Генератор записей для MongoDB по всем коммитам репозитория.

    Для каждого изменения .bsl файла в каждом коммите выдаёт словарь,
    готовый для сохранения в MongoDB (save_commit).

    Args:
        path_to_repo: Путь к репозиторию (по умолчанию из settings)
        name_of_src: Папка конфигурации (по умолчанию из settings)
        name_of_branch: Ветка (по умолчанию из settings)

    Yields:
        dict: Запись с полями sha, date, file, type, object, content,
              subsystems, insert, delete, email, name, message,
              committed_date, authored_date
    """
    path_to_repo = path_to_repo or settings.path_to_repo()
    name_of_src = name_of_src or settings.name_of_src()
    name_of_branch = name_of_branch or settings.name_of_branch()

    path_to_repo = os.path.normpath(path_to_repo)
    name_of_src = os.path.normpath(name_of_src)

    # Сначала строим структуру подсистем
    subsystem_by_object = build_subsystem_structure(path_to_repo, name_of_src)

    repo = git.Repo(path_to_repo)
    commits = list(repo.iter_commits(name_of_branch))

    for commit in commits:
        try:
            stats = commit.stats.files
        except Exception:
            continue

        for file_path in stats:
            file_stats = stats.get(file_path, {})
            record = build_record(
                commit, file_path, file_stats, subsystem_by_object, name_of_src
            )
            if record is not None:
                yield record
