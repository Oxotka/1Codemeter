import copy
import os
import posixpath
import re
from typing import Dict, List, Optional, Tuple

import git
from tqdm import tqdm

from src import save_to_mongo, settings


class StructureOfCodemeter:
    def __init__(self):
        self.path_to_repo = os.path.normpath(settings.path_to_repo())  # Путь до локального репозитория
        self.name_of_src = os.path.normpath(settings.name_of_src())  # Имя в папке с конфигурацией
        self.date_since = settings.date_since()  # Дата, с которой начинаем читать коммиты
        self.date_before = settings.date_before()  # Дата, до которой читаем коммиты
        self.exclude_subsystems = settings.exclude_subsystems()  # Исключаемые подсистемы
        self.include_subsystems = settings.include_subsystems()  # Включаемые подсистемы
        self.configuration_name = ''  # Имя конфигурации из файлов конфигурации
        self.commits = []  # Все подходящие коммиты, между датами date_since и date_before
        self.subsystems = []  # Служебный массив всех подсистем. Собирается из файлов конфигурации
        self.subsystem_by_object = {}  # Служебный словарь подсистем. {type: {object: [subsystem1]}}
        self.authors = {}  # Авторы в формате {емайл : имя}. Заполняется автоматически при чтении коммитов
        self.structure_of_conf = {}  # Итоговая структура конфигурации

    @staticmethod
    def single_to_plural(content):
        if content.startswith('FilterCriterion'):
            return content.replace("FilterCriterion", "FilterCriteria")
        if content.startswith('ChartOfCharacteristicTypes'):
            return content.replace("ChartOfCharacteristicTypes", "ChartsOfCharacteristicTypes")
        else:
            return content.replace(".", "s.", 1)

    def collect_data(self):
        if self.path_to_repo == '':
            print('Path to repo is empty. Please check settings.py')
            return

        path = os.path.join(self.path_to_repo, self.name_of_src)
        configuration = os.path.normpath('Configuration/Configuration.mdo')
        path_to_configuration = os.path.join(path, configuration)
        if not os.path.isfile(path_to_configuration):
            print('Configuration file is not found by path - {path}. Please check settings.py'.format(
                path=path_to_configuration))
            return

        self.get_configuration_name(path_to_configuration)
        self.get_subsystems_info(path_to_configuration, path)

        if settings.save_to_mongo():
            self.sync_to_mongo()

        self.get_commits_info()
        self.structure_by_content_and_subsystem()

    def get_configuration_name(self, path_to_configuration):
        reg_exp_pattern_name = '(?<=<value>).*?(?=</value>)'
        with open(path_to_configuration, mode='r', encoding='utf8') as f:
            file = f.read().encode('utf-8').decode('utf-8')
            m = re.search(reg_exp_pattern_name, file)
            if not (m is None):
                self.configuration_name = m.group()

    def get_subsystems_info(self, path_to_configuration, path):
        subsystem_path = os.path.normpath('Subsystems/')
        reg_exp_pattern_subsystem = '(?<=<subsystems>Subsystem.).*?(?=</subsystems>)'
        reg_exp_pattern_content = '(?<=<content>).*?(?=</content>)'

        upper_subsystems = []
        with open(path_to_configuration, mode='r', encoding='utf8') as f:
            file = f.read().encode('utf-8').decode('utf-8')
            for subsystem in re.findall(reg_exp_pattern_subsystem, file):
                upper_subsystems.append(subsystem)

        for subsystem in upper_subsystems:
            path_to_dir_subsystem = os.path.join(path, subsystem_path, subsystem)
            info_subsystem = self.info_about_subsystems(subsystem, '', path_to_dir_subsystem, reg_exp_pattern_content)
            self.subsystems.append(info_subsystem)

        if len(self.subsystems) == 0:
            return
        for subsystem in self.subsystems:
            self.get_subsystem_content_info(subsystem)

    def info_about_subsystems(self, subsystem, upper_subsystem, path, reg_exp_pattern_content):
        subsystem_name = os.path.join(path, subsystem + '.mdo')
        full_subsystem = subsystem
        if upper_subsystem != '':
            full_subsystem = f'{upper_subsystem}.{subsystem}'

        contents = []
        subsystems = []
        if os.path.isdir(os.path.join(path, 'Subsystems')):
            inner_subsystems = [f for f in os.listdir(os.path.join(path, 'Subsystems')) if f != '.DS_Store']
            for inner_subsystem in inner_subsystems:
                inner_subsystem_path = os.path.join(path, 'Subsystems', inner_subsystem)
                inner_info = self.info_about_subsystems(inner_subsystem,
                                                        full_subsystem, inner_subsystem_path, reg_exp_pattern_content)
                subsystems.append(inner_info)

        with open(subsystem_name, mode='r', encoding='utf8') as f:
            file = f.read().encode('utf-8').decode('utf-8')
            for content in re.findall(reg_exp_pattern_content, file):
                contents.append(content)

        return {full_subsystem: {'subsystems': subsystems, 'contents': contents}}

    def get_subsystem_content_info(self, subsystem):
        for info in subsystem:
            if len(subsystem.get(info).get('subsystems')) > 0:
                for inner_subsystem in subsystem.get(info).get('subsystems'):
                    self.get_subsystem_content_info(inner_subsystem)

            for content in subsystem.get(info).get('contents'):
                elements = self.single_to_plural(content).split('.')
                if len(elements) != 2:
                    continue
                type_name = elements[0]
                object_name = elements[1]
                type_info = self.subsystem_by_object.get(type_name, {})
                object_info = type_info.get(object_name, [])
                if info not in object_info:
                    object_info.append(info)
                type_info[object_name] = object_info
                self.subsystem_by_object[type_name] = type_info

    def _src_posix(self) -> str:
        return self.name_of_src.replace('\\', '/').strip('/')

    def _build_repo_key(self, branch: str) -> str:
        return '{repo}::{branch}::{src}'.format(
            repo=os.path.abspath(self.path_to_repo),
            branch=branch,
            src=self._src_posix(),
        )

    @staticmethod
    def _normalize_git_path(path: str) -> str:
        return path.replace('\\', '/').strip()

    def _paths_from_stats_key(self, path_key: str) -> List[str]:
        normalized = self._normalize_git_path(path_key)
        if '=>' not in normalized:
            return [normalized]

        if '{' in normalized and '}' in normalized:
            start = normalized.find('{')
            end = normalized.rfind('}')
            if start < end:
                prefix = normalized[:start]
                middle = normalized[start + 1:end]
                suffix = normalized[end + 1:]
                if '=>' in middle:
                    old_part, new_part = middle.split('=>', 1)
                    return [
                        self._normalize_git_path(prefix + old_part.strip() + suffix),
                        self._normalize_git_path(prefix + new_part.strip() + suffix),
                    ]

        old_part, new_part = normalized.split('=>', 1)
        return [self._normalize_git_path(old_part.strip()), self._normalize_git_path(new_part.strip())]

    def _is_subsystem_definition_path(self, path: str) -> bool:
        src = self._src_posix()
        configuration_path = '{src}/Configuration/Configuration.mdo'.format(src=src)
        normalized = self._normalize_git_path(path)
        if normalized == configuration_path:
            return True
        return normalized.startswith('{src}/Subsystems/'.format(src=src)) and normalized.endswith('.mdo')

    def _parse_type_and_object(self, repo_file: str) -> Tuple[Optional[str], Optional[str]]:
        normalized = self._normalize_git_path(repo_file)
        src_prefix = self._src_posix() + '/'
        if not normalized.startswith(src_prefix):
            return None, None

        relative = normalized[len(src_prefix):]
        parts = relative.split('/')
        if len(parts) >= 2:
            return parts[0], parts[1]

        if len(parts) == 1:
            converted = self.single_to_plural(parts[0])
            converted_parts = converted.split('.')
            if len(converted_parts) == 2:
                return converted_parts[0], converted_parts[1]

        return None, None

    def _get_tree(self, commit, path: str):
        tree = commit.tree
        if path == '':
            return tree

        for part in path.split('/'):
            if part == '':
                continue
            try:
                tree = tree / part
            except KeyError:
                return None
            if tree.type != 'tree':
                return None
        return tree

    def _read_blob_text(self, commit, path: str) -> Optional[str]:
        normalized = self._normalize_git_path(path)
        try:
            blob = commit.tree / normalized
        except KeyError:
            return None
        if blob.type != 'blob':
            return None
        return blob.data_stream.read().decode('utf-8', errors='ignore')

    def _list_subsystem_dirs(self, commit, path: str) -> List[str]:
        tree = self._get_tree(commit, path)
        if tree is None:
            return []
        return [item.name for item in tree if item.type == 'tree' and item.name != '.DS_Store']

    def _info_about_subsystems_for_commit(self, commit, subsystem, upper_subsystem, path, reg_exp_pattern_content):
        subsystem_name = posixpath.join(path, subsystem + '.mdo')
        full_subsystem = subsystem
        if upper_subsystem != '':
            full_subsystem = f'{upper_subsystem}.{subsystem}'

        contents = []
        subsystems = []
        inner_path = posixpath.join(path, 'Subsystems')
        for inner_subsystem in self._list_subsystem_dirs(commit, inner_path):
            inner_subsystem_path = posixpath.join(inner_path, inner_subsystem)
            inner_info = self._info_about_subsystems_for_commit(
                commit,
                inner_subsystem,
                full_subsystem,
                inner_subsystem_path,
                reg_exp_pattern_content,
            )
            subsystems.append(inner_info)

        file = self._read_blob_text(commit, subsystem_name)
        if file is not None:
            for content in re.findall(reg_exp_pattern_content, file):
                contents.append(content)

        return {full_subsystem: {'subsystems': subsystems, 'contents': contents}}

    def _append_subsystem_content_info(self, subsystem, subsystem_by_object):
        for info in subsystem:
            inner_subsystems = subsystem.get(info).get('subsystems')
            if len(inner_subsystems) > 0:
                for inner_subsystem in inner_subsystems:
                    self._append_subsystem_content_info(inner_subsystem, subsystem_by_object)

            for content in subsystem.get(info).get('contents'):
                elements = self.single_to_plural(content).split('.')
                if len(elements) != 2:
                    continue
                type_name = elements[0]
                object_name = elements[1]
                type_info = subsystem_by_object.get(type_name, {})
                object_info = type_info.get(object_name, [])
                if info not in object_info:
                    object_info.append(info)
                type_info[object_name] = object_info
                subsystem_by_object[type_name] = type_info

    def _get_subsystem_mapping_for_commit(self, commit) -> Dict[str, Dict[str, List[str]]]:
        src = self._src_posix()
        path_to_configuration = posixpath.join(src, 'Configuration', 'Configuration.mdo')
        reg_exp_pattern_subsystem = '(?<=<subsystems>Subsystem.).*?(?=</subsystems>)'
        reg_exp_pattern_content = '(?<=<content>).*?(?=</content>)'

        configuration_file = self._read_blob_text(commit, path_to_configuration)
        if configuration_file is None:
            return {}

        upper_subsystems = re.findall(reg_exp_pattern_subsystem, configuration_file)
        if len(upper_subsystems) == 0:
            return {}

        subsystems = []
        for subsystem in upper_subsystems:
            path_to_dir_subsystem = posixpath.join(src, 'Subsystems', subsystem)
            info_subsystem = self._info_about_subsystems_for_commit(
                commit,
                subsystem,
                '',
                path_to_dir_subsystem,
                reg_exp_pattern_content,
            )
            subsystems.append(info_subsystem)

        subsystem_by_object = {}
        for subsystem in subsystems:
            self._append_subsystem_content_info(subsystem, subsystem_by_object)

        return subsystem_by_object

    @staticmethod
    def _sorted_subsystem_mapping(mapping: Dict[str, Dict[str, List[str]]]) -> Dict[str, Dict[str, List[str]]]:
        sorted_mapping = {}
        for type_name in sorted(mapping.keys()):
            object_map = mapping.get(type_name, {})
            sorted_mapping[type_name] = {}
            for object_name in sorted(object_map.keys()):
                sorted_mapping[type_name][object_name] = sorted(object_map.get(object_name, []))
        return sorted_mapping

    def sync_to_mongo(self):
        uri = settings.mongo_uri()
        if uri == '':
            print('MongoDB synchronization skipped: mongo_uri is empty.')
            return

        try:
            storage = save_to_mongo.MongoStorage(
                uri=uri,
                db_name=settings.mongo_db_name(),
                changes_collection=settings.mongo_changes_collection(),
                subsystem_collection=settings.mongo_subsystem_history_collection(),
                sync_collection=settings.mongo_sync_collection(),
            )
            storage.ping()
        except Exception as e:
            print('MongoDB synchronization skipped due to connection error: {error}'.format(error=e))
            return

        repo = git.Repo(self.path_to_repo)
        branch = settings.name_of_branch()
        commits_newest = list(repo.iter_commits(branch))
        if len(commits_newest) == 0:
            print('MongoDB synchronization skipped: no commits found.')
            return

        repo_key = self._build_repo_key(branch)
        commit_shas = [commit.hexsha for commit in commits_newest]
        last_processed_sha = storage.get_last_processed_sha(repo_key)

        if last_processed_sha in commit_shas:
            last_processed_index = commit_shas.index(last_processed_sha)
            commits_to_process = list(reversed(commits_newest[:last_processed_index]))
            current_subsystem_map = self._get_subsystem_mapping_for_commit(commits_newest[last_processed_index])
        else:
            commits_to_process = list(reversed(commits_newest))
            current_subsystem_map = {}

        if len(commits_to_process) == 0:
            print('MongoDB synchronization: no new commits to process.')
            return

        print('')
        print('MongoDB synchronization has started')
        print('Commits to process: {count}'.format(count=len(commits_to_process)))

        with tqdm(total=len(commits_to_process), desc='Sync mongo', ncols=100, colour='blue') as pbar:
            for commit in commits_to_process:
                pbar.update(1)
                stats_files = commit.stats.files

                changed_paths = set()
                for stats_key in stats_files.keys():
                    for expanded_path in self._paths_from_stats_key(stats_key):
                        changed_paths.add(expanded_path)

                subsystem_definition_changed = False
                for path in changed_paths:
                    if self._is_subsystem_definition_path(path):
                        subsystem_definition_changed = True
                        break

                if subsystem_definition_changed or len(current_subsystem_map) == 0:
                    current_subsystem_map = self._get_subsystem_mapping_for_commit(commit)
                    storage.save_subsystem_snapshot(
                        {
                            'repo_key': repo_key,
                            'sha': commit.hexsha,
                            'date': commit.committed_datetime,
                            'author_email': commit.author.email,
                            'author_name': commit.author.name,
                            'subsystem_by_object': self._sorted_subsystem_mapping(current_subsystem_map),
                            'changed_subsystem_files': sorted(
                                [path for path in changed_paths if self._is_subsystem_definition_path(path)]
                            ),
                        }
                    )

                changes_batch = []
                for file_path_key, stat in stats_files.items():
                    expanded_paths = self._paths_from_stats_key(file_path_key)
                    file_path = expanded_paths[-1]
                    if not file_path.endswith('.bsl'):
                        continue
                    if not file_path.startswith(self._src_posix() + '/'):
                        continue

                    type_name, object_name = self._parse_type_and_object(file_path)
                    if type_name is None or object_name is None:
                        continue

                    subsystems = current_subsystem_map.get(type_name, {}).get(object_name, [])
                    changes_batch.append(
                        {
                            'repo_key': repo_key,
                            'sha': commit.hexsha,
                            'date': commit.committed_datetime,
                            'file': file_path,
                            'insert': stat.get('insertions', 0),
                            'delete': stat.get('deletions', 0),
                            'email': commit.author.email,
                            'name': commit.author.name,
                            'type': type_name,
                            'object': object_name,
                            'subsystems': sorted(subsystems),
                        }
                    )

                storage.save_change_batch(changes_batch)
                storage.set_last_processed_sha(repo_key, commit.hexsha, commit.committed_datetime)

        print('MongoDB synchronization completed')

    def get_commits_info(self):
        repo = git.Repo(self.path_to_repo)
        branch = settings.name_of_branch()
        commits = list(repo.iter_commits(branch))
        print('')
        print('Statistics collection has started')
        print('Please wait. It may take a long time...')
        print('')
        print('The number of all commits in the repository: {len}'.format(len=len(commits)))
        print('')
        if self.date_before is not None and self.date_since is not None:
            print('Processing is performed only between these dates: {since} and {before}'.format(
                since=self.date_since.date(), before=self.date_before.date()))
            print('Other commits will be skipped and the process may stop before the progress bar completes.')

        elif self.date_since is not None:
            print('Processing is performed only since {since}'.format(
                since=self.date_since.date()))
            print('Other commits will be skipped and the process may stop before the progress bar completes.')
        elif self.date_before is not None:
            print('Processing is performed only before {before}'.format(
                before=self.date_before.date()))
            print('Other commits will be skipped and the process may stop before the progress bar completes.')

        with tqdm(total=len(commits), desc='Get commits', ncols=100, colour='green') as pbar:
            for commit in commits:
                pbar.update(1)

                if self.date_before is not None \
                        and commit.committed_datetime.timestamp() > self.date_before.timestamp():
                    continue

                if self.date_since is not None \
                        and self.date_since.timestamp() >= commit.committed_datetime.timestamp():
                    print('Date of commit ({commit}) are earlier then date_since ({since})'.format(
                        commit=commit.committed_datetime.date(), since=self.date_since.date()))
                    print('It is okay, we stop get commit and go forward')
                    break

                for file in commit.stats.files:
                    if os.path.normpath(file).startswith(os.path.join(self.name_of_src, '')) \
                            and file.endswith('bsl'):
                        stat = {'date': commit.committed_datetime.date(),
                                'file': file,
                                'insert': commit.stats.files.get(file).get('insertions'),
                                'delete': commit.stats.files.get(file).get('deletions'),
                                'email': commit.author.email}
                        self.commits.append(stat)
                        self.authors[commit.author.email] = commit.author.name

    def summarize_info_to_contents(self):
        summarized = {}
        if len(self.commits) == 0:
            return summarized
        for commit in self.commits:
            file = commit.get('file')
            email = commit.get('email')
            file_info = summarized.get(file)
            if file_info is None:
                file_info = {email: {'insert': 0, 'delete': 0}}
            email_info = file_info.get(email)
            if email_info is None:
                email_info = {'insert': 0, 'delete': 0}
            email_info['insert'] = email_info.get('insert') + commit.get('insert')
            email_info['delete'] = email_info.get('delete') + commit.get('delete')
            file_info[email] = email_info
            summarized[file] = file_info

        return summarized

    def structure_by_content_and_subsystem(self):
        summarized = self.summarize_info_to_contents()
        structure_of_configuration = {}
        with tqdm(total=len(summarized), desc='Summarize info', ncols=100, colour='green') as pbar:
            for file in summarized:
                pbar.update(1)
                email_info = summarized.get(file)
                file = os.path.normpath(file)
                file = file.replace(os.path.join(self.name_of_src, ''), '')
                parts_of_name = file.split(os.path.sep)
                if len(parts_of_name) == 1:
                    continue
                    # TODO Это какие-то странные объекты и они считаются неправильно, поэтому отключил их.
                    #  Если включить, то статистика после этого едет. Возможно, это удаления или переименования
                    parts_of_name = self.single_to_plural(file).split('.')
                    type_name = parts_of_name[0]
                    object_name = parts_of_name[1]
                    content_object = 2
                else:
                    type_name = parts_of_name[0]  # example: AccumulationRegisters
                    object_name = parts_of_name[1]  # example: Взаиморасчеты
                    content_object = 2
                type_info = copy.deepcopy(structure_of_configuration.get(type_name, {}))
                object_info = copy.deepcopy(type_info.get(object_name, {}))
                info = object_info
                for i in range(content_object, len(parts_of_name)):
                    inner_info = info.get(parts_of_name[i])
                    if inner_info is None:
                        info.update({parts_of_name[i]: {}})
                        inner_info = info.get(parts_of_name[i])
                    info = inner_info
                    if i == len(parts_of_name) - 1:
                        info.update(email_info)
                type_info[object_name] = object_info
                skip = False
                subsystem_type = self.subsystem_by_object.get(type_name, {})
                subsystems = subsystem_type.get(object_name, [])
                if len(self.include_subsystems) > 0 and len(self.subsystem_by_object) > 0:
                    it_is_include = False
                    for include in self.include_subsystems:
                        if include != "" and include in subsystems:
                            it_is_include = True
                            break
                    skip = not it_is_include

                if len(self.exclude_subsystems) > 0 and len(self.subsystem_by_object) > 0:
                    for exclude in self.exclude_subsystems:
                        if exclude != "":
                            for object_subsystem in subsystems:
                                if exclude in object_subsystem:
                                    skip = True
                                    break
                if skip:
                    continue

                for email_info_by_author in email_info:
                    authors = copy.deepcopy(object_info.get('authors', {}))
                    if authors.get(email_info_by_author) is None:
                        upd_author = email_info.get(email_info_by_author, {})
                    else:
                        upd_author = copy.deepcopy(authors.get(email_info_by_author))
                        upd_author['insert'] = upd_author.get('insert', 0) + email_info.get(
                            email_info_by_author).get('insert', 0)
                        upd_author['delete'] = upd_author.get('delete', 0) + email_info.get(
                            email_info_by_author).get('delete', 0)
                    authors[email_info_by_author] = upd_author
                    object_info['authors'] = authors

                    authors = copy.deepcopy(type_info.get('authors', {}))
                    if authors.get(email_info_by_author) is None:
                        upd_author = email_info.get(email_info_by_author, {})
                    else:
                        upd_author = copy.deepcopy(authors.get(email_info_by_author))
                        upd_author['insert'] = upd_author.get('insert', 0) + email_info.get(
                            email_info_by_author).get('insert', 0)
                        upd_author['delete'] = upd_author.get('delete', 0) + email_info.get(
                            email_info_by_author).get('delete', 0)
                    authors[email_info_by_author] = upd_author
                    type_info['authors'] = authors

                    structure_authors = structure_of_configuration.get('authors', {})
                    if structure_authors.get(email_info_by_author) is None:
                        structure_author = email_info.get(email_info_by_author)
                    else:
                        structure_author = copy.deepcopy(structure_authors.get(email_info_by_author))

                        structure_author['insert'] = structure_author.get('insert', 0) + email_info.get(
                            email_info_by_author).get('insert', 0)
                        structure_author['delete'] = structure_author.get('delete', 0) + email_info.get(
                            email_info_by_author).get('delete', 0)
                    structure_authors[email_info_by_author] = structure_author

                    structure_of_configuration['authors'] = structure_authors
                type_info = dict(sorted(type_info.items()))
                structure_of_configuration.update({type_name: type_info})

        self.structure_of_conf = dict(sorted(structure_of_configuration.items()))
