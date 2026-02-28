from __future__ import annotations

import datetime
from typing import Any, Dict, Iterable, Optional

from pymongo import UpdateOne
from pymongo.mongo_client import MongoClient
from pymongo.server_api import ServerApi

from src import settings


class MongoStorage:
    def __init__(
        self,
        uri: str,
        db_name: str,
        changes_collection: str,
        subsystem_collection: str,
        sync_collection: str,
    ) -> None:
        self.client = MongoClient(uri, server_api=ServerApi("1"))
        self.db = self.client[db_name]
        self.changes = self.db[changes_collection]
        self.subsystem_history = self.db[subsystem_collection]
        self.sync_state = self.db[sync_collection]
        self._ensure_indexes()

    def ping(self) -> None:
        self.client.admin.command("ping")

    def _ensure_indexes(self) -> None:
        self.changes.create_index(
            [("repo_key", 1), ("sha", 1), ("file", 1)],
            unique=True,
            name="uniq_repo_sha_file",
        )
        self.changes.create_index(
            [("repo_key", 1), ("date", 1), ("email", 1)],
            name="idx_changes_repo_date_email",
        )
        self.changes.create_index(
            [("repo_key", 1), ("type", 1), ("object", 1)],
            name="idx_changes_repo_type_object",
        )

        self.subsystem_history.create_index(
            [("repo_key", 1), ("sha", 1)],
            unique=True,
            name="uniq_repo_subsystem_snapshot",
        )
        self.subsystem_history.create_index(
            [("repo_key", 1), ("date", 1)],
            name="idx_subsystem_repo_date",
        )

        self.sync_state.create_index(
            [("repo_key", 1)],
            unique=True,
            name="uniq_repo_sync",
        )

    def get_last_processed_sha(self, repo_key: str) -> Optional[str]:
        doc = self.sync_state.find_one({"repo_key": repo_key})
        if doc is None:
            return None
        return doc.get("last_processed_sha")

    def set_last_processed_sha(
        self,
        repo_key: str,
        sha: str,
        committed_at: datetime.datetime,
    ) -> None:
        self.sync_state.update_one(
            {"repo_key": repo_key},
            {
                "$set": {
                    "repo_key": repo_key,
                    "last_processed_sha": sha,
                    "last_processed_at": committed_at,
                    "updated_at": datetime.datetime.utcnow(),
                }
            },
            upsert=True,
        )

    def save_change_batch(self, docs: Iterable[Dict[str, Any]]) -> None:
        operations = []
        for doc in docs:
            operations.append(
                UpdateOne(
                    {
                        "repo_key": doc.get("repo_key"),
                        "sha": doc.get("sha"),
                        "file": doc.get("file"),
                    },
                    {"$set": doc},
                    upsert=True,
                )
            )

        if operations:
            self.changes.bulk_write(operations, ordered=False)

    def save_subsystem_snapshot(self, doc: Dict[str, Any]) -> None:
        self.subsystem_history.update_one(
            {
                "repo_key": doc.get("repo_key"),
                "sha": doc.get("sha"),
            },
            {"$set": doc},
            upsert=True,
        )


class MongoRepository:
    """Legacy-compatible repository used by scan_repository.py and old docs."""

    def __init__(self, connection_string: Optional[str] = None, database_name: Optional[str] = None):
        if connection_string is None:
            connection_string = settings.mongo_connection_string()
        if database_name is None:
            database_name = settings.mongo_database_name()

        self.client = MongoClient(connection_string, server_api=ServerApi("1"))
        self.db = self.client[database_name]
        self.commits_collection = self.db["commits"]
        self.authors_collection = self.db["authors"]
        self.metadata_collection = self.db["metadata"]
        self._create_indexes()

    def _create_indexes(self):
        self.commits_collection.create_index([("sha", 1), ("file", 1)], unique=True)
        self.commits_collection.create_index("sha")
        self.commits_collection.create_index("date")
        self.commits_collection.create_index("email")
        self.commits_collection.create_index([("type", 1), ("object", 1)])
        self.metadata_collection.create_index("key", unique=True)

    def save_commit(self, commit_data: Dict[str, Any]) -> bool:
        sha = commit_data.get("sha")
        file_path = commit_data.get("file")
        if sha is None or file_path is None:
            return False

        doc = dict(commit_data)
        if "date" in doc and hasattr(doc["date"], "year") and not isinstance(doc["date"], datetime.datetime):
            doc["date"] = datetime.datetime.combine(doc["date"], datetime.datetime.min.time())

        doc["created_at"] = datetime.datetime.utcnow()

        result = self.commits_collection.update_one(
            {"sha": sha, "file": file_path},
            {"$setOnInsert": doc},
            upsert=True,
        )
        return result.upserted_id is not None

    def save_author(self, email: str, name: str):
        self.authors_collection.update_one(
            {"email": email},
            {"$set": {"email": email, "name": name, "updated_at": datetime.datetime.utcnow()}},
            upsert=True,
        )

    def get_last_processed_commit_sha(self) -> Optional[str]:
        metadata = self.metadata_collection.find_one({"key": "last_processed_commit_sha"})
        if metadata:
            return metadata.get("value")
        return None

    def set_last_processed_commit_sha(self, sha: str):
        self.metadata_collection.update_one(
            {"key": "last_processed_commit_sha"},
            {
                "$set": {
                    "key": "last_processed_commit_sha",
                    "value": sha,
                    "updated_at": datetime.datetime.utcnow(),
                }
            },
            upsert=True,
        )

    def commit_exists(self, sha: str) -> bool:
        return self.commits_collection.find_one({"sha": sha}) is not None

    def commit_file_exists(self, sha: str, file_path: str) -> bool:
        return self.commits_collection.find_one({"sha": sha, "file": file_path}) is not None

    def get_commits_count(self) -> int:
        return self.commits_collection.count_documents({})

    def get_authors_count(self) -> int:
        return self.authors_collection.count_documents({})

    def close(self):
        self.client.close()


_repo: Optional[MongoRepository] = None


def get_repository() -> MongoRepository:
    global _repo
    if _repo is None:
        _repo = MongoRepository()
    return _repo


def save(record: Dict[str, Any]):
    repo = get_repository()
    repo.save_commit(record)
    if "email" in record and "name" in record:
        repo.save_author(record["email"], record["name"])
