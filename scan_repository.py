"""
Скрипт для разового сканирования всего репозитория с возможностью прерывания и продолжения.

Этот скрипт обрабатывает все коммиты в репозитории от начала до конца,
сохраняя информацию в MongoDB. Можно прервать выполнение (Ctrl+C) и продолжить позже -
скрипт запомнит последний обработанный коммит и продолжит с него.
"""
import os
import sys
import signal
import git
from datetime import datetime
from tqdm import tqdm
from src import settings
from src.save_to_mongo import MongoRepository
from src.codemeter import StructureOfCodemeter


class RepositoryScanner:
    """Класс для сканирования репозитория и сохранения коммитов в MongoDB."""
    
    def __init__(self):
        """Инициализация сканера."""
        self.path_to_repo = os.path.normpath(settings.path_to_repo())
        self.name_of_src = os.path.normpath(settings.name_of_src())
        self.repo = None
        self.mongo_repo = None
        self.structure = None
        self.interrupted = False
        
        # Обработка сигнала прерывания
        signal.signal(signal.SIGINT, self._signal_handler)
        signal.signal(signal.SIGTERM, self._signal_handler)
    
    def _signal_handler(self, signum, frame):
        """Обработчик сигнала прерывания."""
        print('\n\nПолучен сигнал прерывания. Сохраняю прогресс...')
        self.interrupted = True
    
    def _extract_type_and_object(self, file_path):
        """
        Извлекает тип и объект из пути к файлу.
        
        Args:
            file_path: Путь к файлу относительно репозитория
            
        Returns:
            tuple: (type_name, object_name, content_path) или (None, None, None)
        """
        file_path = os.path.normpath(file_path)
        # Убираем префикс с именем src
        if file_path.startswith(self.name_of_src):
            file_path = file_path.replace(os.path.join(self.name_of_src, ''), '')
        
        parts = file_path.split(os.path.sep)
        
        if len(parts) < 2:
            return None, None, None
        
        type_name = parts[0]  # Например: AccumulationRegisters
        object_name = parts[1]  # Например: Взаиморасчеты
        
        # Остальная часть пути (если есть)
        content_path = os.path.sep.join(parts[2:]) if len(parts) > 2 else None
        
        return type_name, object_name, content_path
    
    def _get_subsystems_for_object(self, type_name, object_name):
        """
        Получает список подсистем для объекта.
        
        Args:
            type_name: Тип объекта
            object_name: Имя объекта
            
        Returns:
            list: Список подсистем
        """
        if self.structure is None:
            # Инициализируем структуру для получения информации о подсистемах
            try:
                self.structure = StructureOfCodemeter()
                self.structure.path_to_repo = self.path_to_repo
                self.structure.name_of_src = self.name_of_src
                
                # Получаем информацию о подсистемах
                path = os.path.join(self.path_to_repo, self.name_of_src)
                configuration = os.path.normpath('Configuration/Configuration.mdo')
                path_to_configuration = os.path.join(path, configuration)
                
                if os.path.isfile(path_to_configuration):
                    self.structure.get_configuration_name(path_to_configuration)
                    self.structure.get_subsystems_info(path_to_configuration, path)
                else:
                    # Если файл конфигурации не найден, создаем пустую структуру
                    self.structure.subsystem_by_object = {}
            except Exception as e:
                print(f'\nПредупреждение: не удалось загрузить информацию о подсистемах: {e}')
                # Создаем пустую структуру
                if self.structure is None:
                    self.structure = type('obj', (object,), {'subsystem_by_object': {}})()
        
        if not hasattr(self.structure, 'subsystem_by_object'):
            return []
        
        subsystem_type = self.structure.subsystem_by_object.get(type_name, {})
        subsystems = subsystem_type.get(object_name, [])
        return subsystems
    
    def _process_commit(self, commit):
        """
        Обрабатывает один коммит и сохраняет информацию в MongoDB.
        
        Args:
            commit: Объект коммита GitPython
            
        Returns:
            int: Количество обработанных файлов
        """
        files_processed = 0
        
        # Получаем статистику изменений
        try:
            stats = commit.stats.files
        except Exception:
            # Некоторые коммиты могут не иметь статистики (например, merge коммиты)
            # Пропускаем их
            return 0
        
        for file_path in stats:
            # Обрабатываем только .bsl файлы из выбранной конфигурации
            if not os.path.normpath(file_path).startswith(os.path.join(self.name_of_src, '')):
                continue
            if not file_path.endswith('.bsl'):
                continue
            
            # Извлекаем тип и объект
            type_name, object_name, content_path = self._extract_type_and_object(file_path)
            if type_name is None or object_name is None:
                continue
            
            # Получаем подсистемы для объекта
            subsystems = self._get_subsystems_for_object(type_name, object_name)
            
            # Получаем статистику изменений
            file_stats = stats.get(file_path, {})
            insertions = file_stats.get('insertions', 0)
            deletions = file_stats.get('deletions', 0)
            
            # Формируем запись для MongoDB
            commit_record = {
                'sha': commit.hexsha,
                'date': commit.committed_datetime,
                'file': file_path,
                'type': type_name,
                'object': object_name,
                'content': content_path,
                'subsystems': subsystems,
                'insert': insertions,
                'delete': deletions,
                'email': commit.author.email,
                'name': commit.author.name,
                'message': commit.message[:500] if commit.message else '',  # Ограничиваем длину сообщения
                'committed_date': commit.committed_datetime,
                'authored_date': commit.authored_datetime,
            }
            
            # Проверяем, не обработан ли уже этот файл
            if self.mongo_repo.commit_file_exists(commit.hexsha, file_path):
                continue
            
            # Сохраняем в MongoDB
            saved = self.mongo_repo.save_commit(commit_record)
            if saved:
                files_processed += 1
            
            # Сохраняем информацию об авторе
            self.mongo_repo.save_author(commit.author.email, commit.author.name)
        
        return files_processed
    
    def scan(self, parallel=False, max_workers=None):
        """
        Сканирует весь репозиторий и сохраняет коммиты в MongoDB.
        
        Args:
            parallel: Использовать ли параллельную обработку (НЕ РЕАЛИЗОВАНО)
                     Параллелизация несовместима с текущим подходом отслеживания
                     "последнего коммита". Для параллелизации нужен другой подход -
                     проверка каждого коммита на существование в БД перед обработкой.
            max_workers: Количество воркеров для параллельной обработки
        """
        # Проверяем путь к репозиторию
        if not self.path_to_repo or not os.path.isdir(self.path_to_repo):
            print(f'Ошибка: путь к репозиторию неверен: {self.path_to_repo}')
            print('Проверьте настройки в src/settings.py')
            return
        
        # Проверяем путь к конфигурации
        path = os.path.join(self.path_to_repo, self.name_of_src)
        if not os.path.isdir(path):
            print(f'Ошибка: путь к конфигурации неверен: {path}')
            print('Проверьте настройки в src/settings.py')
            return
        
        # Инициализируем подключения
        try:
            print('Подключение к репозиторию...')
            self.repo = git.Repo(self.path_to_repo)
            print('Подключение к MongoDB...')
            self.mongo_repo = MongoRepository()
            print('Подключение успешно!\n')
        except Exception as e:
            print(f'Ошибка при подключении: {e}')
            return
        
        # Получаем все коммиты
        branch = settings.name_of_branch()
        print(f'Получение списка коммитов из ветки {branch}...')
        try:
            all_commits = list(self.repo.iter_commits(branch))
        except Exception as e:
            print(f'Ошибка при получении коммитов: {e}')
            return
        
        total_commits = len(all_commits)
        print(f'Всего коммитов в репозитории: {total_commits}\n')
        
        # Получаем последний обработанный коммит
        last_processed_sha = self.mongo_repo.get_last_processed_commit_sha()
        start_index = 0
        
        if last_processed_sha:
            print(f'Найден последний обработанный коммит: {last_processed_sha[:8]}')
            # Находим индекс этого коммита
            for i, commit in enumerate(all_commits):
                if commit.hexsha == last_processed_sha:
                    start_index = i + 1
                    print(f'Продолжаем с коммита #{start_index + 1} из {total_commits}\n')
                    break
        else:
            print('Начинаем сканирование с начала репозитория\n')
        
        # Статистика
        total_files_processed = 0
        total_commits_processed = 0
        skipped_commits = 0
        
        # Обрабатываем коммиты
        with tqdm(total=total_commits, initial=start_index, desc='Обработка коммитов', 
                  ncols=100, colour='green') as pbar:
            for i in range(start_index, total_commits):
                if self.interrupted:
                    break
                
                commit = all_commits[i]
                
                try:
                    # Обрабатываем коммит (пропуск уже обработанных файлов происходит внутри _process_commit)
                    
                    # Обрабатываем коммит
                    files_count = self._process_commit(commit)
                    
                    if files_count > 0:
                        total_files_processed += files_count
                        total_commits_processed += 1
                    
                    # Сохраняем прогресс каждые 10 коммитов или после каждого коммита с файлами
                    if files_count > 0 and (total_commits_processed % 10 == 0 or i == total_commits - 1):
                        self.mongo_repo.set_last_processed_commit_sha(commit.hexsha)
                    elif files_count == 0 and i == total_commits - 1:
                        # Сохраняем прогресс даже если в последнем коммите нет файлов
                        self.mongo_repo.set_last_processed_commit_sha(commit.hexsha)
                    
                    pbar.update(1)
                    
                    # Обновляем описание прогресса
                    pbar.set_postfix({
                        'обработано': total_commits_processed,
                        'пропущено': skipped_commits,
                        'файлов': total_files_processed
                    })
                except Exception as e:
                    print(f'\nОшибка при обработке коммита {commit.hexsha[:8]}: {e}')
                    # Продолжаем обработку следующих коммитов
                    pbar.update(1)
                    continue
        
        # Сохраняем финальный прогресс
        if total_commits_processed > 0:
            last_commit = all_commits[min(start_index + total_commits_processed - 1, total_commits - 1)]
            self.mongo_repo.set_last_processed_commit_sha(last_commit.hexsha)
        
        # Выводим статистику
        print('\n' + '='*60)
        print('Сканирование завершено!')
        print('='*60)
        print(f'Всего коммитов в репозитории: {total_commits}')
        print(f'Обработано коммитов: {total_commits_processed}')
        print(f'Пропущено коммитов (уже в БД): {skipped_commits}')
        print(f'Обработано файлов: {total_files_processed}')
        print(f'Всего коммитов в MongoDB: {self.mongo_repo.get_commits_count()}')
        print(f'Всего авторов в MongoDB: {self.mongo_repo.get_authors_count()}')
        
        if self.interrupted:
            print('\n⚠️  Сканирование было прервано. Вы можете запустить скрипт снова,')
            print('   и он продолжит с последнего обработанного коммита.')
        else:
            print('\n✅ Все коммиты успешно обработаны!')
        
        # Закрываем соединения
        self.mongo_repo.close()


def main():
    """Главная функция."""
    print('='*60)
    print('Скрипт разового сканирования репозитория 1С')
    print('='*60)
    print()
    
    scanner = RepositoryScanner()
    scanner.scan()
    
    print('\nДля выхода нажмите Enter...')
    try:
        input()
    except:
        pass


if __name__ == '__main__':
    main()
