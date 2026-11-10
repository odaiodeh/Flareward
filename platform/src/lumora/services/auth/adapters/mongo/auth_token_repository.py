"""
MongoCredentialStore — implements :class:`CredentialStore` using MongoDB.

Index:
    - Unique lookup: ``(user_id, server_identifier)``

Sensitive fields (access_token, refresh_token) are encrypted at rest
using Fernet symmetric encryption when an encryption key is provided.
"""

from __future__ import annotations

import logging
from datetime import UTC, datetime

from pymongo import ASCENDING, MongoClient
from pymongo.collection import Collection

from lumora.services.auth.adapters.crypto import FieldCipher
from lumora.services.auth.credentials.models import StoredCredential, TokenStatus
from lumora.services.auth.credentials.ports import CredentialStore

logger = logging.getLogger(__name__)

_ENCRYPTED_FIELDS = ("access_token", "refresh_token")


class MongoCredentialStore(CredentialStore):
    def __init__(
        self,
        mongodb_ip: str = "127.0.0.1",
        mongodb_port: int = 27017,
        db_name: str = "lumora",
        coll_name: str = "credentials",
        encryption_key: str = "",
        *,
        collection: Collection | None = None,
    ) -> None:
        self._client = None
        if collection is None:
            self._client = MongoClient(f"mongodb://{mongodb_ip}:{mongodb_port}/")
            collection = self._client[db_name][coll_name]
        self._coll = collection
        try:
            self._cipher = FieldCipher(encryption_key) if encryption_key else None
            self._ensure_indexes()
        except Exception:
            self.close()
            raise

    def close(self) -> None:
        if self._client is not None:
            self._client.close()

    def _ensure_indexes(self) -> None:
        self._coll.create_index(
            [("user_id", ASCENDING), ("server_identifier", ASCENDING)],
            unique=True,
            name="uq_user_server",
        )

    # ------------------------------------------------------------------

    def upsert(self, credential: StoredCredential) -> None:
        doc = credential.model_dump()
        doc["server_identifier"] = credential.server_identifier.rstrip("/")
        doc["updated_at"] = datetime.now(UTC)
        if self._cipher:
            for field in _ENCRYPTED_FIELDS:
                if doc.get(field):
                    doc[field] = self._cipher.encrypt(doc[field])
        self._coll.update_one(
            {"user_id": credential.user_id, "server_identifier": doc["server_identifier"]},
            {"$set": doc},
            upsert=True,
        )

    def find_by_server(
        self,
        user_id: str,
        server_identifier: str,
        scheme_type: str = "",
    ) -> StoredCredential | None:
        normalized = server_identifier.rstrip("/")
        query = {
            "user_id": user_id,
            "server_identifier": normalized,
            "status": TokenStatus.ACTIVE.value,
        }
        if scheme_type:
            query["scheme_type"] = scheme_type
        doc = self._coll.find_one(query)
        return self._to_model(doc) if doc else None

    def delete(self, user_id: str, server_identifier: str) -> None:
        normalized = server_identifier.rstrip("/")
        self._coll.delete_one({"user_id": user_id, "server_identifier": normalized})

    def update_status(self, user_id: str, server_identifier: str, status: str) -> None:
        normalized = server_identifier.rstrip("/")
        self._coll.update_one(
            {"user_id": user_id, "server_identifier": normalized},
            {"$set": {"status": status, "updated_at": datetime.now(UTC)}},
        )

    # ------------------------------------------------------------------

    def _to_model(self, doc: dict) -> StoredCredential:
        doc.pop("_id", None)
        doc.pop("_expires_at", None)
        doc.pop("staged", None)
        doc.pop("server_url_normalised", None)
        doc.pop("mcp_server_url", None)
        doc.pop("server_url", None)
        doc.pop("auth_rid", None)
        if self._cipher:
            for field in _ENCRYPTED_FIELDS:
                if doc.get(field):
                    doc[field] = self._cipher.decrypt(doc[field])
        return StoredCredential.model_validate(doc)
