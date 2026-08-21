from sqlalchemy import Column, Integer, String, Text, DateTime
from app.models.base import BaseModel

# Woodful is the source of truth for all entities in scope. Sync is
# push-only (Woodful -> external system) in this architecture -
# deliberately not bidirectional. Accepting writes back from Zoho/SAP
# would mean an external system could silently alter Woodful's own
# business records (pricing, stock, client data) without going through
# Woodful's own authorization/validation/audit path - exactly the
# "AI/agents must not silently modify records" principle this whole
# session has been built around, applied to external systems too.
# Conflict resolution is therefore simple by design: Woodful always
# wins, and a push failure is retried or flagged - never silently
# overwritten by whatever the external system happens to hold.
SYNC_DIRECTION = "push"  # Woodful -> external system, by design

SYNC_STATUSES = {"PENDING", "SYNCED", "FAILED", "RETRYING"}
EXTERNAL_SYSTEMS = {"zoho", "sap"}

# What this architecture is actually built for right now - not every
# entity type in the app, only the ones Family 19 names.
SYNCABLE_ENTITY_TYPES = {
    "client", "supplier", "material", "order", "purchase", "payment",
}


class IntegrationSyncLog(BaseModel):
    """One row per sync attempt - append-only, never updated in place.
    A retry is a NEW row referencing the same entity, not an edit to
    the failed one, so the full attempt history (including every prior
    failure and its error) is always genuinely present, not overwritten.
    dedup_key makes a given (entity, system, operation) attempt safe to
    re-trigger without creating duplicate pushes for work already
    successfully completed."""
    __tablename__ = "integration_sync_logs"

    external_system = Column(String(10), nullable=False, index=True)  # "zoho" / "sap"
    entity_type = Column(String(30), nullable=False, index=True)
    entity_id = Column(Integer, nullable=False, index=True)
    external_id = Column(String(100), nullable=True)  # the record's ID in the external system, once known
    operation = Column(String(20), nullable=False)  # create / update
    status = Column(String(20), nullable=False, index=True)  # PENDING / SYNCED / FAILED / RETRYING
    dedup_key = Column(String(150), nullable=True, index=True)
    attempt_number = Column(Integer, nullable=False, default=1)
    error_message = Column(Text, nullable=True)
    triggered_by_user_id = Column(Integer, nullable=True)
    synced_at = Column(DateTime, nullable=True)  # set only when status becomes SYNCED
