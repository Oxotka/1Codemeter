"""
Скрипт для разового сканирования всего репозитория с возможностью прерывания и продолжения.

Этот скрипт обрабатывает все коммиты в репозитории от начала до конца,
сохраняя информацию в MongoDB. Можно прервать выполнение (Ctrl+C) и продолжить позже -
скрипт запомнит последний обработанный коммит и продолжит с него.
"""
import os
import signal
import git
from tqdm import tqdm
from src import settings
from src.save_to_mongo import MongoRepository
from src.collect_for_mongo import build_subsystem_structure, build_record


class RepositoryScanner:
    """Класс для сканирования репозитория и сохранения коммитов в MongoDB."""
    
    def __init__(self):
        """Инициализация сканера."""
        self.path_to_repo = os.path.normpath(settings.path_to_repo())
        self.name_of_src = os.path.normpath(settings.name_of_src())
        self.repo = None
        self.mongo_repo = None
        self.subsystem_by_object = None
        self.interrupted = False
        
        # Обработка сигнала прерывания
        signal.signal(signal.SIGINT, self._signal_handler)
        signal.signal(signal.SIGTERM, self._signal_handler)
    
    def _signal_handler(self, signum, frame):
        """Обработчик сигнала прерывания."""
        print('\n\nПолучен сигнал прерывания. Сохраняю прогресс...')
        self.interrupted = True
    
    def _process_commit(self, commit):
        """
        Обрабатывает один коммит и сохраняет информацию в MongoDB.
        
        Args:
            commit: Объект коммита GitPython
            
        Returns:
            int: Количество обработанных файлов
        """
        files_processed = 0
        
        try:
            stats = commit.stats.files
        except Exception:
            return 0
        
        for file_path in stats:
            file_stats = stats.get(file_path, {})
            record = build_record(
                commit, file_path, file_stats,
                self.subsystem_by_object, self.name_of_src
            )
            if record is None:
                continue
            
            if self.mongo_repo.commit_file_exists(commit.hexsha, record['file']):
                continue
            
            saved = self.mongo_repo.save_commit(record)
            if saved:
                files_processed += 1
            
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
        
        # Строим структуру подсистем для привязки объектов к подсистемам
        print('Построение структуры подсистем...')
        self.subsystem_by_object = build_subsystem_structure(
            self.path_to_repo, self.name_of_src
        )
        print('Структура подсистем готова.\n')
        
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
