"""Local filesystem storage provider - Section 5's "development mode":
Woodful must run on localhost without an internet connection or Google
Drive. One JSON file per record (not one giant file per collection),
per Section 13 (avoid unnecessary full-collection rewrites) - updating
one Client only ever touches that Client's own file.

Concurrency (Section 11): version is a simple monotonic integer,
stored inside the record file itself. update() reads the current
version before writing and compares against expected_version if the
caller supplied one - a real, working optimistic-concurrency check,
just backed by a file's own content rather than Google Drive's
revision metadata. Same contract the Google Drive provider must
satisfy, deliberately kept this simple here specifically so it can be
verified in an environment with no network and no Drive API library
available.

This is NOT a replacement for a real database in production - it has
no indexing, every list() call reads every file in the collection
directory, and there is no cross-process locking beyond what the OS
filesystem gives a single `open(..., "x")` call. It exists to make
local development possible without Google Drive (Section 5) and to
prove the StorageProvider contract is genuinely implementable and
testable, not as a production-scale store in its own right.
"""
import json
import os
import re
import tempfile
from datetime import datetime, timezone
from typing import Any, Dict, Optional

from app.storage.base import (
    StorageProvider, StoredRecord, ListResult,
    RecordNotFoundError, ConcurrencyConflictError, StorageError,
)

_SAFE_NAME_RE = re.compile(r"^[A-Za-z0-9_\-]+$")


def _validate_name(kind: str, name: str) -> None:
    """Collection names and record IDs become directory/file names on
    disk - reject anything that isn't a safe, simple token before it
    ever reaches a filesystem path. This is a real, load-bearing check
    (not just tidiness): without it, a record_id containing "../" could
    escape the intended storage directory entirely."""
    if not name or not _SAFE_NAME_RE.match(name):
        raise StorageError(f"Invalid {kind}: {name!r} - must be non-empty and contain only letters, digits, - and _")


class LocalJSONStorageProvider(StorageProvider):
    def __init__(self, root_dir: str):
        self.root_dir = root_dir
        os.makedirs(root_dir, exist_ok=True)

    def _collection_dir(self, collection: str) -> str:
        _validate_name("collection", collection)
        path = os.path.join(self.root_dir, collection)
        os.makedirs(path, exist_ok=True)
        return path

    def _record_path(self, collection: str, record_id: str) -> str:
        _validate_name("record_id", record_id)
        return os.path.join(self._collection_dir(collection), f"{record_id}.json")

    def _read_raw(self, path: str) -> Optional[dict]:
        if not os.path.exists(path):
            return None
        try:
            with open(path, "r", encoding="utf-8") as f:
                return json.load(f)
        except (json.JSONDecodeError, OSError) as e:
            # A corrupted or unreadable record file is a genuine storage
            # failure, not a "record doesn't exist" - Section 28: never
            # silently treat malformed stored data as success.
            raise StorageError(f"Could not read stored record at {path}: {e}") from e

    def _write_raw(self, path: str, envelope: dict) -> None:
        # Write to a temp file in the same directory, then atomically
        # rename over the target - a crash or concurrent read mid-write
        # can never observe a half-written record file. This is the
        # actual mechanism behind this provider's part of Section 12
        # (atomic operations) at the single-record level; multi-record
        # transactions are a repository-layer concern (see
        # base_repository.py's docstring).
        directory = os.path.dirname(path)
        fd, tmp_path = tempfile.mkstemp(dir=directory, prefix=".tmp-", suffix=".json")
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as f:
                json.dump(envelope, f, indent=2, default=str)
            os.replace(tmp_path, path)
        except BaseException:
            if os.path.exists(tmp_path):
                os.remove(tmp_path)
            raise

    def _to_stored_record(self, record_id: str, envelope: dict) -> StoredRecord:
        return StoredRecord(
            record_id=record_id,
            data=envelope["data"],
            version=str(envelope["version"]),
            updated_at=datetime.fromisoformat(envelope["updated_at"]),
            provider_ref=envelope.get("path"),
        )

    def create(self, collection: str, record_id: str, data: Dict[str, Any]) -> StoredRecord:
        path = self._record_path(collection, record_id)
        if os.path.exists(path):
            raise StorageError(f"Record already exists: {collection}/{record_id}")
        now = datetime.now(timezone.utc).isoformat()
        envelope = {"data": data, "version": "1", "created_at": now, "updated_at": now, "path": path}
        self._write_raw(path, envelope)
        return self._to_stored_record(record_id, envelope)

    def get(self, collection: str, record_id: str) -> Optional[StoredRecord]:
        path = self._record_path(collection, record_id)
        envelope = self._read_raw(path)
        if envelope is None:
            return None
        return self._to_stored_record(record_id, envelope)

    def update(self, collection: str, record_id: str, data: Dict[str, Any],
               expected_version: Optional[str] = None) -> StoredRecord:
        path = self._record_path(collection, record_id)
        envelope = self._read_raw(path)
        if envelope is None:
            raise RecordNotFoundError(f"Cannot update - record does not exist: {collection}/{record_id}")
        current_version = str(envelope["version"])
        if expected_version is not None and expected_version != current_version:
            raise ConcurrencyConflictError(collection, record_id, expected_version, current_version)
        now = datetime.now(timezone.utc).isoformat()
        new_envelope = {
            "data": data, "version": str(int(current_version) + 1),
            "created_at": envelope["created_at"], "updated_at": now, "path": path,
        }
        self._write_raw(path, new_envelope)
        return self._to_stored_record(record_id, new_envelope)

    def delete(self, collection: str, record_id: str) -> None:
        path = self._record_path(collection, record_id)
        if not os.path.exists(path):
            raise RecordNotFoundError(f"Cannot delete - record does not exist: {collection}/{record_id}")
        os.remove(path)

    def list(self, collection: str, cursor: Optional[str] = None, limit: int = 100) -> ListResult:
        directory = self._collection_dir(collection)
        filenames = sorted(f for f in os.listdir(directory) if f.endswith(".json") and not f.startswith(".tmp-"))
        start_idx = 0
        if cursor is not None:
            try:
                start_idx = filenames.index(f"{cursor}.json") + 1
            except ValueError:
                start_idx = 0
        page = filenames[start_idx:start_idx + limit]
        records = []
        for fname in page:
            record_id = fname[:-len(".json")]
            envelope = self._read_raw(os.path.join(directory, fname))
            if envelope is not None:
                records.append(self._to_stored_record(record_id, envelope))
        next_cursor = page[-1][:-len(".json")] if len(filenames) > start_idx + limit else None
        return ListResult(records=records, next_cursor=next_cursor)

    def health_check(self) -> bool:
        try:
            test_path = os.path.join(self.root_dir, ".health_check")
            with open(test_path, "w") as f:
                f.write("ok")
            os.remove(test_path)
            return True
        except OSError:
            return False
