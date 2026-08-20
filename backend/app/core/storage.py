"""Storage abstraction (Family 17.1). Business code depends on this
interface only - never on os.path/open()/os.remove() directly. This is
what makes object storage addable later without touching any route.

LocalStorageBackend is the only backend actually implemented in this
build (no cloud credentials exist in this environment) and preserves
the exact current on-disk layout and behavior. The provider is chosen
by STORAGE_PROVIDER in configuration - "local" is the only value that
does anything today; any other value raises clearly, rather than
silently falling back to local storage under a different name.

A real cloud backend (S3-compatible / Azure Blob / GCS) would implement
this same StorageBackend interface - upload routes would not change at
all, only which backend get_storage_backend() returns.
"""
import os
from typing import Optional

from app.core.config import settings


class StorageBackend:
    """The interface every backend implements. save/read/exists/delete
    only - no direct filesystem or cloud SDK calls anywhere outside a
    concrete backend's own implementation of these four methods."""

    def save(self, relative_path: str, data: bytes) -> None:
        raise NotImplementedError

    def read(self, relative_path: str) -> bytes:
        raise NotImplementedError

    def exists(self, relative_path: str) -> bool:
        raise NotImplementedError

    def delete(self, relative_path: str) -> None:
        raise NotImplementedError


class LocalStorageBackend(StorageBackend):
    """Writes under settings.UPLOAD_DIRECTORY - identical on-disk
    layout to what every upload route already did directly before this
    abstraction existed. This remains the backend for local development
    regardless of what a future cloud backend is configured for
    production, per Family 17.1's explicit requirement."""

    def __init__(self, base_dir: Optional[str] = None):
        self.base_dir = base_dir or settings.UPLOAD_DIRECTORY

    def _full_path(self, relative_path: str) -> str:
        # relative_path is always a server-generated random filename
        # (never user input) by the time it reaches here - the same
        # path-traversal protection every upload route already had is
        # unchanged, just enforced one layer up in the route itself.
        return os.path.join(self.base_dir, relative_path)

    def save(self, relative_path: str, data: bytes) -> None:
        full_path = self._full_path(relative_path)
        os.makedirs(os.path.dirname(full_path), exist_ok=True)
        with open(full_path, "wb") as f:
            f.write(data)

    def read(self, relative_path: str) -> bytes:
        with open(self._full_path(relative_path), "rb") as f:
            return f.read()

    def exists(self, relative_path: str) -> bool:
        return os.path.exists(self._full_path(relative_path))

    def delete(self, relative_path: str) -> None:
        full_path = self._full_path(relative_path)
        if os.path.exists(full_path):
            os.remove(full_path)

    def local_path_for_serving(self, relative_path: str) -> str:
        """Only meaningful for the local backend - FastAPI's
        FileResponse needs an actual filesystem path. A cloud backend
        would not implement this; routes serving uploaded files should
        prefer read() + a Response with explicit media_type so they
        work against any backend, not just local."""
        return self._full_path(relative_path)


_backend_instance: Optional[StorageBackend] = None


def get_storage_backend() -> StorageBackend:
    """The single place that decides which backend is active, based on
    STORAGE_PROVIDER. Cached after first call. Any value other than
    "local" raises clearly rather than silently using local storage
    under a different provider's name - there is no real cloud backend
    implemented in this build, and pretending otherwise would be
    exactly the kind of faked capability this pass prohibits."""
    global _backend_instance
    if _backend_instance is not None:
        return _backend_instance
    provider = (settings.STORAGE_PROVIDER or "local").lower()
    if provider == "local":
        _backend_instance = LocalStorageBackend()
    else:
        raise NotImplementedError(
            f"STORAGE_PROVIDER='{provider}' is not implemented in this build. "
            f"Only 'local' is available. A real S3-compatible/Azure Blob/GCS backend "
            f"would implement the StorageBackend interface in this module."
        )
    return _backend_instance
