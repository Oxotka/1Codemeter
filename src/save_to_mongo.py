import os
from pymongo import MongoClient
from pymongo.errors import DuplicateKeyError
from datetime import datetime
from src import settings


class MongoRepository:
    """Класс для работы с MongoDB репозиторием коммитов."""
    
    def __init__(self, connection_string=None, database_name=None):
        """
        Инициализация подключения к MongoDB.
        
        Args:
            connection_string: Строка подключения к MongoDB (по умолчанию localhost:27017)
            database_name: Имя базы данных (по умолчанию из settings)
        """
        if connection_string is None:
            connection_string = settings.mongo_connection_string()
        if database_name is None:
            database_name = settings.mongo_database_name()
        
        self.client = MongoClient(connection_string)
        self.db = self.client[database_name]
        self.commits_collection = self.db['commits']
        self.authors_collection = self.db['authors']
        self.metadata_collection = self.db['metadata']
        
        # Создаем индексы для оптимизации запросов
        self._create_indexes()
    
    def _create_indexes(self):
        """Создает индексы для оптимизации запросов."""
        # Составной уникальный индекс для коммита и файла (один коммит может содержать несколько файлов)
        self.commits_collection.create_index([('sha', 1), ('file', 1)], unique=True)
        # Индекс для быстрого поиска по SHA коммита
        self.commits_collection.create_index('sha')
        # Индекс для поиска по дате
        self.commits_collection.create_index('date')
        # Индекс для поиска по email автора
        self.commits_collection.create_index('email')
        # Индекс для поиска по типу и объекту
        self.commits_collection.create_index([('type', 1), ('object', 1)])
        # Индекс для поиска последнего обработанного коммита
        self.metadata_collection.create_index('key', unique=True)
    
    def save_commit(self, commit_data):
        """
        Сохраняет информацию о коммите в MongoDB.
        
        Args:
            commit_data: Словарь с данными коммита
            
        Returns:
            bool: True если коммит сохранен, False если уже существует
        """
        try:
            # Преобразуем date в datetime если это date объект
            if 'date' in commit_data and isinstance(commit_data['date'], datetime):
                commit_data['date'] = commit_data['date']
            elif 'date' in commit_data:
                # Если это date объект, преобразуем в datetime
                if hasattr(commit_data['date'], 'isoformat'):
                    commit_data['date'] = datetime.combine(commit_data['date'], datetime.min.time())
            
            # Добавляем timestamp создания записи
            commit_data['created_at'] = datetime.now()
            
            self.commits_collection.insert_one(commit_data)
            return True
        except DuplicateKeyError:
            # Коммит уже существует, пропускаем
            return False
    
    def save_author(self, email, name):
        """
        Сохраняет или обновляет информацию об авторе.
        
        Args:
            email: Email автора
            name: Имя автора
        """
        self.authors_collection.update_one(
            {'email': email},
            {'$set': {'email': email, 'name': name, 'updated_at': datetime.now()}},
            upsert=True
        )
    
    def get_last_processed_commit_sha(self):
        """
        Получает SHA последнего обработанного коммита.
        
        Returns:
            str: SHA последнего обработанного коммита или None
        """
        metadata = self.metadata_collection.find_one({'key': 'last_processed_commit_sha'})
        if metadata:
            return metadata.get('value')
        return None
    
    def set_last_processed_commit_sha(self, sha):
        """
        Устанавливает SHA последнего обработанного коммита.
        
        Args:
            sha: SHA коммита
        """
        self.metadata_collection.update_one(
            {'key': 'last_processed_commit_sha'},
            {'$set': {'key': 'last_processed_commit_sha', 'value': sha, 'updated_at': datetime.now()}},
            upsert=True
        )
    
    def commit_exists(self, sha):
        """
        Проверяет, существует ли хотя бы один файл из коммита с данным SHA.
        
        Args:
            sha: SHA коммита
            
        Returns:
            bool: True если коммит существует
        """
        return self.commits_collection.find_one({'sha': sha}) is not None
    
    def commit_file_exists(self, sha, file_path):
        """
        Проверяет, существует ли конкретный файл в коммите.
        
        Args:
            sha: SHA коммита
            file_path: Путь к файлу
            
        Returns:
            bool: True если файл уже обработан
        """
        return self.commits_collection.find_one({'sha': sha, 'file': file_path}) is not None
    
    def get_commits_count(self):
        """Возвращает количество сохраненных коммитов."""
        return self.commits_collection.count_documents({})
    
    def get_authors_count(self):
        """Возвращает количество уникальных авторов."""
        return self.authors_collection.count_documents({})
    
    def close(self):
        """Закрывает соединение с MongoDB."""
        self.client.close()


# Глобальный экземпляр репозитория
_repo = None


def get_repository():
    """Получает или создает глобальный экземпляр репозитория."""
    global _repo
    if _repo is None:
        _repo = MongoRepository()
    return _repo


def save(record):
    """
    Сохраняет запись о коммите в MongoDB (старый интерфейс для совместимости).
    
    Args:
        record: Словарь с данными коммита
    """
    repo = get_repository()
    repo.save_commit(record)
    if 'email' in record and 'name' in record:
        repo.save_author(record['email'], record['name'])
