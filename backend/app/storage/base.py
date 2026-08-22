"""Family 105 - the storage provider abstraction.

This is the seam between "how Woodful's business logic works with
data" and "where that data physically lives." A StorageProvider is a
generic key-value-ish record store: it knows how to create, read,
update, delete, and list records within a named collection (e.g.
"clients", "orders"). It knows NOTHING about Woodful's business rules
- no validation, no ID generation scheme, no relationships. That
belongs one layer up, in the Repository classes (see base_repository.py).

Why this shape specifically:
- collection + record_id addressing maps cleanly onto both a local
  JSON-per-record file (collection = folder, record_id = filename) and
  a Google Drive folder structure (collection = subfolder, record_id =
  a file within it) without either provider needing to know about the
  other.
- optimistic-concurrency version field (see StoredRecord) is provider-
  agnostic at this layer - Google Drive's revision ID and a local
  provider's simple monotonic counter both satisfy the same contract:
  "give me something that changes when the record changes, and let me
  assert it hasn't changed since I last read it."
- Every method is explicit about what it returns on a not-found record
  (None, not an exception) versus what it raises on a genuine failure
  (StorageError and its subclasses) - callers should never need to
  guess which failure mode they're in.
"""
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, Optional, List, Dict
from datetime import datetime


class StorageError(Exception):
    """Base class for every storage-layer failure. Repositories catch
    this (or a specific subclass) rather than letting a provider's own
    internal exception type (a Google API exception, an OSError, ...)
    leak up into business logic - business logic should only ever need
    to know "storage failed" plus which specific, provider-agnostic
    failure mode."""


class RecordNotFoundError(StorageError):
    """Raised by update()/delete() when asked to act on a record that
    does not exist. get()/list() do NOT raise this - a missing record
    from get() is None, since "not found" is an expected, normal
    outcome there, not an error condition."""


class ConcurrencyConflictError(StorageError):
    """Raised by update() when the caller's expected_version does not
    match the record's current version - someone else changed this
    record since the caller last read it. Section 11's explicit
    requirement: never silently overwrite a concurrent change."""

    def __init__(self, collection: str, record_id: str, expected_version: str, actual_version: str):
        self.collection = collection
        self.record_id = record_id
        self.expected_version = expected_version
        self.actual_version = actual_version
        super().__init__(
            f"Conflict updating {collection}/{record_id}: expected version "
            f"{expected_version!r}, but the stored record is now at {actual_version!r}. "
            f"Re-read the record and reapply your change."
        )


class StorageUnavailableError(StorageError):
    """Raised when the underlying provider genuinely could not be
    reached or used - no internet, Drive API down, permission denied,
    rate limited, timeout. Distinct from RecordNotFoundError (the
    provider works fine, the record just isn't there) - callers
    typically want to show a different message for each (Section 28:
    "meaningful application errors", never a raw stack trace)."""


@dataclass
class StoredRecord:
    """What a provider hands back for one record - the raw data plus
    just enough metadata for the repository layer to do optimistic
    concurrency control and know when the record last changed.
    provider_ref is deliberately opaque here (a local file path for one
    provider, a Google Drive file ID for another) - repositories treat
    it as a token to pass back, never parse or construct it
    themselves (Section 10: business ID and Drive file ID are
    different concepts, and nothing outside the provider should
    conflate them)."""
    record_id: str
    data: Dict[str, Any]
    version: str
    updated_at: datetime
    provider_ref: Optional[str] = None


@dataclass
class ListResult:
    """A page of records plus an opaque cursor for the next page, when
    the collection is too large to return in one call - see Section 15
    (do not repeatedly download unrelated data) and Section 29 (avoid
    unnecessary full-dataset downloads)."""
    records: List[StoredRecord] = field(default_factory=list)
    next_cursor: Optional[str] = None


class StorageProvider(ABC):
    """The contract every concrete provider must satisfy. See
    local_provider.py for the filesystem/JSON implementation (used in
    development, per Section 5) and google_drive_provider.py for the
    production implementation (Section 6 onward).

    IMPORTANT - the current state of this abstraction, honestly:
    only LocalJSONStorageProvider has been implemented and genuinely
    exercised (real create/read/update/delete/list cycles, run in this
    environment). GoogleDriveStorageProvider exists as a structural
    skeleton implementing this same interface, but this sandbox cannot
    install google-api-python-client/google-auth or reach the network,
    so it has NOT been executed against the real Drive API even once.
    Treat it as an unverified draft, not working code, until someone
    with real Google credentials and a real environment runs it."""

    @abstractmethod
    def create(self, collection: str, record_id: str, data: Dict[str, Any]) -> StoredRecord:
        """Creates a new record. Raises StorageError (a provider-
        specific subclass, e.g. a "already exists" case) if record_id
        is already taken within this collection - callers that want
        create-or-update should use upsert-style logic at the
        repository layer, not rely on create() silently overwriting."""

    @abstractmethod
    def get(self, collection: str, record_id: str) -> Optional[StoredRecord]:
        """Returns None if the record doesn't exist - not an
        exception. See RecordNotFoundError's docstring for why this
        method specifically is the exception to that rule."""

    @abstractmethod
    def update(self, collection: str, record_id: str, data: Dict[str, Any],
               expected_version: Optional[str] = None) -> StoredRecord:
        """Updates an existing record. If expected_version is given
        and doesn't match the record's current stored version, raises
        ConcurrencyConflictError rather than overwriting (Section 11).
        If expected_version is None, the caller is explicitly opting
        out of the conflict check - used sparingly, only where the
        business logic has its own reason to believe last-write-wins
        is acceptable for that specific field/record."""

    @abstractmethod
    def delete(self, collection: str, record_id: str) -> None:
        """Raises RecordNotFoundError if record_id doesn't exist.
        Whether this is a hard delete or the provider chooses to soft-
        delete internally is a provider implementation detail - the
        business-rule decision of WHETHER something should be hard or
        soft deleted belongs to the repository/business logic layer
        (Section 25), not here."""

    @abstractmethod
    def list(self, collection: str, cursor: Optional[str] = None, limit: int = 100) -> ListResult:
        """Lists records in a collection, paginated. Order is
        provider-defined (typically creation order) - callers needing
        a specific sort/filter should do so at the repository layer
        after listing, or the repository should maintain its own
        index (Section 15) rather than expect every provider to
        support arbitrary server-side queries the way a SQL WHERE
        clause does."""

    @abstractmethod
    def health_check(self) -> bool:
        """True if the provider is currently reachable and usable.
        Used at startup and by a monitoring endpoint - see Section 28
        (Google Drive failure handling) and Section 40 (monitoring)."""
