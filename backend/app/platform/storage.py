"""Storage abstraction.
Business code depends on this interface only - never on
os.path/open()/os.remove() directly, and never on any backend-specific
method. This is what makes both local disk and Google Drive work
through the exact same route code.

The interface is keyed by a StorageReference, not a bare
relative_path for save/read/exists/delete. That's necessary because
Google Drive's authoritative file identity is its own drive_file_id
- a relative_path has no meaning to the Drive API. save() now returns
a StorageReference (the backend that stored it, the relative_path the
caller passed in, and - for Drive - the real file ID Drive assigned),
and read()/exists()/delete() all take a StorageReference rather than a
bare string, so a caller can never accidentally ask Drive to look
something up by filename.

get_storage_backend_for_record() is the single centralized place that
turns a document-like row's own storage_backend/stored_filename/
drive_file_id columns into the right backend instance and the right
StorageReference - not the globally-configured STORAGE_PROVIDER, which
only decides where a NEW upload goes. An existing local
record must always be read back from local disk even after
STORAGE_PROVIDER is switched to drive for new uploads.
"""
import os
import tempfile
from dataclasses import dataclass
from typing import Optional

from app.platform.config import settings


@dataclass
class StorageReference:
    """What save() returns, and what read()/exists()/delete() require.
    The caller (a route) persists this onto its own document row -
    relative_path becomes stored_filename, backend becomes
    storage_backend, drive_file_id becomes drive_file_id - so the file
    can be located again on any future request, by any process, not
    just the one that uploaded it."""
    backend: str  # "local" or "drive"
    relative_path: str
    drive_file_id: Optional[str] = None


class StorageBackend:
    """The interface every backend implements. save/read/exists/delete
    only - no direct filesystem or cloud SDK calls anywhere outside a
    concrete backend's own implementation of these four methods."""

    def save(self, relative_path: str, data: bytes) -> StorageReference:
        raise NotImplementedError

    def read(self, ref: StorageReference) -> bytes:
        raise NotImplementedError

    def exists(self, ref: StorageReference) -> bool:
        raise NotImplementedError

    def delete(self, ref: StorageReference) -> None:
        raise NotImplementedError


class LocalStorageBackend(StorageBackend):
    """Writes under settings.UPLOAD_DIRECTORY - identical on-disk
    layout to what every upload route already used before this
    abstraction existed. This remains the backend for local
    development regardless of what a future cloud backend is
    configured for production."""

    def __init__(self, base_dir: Optional[str] = None):
        self.base_dir = base_dir or settings.UPLOAD_DIRECTORY

    def _full_path(self, relative_path: str) -> str:
        # relative_path is always a server-generated random filename
        # (never user input) by the time it reaches here - the same
        # path-traversal protection every upload route already had is
        # unchanged, just enforced one layer up in the route itself.
        return os.path.join(self.base_dir, relative_path)

    def save(self, relative_path: str, data: bytes) -> StorageReference:
        full_path = self._full_path(relative_path)
        target_dir = os.path.dirname(full_path)
        os.makedirs(target_dir, exist_ok=True)
        # Write to a temp file in the SAME directory, then atomically
        # rename over the target - a crash or interrupt mid-write can
        # never leave a corrupted, partially-written file at the real
        # path, since a reader only ever sees the complete old file or
        # the complete new one. os.rename() is only atomic within the
        # same filesystem, which is exactly why the temp file lives in
        # target_dir rather than a generic /tmp location - a cross-
        # filesystem rename would silently degrade to copy+delete and
        # lose this guarantee entirely.
        fd, tmp_path = tempfile.mkstemp(dir=target_dir, prefix=".tmp_")
        try:
            with os.fdopen(fd, "wb") as f:
                f.write(data)
            os.replace(tmp_path, full_path)
        except Exception:
            if os.path.exists(tmp_path):
                os.remove(tmp_path)
            raise
        return StorageReference(backend="local", relative_path=relative_path)

    def read(self, ref: StorageReference) -> bytes:
        with open(self._full_path(ref.relative_path), "rb") as f:
            return f.read()

    def exists(self, ref: StorageReference) -> bool:
        return os.path.exists(self._full_path(ref.relative_path))

    def delete(self, ref: StorageReference) -> None:
        full_path = self._full_path(ref.relative_path)
        if os.path.exists(full_path):
            os.remove(full_path)


class DriveStorageBackend(StorageBackend):
    """Google Drive-backed implementation of the file/document storage
    interface.

    HONEST STATUS, stated plainly: this has never been executed. This
    sandbox has no network access and cannot install
    google-api-python-client/google-auth (confirmed unavailable this
    session - both pip and apt package downloads returned 403).
    google.oauth2.service_account and googleapiclient.discovery are
    imported lazily inside __init__, not at module load time, so
    importing this module (and every route that imports
    get_storage_backend from it) does NOT require the google-* packages
    to be installed unless Drive is actually selected - local-only
    deployments are unaffected by Drive's dependencies being absent.

    Every method below is a real, complete implementation against the
    documented Google Drive API v3 surface (files.create with
    media_body for upload, files.get_media for download, files.get for
    existence, files.delete for delete) - not a stub, not a
    NotImplementedError. What is genuinely unverified is whether it
    behaves correctly against the live API, since it has never been
    run against a real Drive account. Do not treat "implemented" as
    "proven" until someone with real Google credentials has actually
    exercised it.

    Folder mapping: relative_path's own prefix segment -
    already established by every upload route ("client_documents/",
    "documents/{parent_type}/...", "payment_documents/", "resumes/") -
    determines the Drive subfolder under one "Woodful Creations" root,
    reusing the convention every upload route already writes rather
    than requiring route changes. Folder IDs are looked up once and
    cached (do not create duplicate folders), keyed by
    (parent_folder_id, name) so a concurrent process creating the same
    folder is detected by querying before creating, not assumed.

    Service account, not per-user OAuth - the intended
    production storage is organization-owned, not tied to a
    developer's personal account. Scope is drive.file specifically
    (only files this app itself creates), never full Drive access.
    """

    _SCOPES = ["https://www.googleapis.com/auth/drive.file"]

    _FOLDER_MAP = {
        "client_documents": "Clients",
        "payment_documents": "Payments",
        "resumes": "Employees",
        "order": "Orders",
        "supplier": "Suppliers",
        "purchase": "Inventory",
        "employee": "Employees",
        "product": "Products",
    }
    _ROOT_FOLDER_NAME = "Woodful Creations"
    _FOLDER_MIME_TYPE = "application/vnd.google-apps.folder"

    def __init__(self, credentials_path: str, root_folder_id: str):
        if not credentials_path or not root_folder_id:
            # Fail clearly rather than silently guessing
            # intent - this mirrors the same check get_storage_backend()
            # already does before ever constructing this class, kept
            # here too so this class is never silently usable in a
            # half-configured state if constructed directly.
            raise RuntimeError(
                "DriveStorageBackend requires both a credentials path and a root folder ID."
            )
        try:
            from google.oauth2 import service_account
            from googleapiclient.discovery import build
        except ImportError as exc:
            raise RuntimeError(
                "STORAGE_PROVIDER=drive requires the google-api-python-client and "
                "google-auth packages (see requirements.txt). They are not installed "
                "in the current environment."
            ) from exc

        self.root_folder_id = root_folder_id
        credentials = service_account.Credentials.from_service_account_file(
            credentials_path, scopes=self._SCOPES
        )
        self._service = build("drive", "v3", credentials=credentials, cache_discovery=False)
        self._folder_id_cache: dict = {}

    def _folder_name_for(self, relative_path: str) -> str:
        """The first meaningful path segment of relative_path (e.g.
        "client_documents" from "client_documents/abc123.pdf", or
        "order" from "documents/order/abc123.pdf") determines the
        target Drive folder via _FOLDER_MAP. Falls back to "Company"
        for anything unrecognized rather than raising - a new
        upload-route prefix added later should still land somewhere
        sensible instead of breaking uploads outright."""
        parts = relative_path.split("/")
        key = parts[1] if parts[0] == "documents" and len(parts) > 1 else parts[0]
        return self._FOLDER_MAP.get(key, "Company")

    def _resolve_folder_id(self, folder_name: str) -> str:
        """Finds (or creates, on first use) the named subfolder
        directly under the configured root, caching the result
        in-process so a folder is looked up/created at most once per
        running process, not on every upload."""
        if folder_name in self._folder_id_cache:
            return self._folder_id_cache[folder_name]

        query = (
            f"name = '{folder_name}' and '{self.root_folder_id}' in parents "
            f"and mimeType = '{self._FOLDER_MIME_TYPE}' and trashed = false"
        )
        results = self._service.files().list(
            q=query, spaces="drive", fields="files(id, name)",
            supportsAllDrives=True, includeItemsFromAllDrives=True,
        ).execute()
        existing = results.get("files", [])
        if existing:
            folder_id = existing[0]["id"]
        else:
            metadata = {
                "name": folder_name,
                "mimeType": self._FOLDER_MIME_TYPE,
                "parents": [self.root_folder_id],
            }
            created = self._service.files().create(
                body=metadata, fields="id", supportsAllDrives=True,
            ).execute()
            folder_id = created["id"]

        self._folder_id_cache[folder_name] = folder_id
        return folder_id

    def save(self, relative_path: str, data: bytes) -> StorageReference:
        from googleapiclient.http import MediaIoBaseUpload
        import io

        folder_id = self._resolve_folder_id(self._folder_name_for(relative_path))
        filename = relative_path.rsplit("/", 1)[-1]
        media = MediaIoBaseUpload(io.BytesIO(data), mimetype="application/octet-stream", resumable=False)
        metadata = {"name": filename, "parents": [folder_id]}
        created = self._service.files().create(
            body=metadata, media_body=media, fields="id", supportsAllDrives=True,
        ).execute()
        drive_file_id = created["id"]
        return StorageReference(backend="drive", relative_path=relative_path, drive_file_id=drive_file_id)

    def read(self, ref: StorageReference) -> bytes:
        import io
        from googleapiclient.http import MediaIoBaseDownload

        if not ref.drive_file_id:
            # drive_file_id, never relative_path/filename
            # search, is Drive's authoritative identity. A Drive
            # StorageReference missing its file ID is a caller bug,
            # not something to paper over by guessing from the name.
            raise ValueError("Cannot read a Drive file without a drive_file_id.")
        request = self._service.files().get_media(fileId=ref.drive_file_id, supportsAllDrives=True)
        buffer = io.BytesIO()
        downloader = MediaIoBaseDownload(buffer, request)
        done = False
        while not done:
            _, done = downloader.next_chunk()
        return buffer.getvalue()

    def exists(self, ref: StorageReference) -> bool:
        from googleapiclient.errors import HttpError

        if not ref.drive_file_id:
            return False
        try:
            meta = self._service.files().get(
                fileId=ref.drive_file_id, fields="id, trashed", supportsAllDrives=True,
            ).execute()
            # A trashed file still returns successfully from the API
            # (it isn't gone until it's permanently deleted) - treating
            # it as existing would let callers read/serve/link a file
            # the user already removed from Drive.
            return not meta.get("trashed", False)
        except HttpError as exc:
            if exc.resp.status == 404:
                return False
            raise

    def delete(self, ref: StorageReference) -> None:
        from googleapiclient.errors import HttpError

        if not ref.drive_file_id:
            return  # nothing to delete - never delete by filename guess
        try:
            self._service.files().delete(fileId=ref.drive_file_id, supportsAllDrives=True).execute()
        except HttpError as exc:
            if exc.resp.status == 404:
                return  # Already-deleted is not an error
            raise


_backend_instance: Optional[StorageBackend] = None
_drive_backend_instance: Optional["DriveStorageBackend"] = None


def _get_or_create_drive_backend() -> "DriveStorageBackend":
    """Reuse a single Drive backend instance across every
    caller, rather than each document operation re-authenticating with
    Google and rebuilding the API client from scratch. DriveStorageBackend
    holds no per-record state - only its auth client and folder-ID cache -
    so sharing one instance across calls is correctness-preserving, not
    just a performance shortcut."""
    global _drive_backend_instance
    if _drive_backend_instance is None:
        _drive_backend_instance = DriveStorageBackend(
            settings.GOOGLE_DRIVE_CREDENTIALS_PATH, settings.GOOGLE_DRIVE_ROOT_FOLDER_ID,
        )
    return _drive_backend_instance


def get_storage_backend() -> StorageBackend:
    """Decides which backend NEW uploads go to, based on
    STORAGE_PROVIDER. Cached after first call. Only "local" and
    "drive" are recognized - anything else raises clearly rather than
    silently using local storage under a different provider's name."""
    global _backend_instance
    if _backend_instance is not None:
        return _backend_instance
    provider = (settings.STORAGE_PROVIDER or "local").lower()
    if provider == "local":
        _backend_instance = LocalStorageBackend()
    elif provider == "drive":
        if not settings.GOOGLE_DRIVE_ENABLED:
            raise RuntimeError(
                "STORAGE_PROVIDER=drive but GOOGLE_DRIVE_ENABLED is not set - "
                "refusing to guess intent. Set GOOGLE_DRIVE_ENABLED=True explicitly "
                "if Drive storage is genuinely intended."
            )
        if not settings.GOOGLE_DRIVE_CREDENTIALS_PATH or not settings.GOOGLE_DRIVE_ROOT_FOLDER_ID:
            raise RuntimeError(
                "STORAGE_PROVIDER=drive requires GOOGLE_DRIVE_CREDENTIALS_PATH and "
                "GOOGLE_DRIVE_ROOT_FOLDER_ID to both be set."
            )
        _backend_instance = _get_or_create_drive_backend()
    else:
        raise NotImplementedError(
            f"STORAGE_PROVIDER='{provider}' is not implemented in this build. "
            f"Only 'local' and 'drive' are available."
        )
    return _backend_instance


def get_storage_backend_for_record(record) -> "tuple[StorageBackend, StorageReference]":
    """The central resolution point. Reads the RECORD's own
    storage_backend/stored_filename/drive_file_id columns - never the
    globally-configured STORAGE_PROVIDER - so an existing local record
    is always read back from local disk even after STORAGE_PROVIDER
    has been switched to "drive" for new uploads.

    `record` is any document-like object exposing those three
    attributes - ClientDocument, PaymentDocument, GenericDocument, and
    Candidate (for its resume fields via the small adapter each
    route already builds where the column names differ, e.g.
    resume_stored_filename) all satisfy this.

    Every route needing to read/check/delete an EXISTING document
    should call this once, then call .read(ref)/.exists(ref)/
    .delete(ref) on the returned backend - never get_storage_backend()
    directly for that purpose, which would use the currently-configured
    provider instead of the record's actual one.
    """
    backend_name = (getattr(record, "storage_backend", None) or "local").lower()
    ref = StorageReference(
        backend=backend_name,
        relative_path=record.stored_filename,
        drive_file_id=getattr(record, "drive_file_id", None),
    )
    if backend_name == "local":
        return LocalStorageBackend(), ref
    elif backend_name == "drive":
        if not settings.GOOGLE_DRIVE_ENABLED or not settings.GOOGLE_DRIVE_CREDENTIALS_PATH or not settings.GOOGLE_DRIVE_ROOT_FOLDER_ID:
            raise RuntimeError(
                "This record's storage_backend is 'drive' but Drive is not configured "
                "on this server (GOOGLE_DRIVE_ENABLED/GOOGLE_DRIVE_CREDENTIALS_PATH/"
                "GOOGLE_DRIVE_ROOT_FOLDER_ID) - refusing to silently fall back to local, "
                "which would read the wrong file or none at all."
            )
        return _get_or_create_drive_backend(), ref
    else:
        raise NotImplementedError(f"Record has unrecognized storage_backend='{backend_name}'.")
