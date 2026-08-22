"""Family 105 Section 4 - the repository layer.

A Repository is what business logic (routes, the chatbot, Excel
import/export, PDF generation - Section 35's shared data layer
requirement) actually talks to. It never touches a StorageProvider's
collection/record_id addressing directly from outside this module -
that's the whole point of the seam.

What lives here versus in StorageProvider:
- StorageProvider: generic CRUD + concurrency, no business meaning.
- Repository (this layer): business ID generation and format (Section
  10 - "EST-XXXX" is a business concept, a Drive file ID is not),
  validation before a write is attempted (Section 17 - the storage
  layer must validate before writing), and mapping between "the
  record_id used for storage addressing" and "the business ID a user
  actually sees," which are deliberately allowed to be the same value
  for simplicity in this implementation but are conceptually distinct
  per Section 10.

This module is intentionally NOT wired into any existing route yet.
Every existing FastAPI route still talks directly to SQLAlchemy - that
is the current, working, tested persistence path, and this file does
not change it. This is Phase 2/3 of the spec's own staged rollout
(inspect -> build the abstraction -> implement local provider through
it) landing as new, additive code with its own tests, not a
replacement for what already works.
"""
from abc import ABC
from typing import Any, Dict, List, Optional, Type
from dataclasses import dataclass

from app.storage.base import StorageProvider, StoredRecord, RecordNotFoundError, ConcurrencyConflictError


@dataclass
class ValidationError(Exception):
    """Raised by a repository's validate() hook before a write is even
    attempted - Section 17: do not allow malformed records to enter
    the persistent store. Distinct from StorageError - this is a
    business-rule rejection, not a storage-layer failure."""
    errors: List[str]

    def __str__(self):
        return "; ".join(self.errors)


class BaseRepository(ABC):
    """Subclass per entity (ClientRepository, OrderRepository, ...).
    collection_name identifies which StorageProvider collection this
    repository owns - one repository per collection, never shared.

    Transactions (Section 12): a single record write is atomic at the
    StorageProvider level (LocalJSONStorageProvider's atomic rename;
    the Google Drive provider must give an equivalent guarantee for
    its own writes). A multi-record operation - Estimate -> Order
    conversion is the spec's own example - is NOT atomic just because
    each individual write is. That needs an explicit saga/compensating-
    action pattern at the call site (create the Order, then update the
    Estimate to reference it and mark it closed; if the second write
    fails, delete the Order that was just created rather than leaving
    it orphaned) - deliberately left as a call-site responsibility
    rather than baked into this base class, since the right recovery
    action is different for every multi-record operation Woodful has.
    This repository layer provides the atomic building blocks; it does
    not yet provide a generic multi-record transaction/rollback
    mechanism, and does not claim to."""

    collection_name: str

    def __init__(self, provider: StorageProvider):
        self.provider = provider

    def validate(self, data: Dict[str, Any]) -> List[str]:
        """Override in subclasses. Return a list of human-readable
        error strings; empty list means valid. Base implementation
        validates nothing - a repository with no business rules of its
        own is legitimate (e.g. a pure lookup/settings collection)."""
        return []

    def create(self, record_id: str, data: Dict[str, Any]) -> StoredRecord:
        errors = self.validate(data)
        if errors:
            raise ValidationError(errors)
        return self.provider.create(self.collection_name, record_id, data)

    def get(self, record_id: str) -> Optional[StoredRecord]:
        return self.provider.get(self.collection_name, record_id)

    def update(self, record_id: str, data: Dict[str, Any], expected_version: Optional[str] = None) -> StoredRecord:
        errors = self.validate(data)
        if errors:
            raise ValidationError(errors)
        return self.provider.update(self.collection_name, record_id, data, expected_version=expected_version)

    def delete(self, record_id: str) -> None:
        self.provider.delete(self.collection_name, record_id)

    def list(self, cursor: Optional[str] = None, limit: int = 100):
        return self.provider.list(self.collection_name, cursor=cursor, limit=limit)
