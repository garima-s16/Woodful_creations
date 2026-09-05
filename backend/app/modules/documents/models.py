from sqlalchemy import Column, Integer, String
from app.platform.database.base import BaseModel

# Every entity type this generic table currently supports. Checked
# against this allowlist on upload so parent_type can never be an
# arbitrary string - only these tables are ever queried to confirm the
# parent genuinely exists.
DOCUMENT_PARENT_TYPES = {"order", "supplier", "purchase", "employee", "product"}


class GenericDocument(BaseModel):
    """A file attached to an order, supplier, purchase, or employee
    record. One table for all four (and any future entity), rather
    than a near-identical dedicated table per type - client and
    payment documents already have their own established, tested
    tables (ClientDocument, PaymentDocument) and are deliberately left
    as-is rather than migrated here, to avoid touching working data.
    stored_filename is a random, server-generated name (never the
    user-supplied original), matching the same path-traversal
    protection already established for every other document type in
    this app.

    storage_backend/drive_file_id - "local" (default,
    matches every existing row) means stored_filename is a path under
    the local StorageBackend, same as before this field existed. "drive"
    means the file lives in Google Drive and drive_file_id is the
    actual reference - stored_filename is still kept for the original
    display name/extension, but the bytes are not on local disk in
    that case."""
    __tablename__ = "generic_documents"

    parent_type = Column(String(20), nullable=False, index=True)  # one of DOCUMENT_PARENT_TYPES
    parent_id = Column(Integer, nullable=False, index=True)  # not a single FK - points to a different table per parent_type
    original_filename = Column(String(255), nullable=False)
    stored_filename = Column(String(255), nullable=False, unique=True)
    content_type = Column(String(100), nullable=True)
    description = Column(String(255), nullable=True)
    uploaded_by = Column(String(100), nullable=True)
    storage_backend = Column(String(20), nullable=False, default="local")
    drive_file_id = Column(String(255), nullable=True, index=True)
