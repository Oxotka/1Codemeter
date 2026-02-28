from __future__ import annotations

import datetime
from typing import Any, Dict, Iterable, Optional

from pymongo import UpdateOne
from pymongo.mongo_client import MongoClient
from pymongo.server_api import ServerApi


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
