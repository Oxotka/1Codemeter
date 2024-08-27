import re
import os
import git
import copy
from tqdm import tqdm
from src import settings, save_to_mongo

class StructureOfCodemeter:
    def __init__(self):
        """Инициализация класса StructureOfCodemeter. 
        Устанавливает параметры репозитория, конфигурации и инициализирует необходимые структуры данных."""
        self.path_to_repo = os.path.normpath(settings.path_to_repo())  # Путь до локального репозитория
        self.name_of_src = os.path.normpath(settings.name_of_src())  # Имя папки с конфигурацией
        self.date_since = settings.date_since()  # Дата, с которой начинаем читать коммиты
        self.date_before = settings.date_before()  # Дата, до которой читаем коммиты
        self.exclude_subsystems = settings.exclude_subsystems()  # Исключаемые подсистемы
        self.include_subsystems = settings.include_subsystems()  # Включаемые подсистемы
        self.configuration_name = ''  # Имя конфигурации из файлов конфигурации
        self.commits = []  # Все подходящие коммиты между датами date_since и date_before
        self.subsystems = []  # Служебный массив всех подсистем
        self.subsystem_by_object = {}  # Словарь подсистем {type: {object: [subsystem1]}}
        self.authors = {}  # Авторы в формате {емайл : имя}
        self.structure_of_conf = {}  # Итоговая структура конфигурации

    @staticmethod
    def single_to_plural(content):
        """Преобразует имя объекта из единственного числа в множественное, если это необходимо.
        
        Args:
            content (str): Имя объекта.
        
        Returns:
            str: Имя объекта в множественном числе.
        """
        if content.startswith('FilterCriterion'):
            return content.replace("FilterCriterion", "FilterCriteria")
        if content.startswith('ChartOfCharacteristicTypes'):
            return content.replace("ChartOfCharacteristicTypes", "ChartsOfCharacteristicTypes")
        else:
            return content.replace(".", "s.", 1)

    def collect_data(self):
        """Собирает данные о конфигурации, подсистемах и коммитах.
        
        Проверяет путь к конфигурации и извлекает необходимую информацию.
        """
        if self.path_to_repo == '':
            print('Path to repo is empty. Please check settings.py')
            return
        
        # Проверка пути к конфигурации
        path = os.path.join(self.path_to_repo, self.name_of_src)
        configuration = os.path.normpath('Configuration/Configuration.mdo')
        path_to_configuration = os.path.join(path, configuration)
        
        if not os.path.isfile(path_to_configuration):
            print('Configuration file is not found by path - {path}. Please check settings.py'.format(
                path=path_to_configuration))
            return
        
        self.get_configuration_name(path_to_configuration)  # Получение имени конфигурации
        self.get_subsystems_info(path_to_configuration, path)  # Получение информации о подсистемах
        self.get_commits_info()  # Получение информации о коммитах
        self.structure_by_content_and_subsystem()  # Формирование структуры по контенту и подсистемам

    def get_configuration_name(self, path_to_configuration):
        """Извлекает имя конфигурации из файла конфигурации.
        
        Args:
            path_to_configuration (str): Путь к файлу конфигурации.
        """
        reg_exp_pattern_name = '(?<=<value>).*?(?=</value>)'
        with open(path_to_configuration, mode='r', encoding='utf8') as f:
            file = f.read().encode('utf-8').decode('utf-8')
            m = re.search(reg_exp_pattern_name, file)
            if not (m is None):
                self.configuration_name = m.group()

    def get_subsystems_info(self, path_to_configuration, path):
        """Получает информацию о подсистемах из файла конфигурации.
        
        Args:
            path_to_configuration (str): Путь к файлу конфигурации.
            path (str): Путь до локального репозитория.
        """
        subsystem_path = os.path.normpath('Subsystems/')
        reg_exp_pattern_subsystem = '(?<=<subsystems>Subsystem.).*?(?=</subsystems>)'
        reg_exp_pattern_content = '(?<=<content>).*?(?=</content>)'
        
        # Получение корневых подсистем
        upper_subsystems = []
        with open(path_to_configuration, mode='r', encoding='utf8') as f:
            file = f.read().encode('utf-8').decode('utf-8')
            for subsystem in re.findall(reg_exp_pattern_subsystem, file):
                upper_subsystems.append(subsystem)
        
        # Получение информации о подсистемах
        for subsystem in upper_subsystems:
            path_to_dir_subsystem = os.path.join(path, subsystem_path, subsystem)
            info_subsystem = self.info_about_subsystems(subsystem, '', path_to_dir_subsystem, reg_exp_pattern_content)
            self.subsystems.append(info_subsystem)
        
        # Получение информации о содержимом подсистем
        if len(self.subsystems) == 0:
            return
        for subsystem in self.subsystems:
            self.get_subsystem_content_info(subsystem)

    def info_about_subsystems(self, subsystem, upper_subsystem, path, reg_exp_pattern_content):
        """Получает информацию о подсистемах и их содержимом.
        
        Args:
            subsystem (str): Имя подсистемы.
            upper_subsystem (str): Имя верхней подсистемы.
            path (str): Путь к директории подсистемы.
            reg_exp_pattern_content (str): Регулярное выражение для поиска содержимого.
        
        Returns:
            dict: Информация о подсистеме и ее содержимом.
        """
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
        """Получает информацию о содержимом подсистемы и обновляет соответствующие структуры.
        
        Args:
            subsystem (dict): Информация о подсистеме.
        """
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

    def get_commits_info(self):
        """Получает информацию о коммитах в репозитории и сохраняет ее в структуру данных.
        
        Обрабатывает коммиты в заданном диапазоне дат и собирает статистику по изменениям.
        """
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
        
        save_to_mongodb = settings.save_to_mongo()
        
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
                    # Находим только в выбранной конфигурации и .bsl файлах
                    if os.path.normpath(file).startswith(os.path.join(self.name_of_src, '')) \
                            and file.endswith('bsl'):
                        stat = {'date': commit.committed_datetime.date(),
                                'file': file,
                                'insert': commit.stats.files.get(file).get('insertions'),
                                'delete': commit.stats.files.get(file).get('deletions'),
                                'email': commit.author.email}
                        self.commits.append(stat)
                        self.authors[commit.author.email] = commit.author.name
                        
                        # TODO добавить сохранение в MongoDB - добавить sha коммита, тип, объект и подсистему
                        if save_to_mongodb:
                            record_for_mongo = \
                              {'date': commit.committed_datetime.date(),
                               'file': file,
                               'insert': commit.stats.files.get(file).get('insertions'),
                               'delete': commit.stats.files.get(file).get('deletions'),
                               'email': commit.author.email,
                               'name': commit.author.name,
                               # 'sha': commit.sha,
                               # 'type':
                               # 'object': ''
                               # 'content': ''
                               # 'subsystems': [],
                               }
                            save_to_mongo.save(record_for_mongo)

    def summarize_info_to_contents(self):
        """Суммирует информацию о содержимом коммитов по файлам и авторам.
        
        Returns:
            dict: Суммированная информация о коммитах.
        """
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
        """Формирует итоговую структуру конфигурации на основе содержимого и подсистем.
        
        Обрабатывает информацию о коммитах и создает структуру, которая включает данные о типах,
        объектах, подсистемах и авторах.
        """
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
                
                type_name = parts_of_name[0]  # Пример: AccumulationRegisters
                object_name = parts_of_name[1]  # Пример: Взаиморасчеты
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
                
                # Проверка на включение/исключение подсистем
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
                
                # Статистика по объекту
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
                    
                    # Общая информация о статистике
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