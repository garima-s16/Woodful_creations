"""Field mappings for Zoho/SAP integration (Family 19).

Each entry maps a Woodful model field to its equivalent field name in
the external system. This is a design artifact - it defines what
*would* be sent if a real connection existed, and is used by
integration_service.py to build the actual payload for any entity in
scope. Fields not listed here are deliberately not synced.

Zoho and SAP model similar business concepts differently (Zoho Books/
CRM vs SAP Business One) - mappings are kept separate per system rather
than assuming one shared schema, since forcing a single mapping would
either lose fields one system supports or invent fields the other
doesn't have.
"""

# Woodful field -> Zoho field, per entity type. Values are the
# equivalent field name in Zoho's object model (Zoho Books/CRM
# terminology) - not verified against a live Zoho tenant (no
# credentials in this environment), but reflects Zoho's documented
# public field names for these object types.
ZOHO_FIELD_MAPPING = {
    "client": {
        "name": "Contact_Name", "phone": "Phone", "email": "Email",
        "address": "Billing_Address",
    },
    "supplier": {
        "name": "Vendor_Name", "phone": "Phone", "gstin": "GST_Number",
        "payment_terms": "Payment_Terms",
    },
    "material": {
        "name": "Item_Name", "unit": "Unit", "current_stock": "Stock_On_Hand",
        # average_rate/stock_value deliberately NOT mapped - Woodful's
        # internal costing should not silently become Zoho's costing
        # basis without an explicit, reviewed decision to do so.
    },
    "order": {
        "order_code": "SalesOrder_Number", "order_date": "Date",
        "order_value": "Total", "delivery_status": "Status",
    },
    "purchase": {
        "purchase_code": "PurchaseOrder_Number", "date": "Date",
        "quantity": "Quantity", "rate": "Rate", "invoice_total": "Total",
    },
    "payment": {
        "receipt_code": "Reference_Number", "amount": "Amount",
        "date": "Date", "payment_mode": "Payment_Mode",
        # reference_number/received_by deliberately NOT mapped -
        # internal reconciliation notes, not meaningful outside Woodful.
    },
}

# Woodful field -> SAP field, per entity type. SAP Business One's
# object model (Business Partners, Items, Sales/Purchase Orders) uses
# different field-naming conventions than Zoho's - kept as its own
# mapping rather than reused, per the module docstring above.
SAP_FIELD_MAPPING = {
    "client": {
        "name": "CardName", "phone": "Phone1", "email": "EmailAddress",
        "address": "Address",
    },
    "supplier": {
        "name": "CardName", "phone": "Phone1", "gstin": "FederalTaxID",
        "payment_terms": "PayTermsGrpCode",
    },
    "material": {
        "name": "ItemName", "unit": "InventoryUOM", "current_stock": "OnHand",
    },
    "order": {
        "order_code": "DocNum", "order_date": "DocDate",
        "order_value": "DocTotal", "delivery_status": "DocStatus",
    },
    "purchase": {
        "purchase_code": "DocNum", "date": "DocDate",
        "quantity": "Quantity", "rate": "Price", "invoice_total": "DocTotal",
    },
    "payment": {
        "receipt_code": "DocNum", "amount": "CashSum",
        "date": "DocDate", "payment_mode": "TransferAccount",
    },
}

FIELD_MAPPINGS = {"zoho": ZOHO_FIELD_MAPPING, "sap": SAP_FIELD_MAPPING}


def build_payload(external_system: str, entity_type: str, entity) -> dict:
    """Builds the actual outbound payload for one entity using the
    real, current attribute values on the SQLAlchemy object - never
    fabricated data. Fields not present in the mapping are silently
    excluded (not sent), never sent as null/guessed."""
    mapping = FIELD_MAPPINGS.get(external_system, {}).get(entity_type, {})
    payload = {}
    for woodful_field, external_field in mapping.items():
        value = getattr(entity, woodful_field, None)
        if value is not None:
            payload[external_field] = str(value) if not isinstance(value, (int, float, bool)) else value
    return payload
