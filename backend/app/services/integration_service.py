"""Family 19 - Zoho + SAP integration architecture.

Design principle: Woodful is the source of truth. Sync is push-only
(see integration_sync_log.py's module docstring for why bidirectional
sync is deliberately not built). This module defines the adapter
boundary and orchestrates a sync attempt end-to-end - resolving the
real entity, building its payload from the real field mappings,
calling the adapter, and writing an honest, append-only log entry.

No real HTTP client code exists here for the actual Zoho/SAP API call.
That is a deliberate omission, not an oversight: writing a request/
response shape without real API credentials or documentation to
verify it against would mean guessing, and a guessed integration that
looks like it works is worse than an honest gap - it is exactly the
kind of faked live integration this family explicitly prohibits. The
seam where that HTTP call belongs is marked clearly below.
"""
from dataclasses import dataclass
from typing import Optional
from datetime import datetime
from sqlalchemy.orm import Session

from app.core.config import settings
from app.models.integration_sync_log import IntegrationSyncLog, SYNCABLE_ENTITY_TYPES
from app.services.integration_field_mappings import build_payload
from app.models.client import Client
from app.models.supplier import Supplier
from app.models.material import Material
from app.models.order import Order
from app.models.purchase import Purchase
from app.models.payment import Payment

ENTITY_MODELS = {
    "client": Client, "supplier": Supplier, "material": Material,
    "order": Order, "purchase": Purchase, "payment": Payment,
}


@dataclass
class AdapterResult:
    success: bool
    external_id: Optional[str]
    error: Optional[str]
    # One of this session's standing verification labels - set by the
    # adapter itself based on what actually happened, never assumed by
    # the caller.
    classification: str


class IntegrationAdapter:
    """The boundary every external system integrates through. A
    concrete adapter must never claim success without a real,
    verified external call having actually happened."""

    external_system: str

    def is_configured(self) -> bool:
        raise NotImplementedError

    def push(self, entity_type: str, payload: dict) -> AdapterResult:
        raise NotImplementedError


class ZohoAdapter(IntegrationAdapter):
    external_system = "zoho"

    def is_configured(self) -> bool:
        return bool(settings.ZOHO_API_KEY and settings.ZOHO_API_BASE_URL)

    def push(self, entity_type: str, payload: dict) -> AdapterResult:
        if not self.is_configured():
            return AdapterResult(
                success=False, external_id=None,
                error="ZOHO_API_KEY / ZOHO_API_BASE_URL are not configured in this environment.",
                classification="NOT VERIFIED — EXTERNAL SERVICE REQUIRED",
            )
        # SEAM: the real Zoho API call belongs here (OAuth token
        # handling, the actual HTTP request per Zoho's API for
        # entity_type, response parsing). Not implemented - see this
        # module's docstring for why guessing at this would be a faked
        # integration, not a real one.
        return AdapterResult(
            success=False, external_id=None,
            error="Zoho credentials are present but the live HTTP call is not implemented in this build.",
            classification="NOT VERIFIED — EXTERNAL SERVICE REQUIRED",
        )


class SAPAdapter(IntegrationAdapter):
    external_system = "sap"

    def is_configured(self) -> bool:
        return bool(settings.SAP_API_KEY and settings.SAP_API_BASE_URL)

    def push(self, entity_type: str, payload: dict) -> AdapterResult:
        if not self.is_configured():
            return AdapterResult(
                success=False, external_id=None,
                error="SAP_API_KEY / SAP_API_BASE_URL are not configured in this environment.",
                classification="NOT VERIFIED — EXTERNAL SERVICE REQUIRED",
            )
        # SEAM: the real SAP Business One Service Layer call belongs
        # here. Not implemented - same reasoning as ZohoAdapter above.
        return AdapterResult(
            success=False, external_id=None,
            error="SAP credentials are present but the live HTTP call is not implemented in this build.",
            classification="NOT VERIFIED — EXTERNAL SERVICE REQUIRED",
        )


ADAPTERS = {"zoho": ZohoAdapter(), "sap": SAPAdapter()}


class IntegrationService:
    @staticmethod
    def sync_entity(
        db: Session, external_system: str, entity_type: str, entity_id: int,
        triggered_by_user_id: Optional[int] = None, force: bool = False,
    ) -> IntegrationSyncLog:
        """Orchestrates one sync attempt end-to-end and always returns
        a real, persisted log row - success, failure, or refusal are
        all logged, never silently dropped. Idempotent: a dedup_key of
        (system, entity_type, entity_id) that already has a SYNCED
        entry is not re-pushed unless force=True, so retriggering the
        same sync (a page refresh, a retried request) cannot create
        duplicate external records."""
        if external_system not in ADAPTERS:
            raise ValueError(f"Unknown external system '{external_system}'. Must be one of: {list(ADAPTERS.keys())}")
        if entity_type not in SYNCABLE_ENTITY_TYPES:
            raise ValueError(f"'{entity_type}' is not a syncable entity type. Must be one of: {SYNCABLE_ENTITY_TYPES}")

        model = ENTITY_MODELS[entity_type]
        entity = db.query(model).filter(model.id == entity_id).first()
        if not entity:
            raise ValueError(f"{entity_type} {entity_id} not found - cannot sync a record that does not exist.")

        dedup_key = f"{external_system}:{entity_type}:{entity_id}"

        if not force:
            already_synced = db.query(IntegrationSyncLog).filter(
                IntegrationSyncLog.dedup_key == dedup_key, IntegrationSyncLog.status == "SYNCED",
            ).first()
            if already_synced:
                return already_synced

        prior_attempts = db.query(IntegrationSyncLog).filter(IntegrationSyncLog.dedup_key == dedup_key).count()

        payload = build_payload(external_system, entity_type, entity)
        adapter = ADAPTERS[external_system]
        result = adapter.push(entity_type, payload)

        log_entry = IntegrationSyncLog(
            external_system=external_system, entity_type=entity_type, entity_id=entity_id,
            external_id=result.external_id, operation="create" if prior_attempts == 0 else "update",
            status="SYNCED" if result.success else "FAILED",
            dedup_key=dedup_key, attempt_number=prior_attempts + 1,
            error_message=result.error, triggered_by_user_id=triggered_by_user_id,
            synced_at=datetime.utcnow() if result.success else None,
        )
        db.add(log_entry)
        db.commit()
        db.refresh(log_entry)
        return log_entry
