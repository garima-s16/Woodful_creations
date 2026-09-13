"""Procurement domain API routes: suppliers, supplier-material
links, purchases, purchase imports, procurement requirements, and the
personal cart. Combines the former suppliers.py, supplier_materials.py,
purchases.py, purchase_imports.py, procurement_requirements.py, and
personal_cart.py."""
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query, Request
from app.platform.audit import log_action
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError
from app.platform.database import get_db
from app.platform.security import get_current_user, require_role
from app.modules.procurement.models import Supplier, Purchase, SupplierMaterial
from app.modules.inventory.schemas import SupplierCreate, SupplierUpdate, SupplierResponse
from app.platform.ids import generate_unique_code, generate_business_id
from typing import List
from fastapi import APIRouter, Depends, HTTPException, Request
from app.modules.inventory.models import Material
from app.modules.procurement.models import SupplierMaterial, Supplier
from app.modules.inventory.schemas import SupplierMaterialCreate, SupplierMaterialUpdate, SupplierMaterialResponse, SupplierMaterialWithSupplierName, SupplierMaterialWithMaterialName
from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response
from pydantic import BaseModel
from app.platform.security import require_role, get_current_user
from app.platform.audit import log_action, serializable_fields
from app.modules.procurement.models import Purchase, ProcurementRequirement
from app.modules.inventory.schemas import PurchaseCreate, PurchaseUpdate, PurchaseResponse, PurchaseReceiveRequest
from app.modules.procurement.services import ProcurementService
from app.shared import build_workbook, xlsx_response
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Request
import zipfile
from fastapi.responses import StreamingResponse
from app.platform.config import settings
from app.platform.security import require_role
from app.modules.procurement.models import Supplier
from app.modules.inventory.schemas import PurchaseCreate
from app.modules.procurement.services import (
    ImportPreviewResponse, ImportRowPreview, ImportCommitRequest, ImportCommitResult,
)
from app.modules.procurement.services import (
    build_import_template, parse_uploaded_workbook, validate_and_match_row, normalize_match_key,
)
from fastapi import APIRouter, Depends, HTTPException, Query
from app.modules.procurement.models import ProcurementRequirement, SupplierDecision, SupplierMaterial
from app.modules.procurement.schemas import ProcurementRequirementCreate, ProcurementRequirementUpdate, ProcurementRequirementResponse, SupplierDecisionCreate, SupplierDecisionResponse, RequirementPurchaseCreate
from app.modules.inventory.schemas import PurchaseCreate, PurchaseResponse
from app.platform.ids import generate_business_id
from fastapi import APIRouter, Depends, HTTPException
from app.platform.security import get_current_user
from app.modules.procurement.models import PersonalCartItem
from app.modules.procurement.schemas import PersonalCartItemCreate, PersonalCartItemUpdate, PersonalCartItemResponse


# --- suppliers.py ---
suppliers_router = APIRouter(prefix="/api/suppliers", tags=["suppliers"])


@suppliers_router.get("/", response_model=List[SupplierResponse])
def list_suppliers(category: Optional[str] = Query(None), db: Session = Depends(get_db),
                    auth=Depends(get_current_user)):
    query = db.query(Supplier)
    if category:
        query = query.filter(Supplier.category == category)
    return query.order_by(Supplier.name).all()


@suppliers_router.post("/", response_model=SupplierResponse, status_code=201)
def create_supplier(data: SupplierCreate, db: Session = Depends(get_db),
                     auth=Depends(require_role("master"))):
    payload = data.dict(exclude={"supplier_code"})
    for _ in range(5):
        code = generate_unique_code(db, Supplier, "supplier_code", "SUP-")
        supplier = Supplier(**payload, supplier_code=code, business_id=generate_business_id(db))
        db.add(supplier)
        try:
            db.commit()
        except IntegrityError:
            db.rollback()
            continue
        db.refresh(supplier)
        return supplier
    raise HTTPException(status_code=500, detail="Unable to generate a unique supplier code, please try again")


@suppliers_router.get("/{supplier_id}", response_model=SupplierResponse)
def get_supplier(supplier_id: int, db: Session = Depends(get_db), auth=Depends(get_current_user)):
    supplier = db.query(Supplier).filter(Supplier.id == supplier_id).first()
    if not supplier:
        raise HTTPException(status_code=404, detail="Supplier not found")
    return supplier


@suppliers_router.put("/{supplier_id}", response_model=SupplierResponse)
def update_supplier(supplier_id: int, data: SupplierUpdate, db: Session = Depends(get_db),
                     auth=Depends(require_role("master"))):
    supplier = db.query(Supplier).filter(Supplier.id == supplier_id).first()
    if not supplier:
        raise HTTPException(status_code=404, detail="Supplier not found")
    for field, value in data.dict(exclude_unset=True).items():
        setattr(supplier, field, value)
    db.add(supplier)
    db.commit()
    db.refresh(supplier)
    return supplier


@suppliers_router.delete("/{supplier_id}", status_code=204)
def delete_supplier(supplier_id: int, request: Request, db: Session = Depends(get_db),
                     auth=Depends(require_role("master"))):
    supplier = db.query(Supplier).filter(Supplier.id == supplier_id).first()
    if not supplier:
        raise HTTPException(status_code=404, detail="Supplier not found")
    if db.query(Purchase).filter(Purchase.supplier_id == supplier_id).first():
        raise HTTPException(status_code=400, detail="This supplier has purchase history and cannot be deleted.")
    if db.query(SupplierMaterial).filter(SupplierMaterial.supplier_id == supplier_id).first():
        raise HTTPException(status_code=400, detail="This supplier is linked to materials and cannot be deleted. Remove those links first.")
    # Defect repair (F138 P2): Material.supplier_id ("primary supplier",
    # nullable FK, distinct from the SupplierMaterial link table already
    # checked above - see Material's own docstring) was never checked
    # here, so a supplier set as a material's primary supplier with no
    # SupplierMaterial row and no Purchase yet could be hard-deleted,
    # leaving that material's supplier_id pointing at a row that no
    # longer exists. Same block-with-clear-message treatment as every
    # other in-use check on this endpoint.
    if db.query(Material).filter(Material.supplier_id == supplier_id).first():
        raise HTTPException(status_code=400, detail="This supplier is set as a material's primary supplier and cannot be deleted. Change that material's primary supplier first.")
    # Defect repair (F138 P2): SupplierDecision.recommended_supplier_id/
    # selected_supplier_id are a real, persisted decision record (P0.2.3)
    # - a decision can exist with no Purchase yet (record_supplier_decision
    # doesn't require one), so the Purchase check above alone doesn't
    # cover it. Never hard-delete a supplier a decision record still
    # references either way.
    from app.modules.procurement.models import SupplierDecision
    if db.query(SupplierDecision).filter(
        (SupplierDecision.selected_supplier_id == supplier_id) | (SupplierDecision.recommended_supplier_id == supplier_id)
    ).first():
        raise HTTPException(status_code=400, detail="This supplier is referenced by a recorded supplier decision and cannot be deleted.")
    supplier_name = supplier.name
    db.delete(supplier)
    db.commit()
    log_action(db, request, user_id=auth.get("user_id"), action="delete_supplier", module_name="suppliers",
               record_id=supplier_id, old_value={"name": supplier_name})


# --- supplier_materials.py ---
supplier_materials_router = APIRouter(prefix="/api/supplier-materials", tags=["supplier-materials"])


def _serialize_links(links, response_cls, role: str):
    """Pricing (supplier_price, last_purchase_price) is financial data,
    genuinely nulled for non-master roles - which suppliers can
    provide a material, MOQ, and lead time stay visible, since that's
    operational information an employee needs to plan a request, not
    money data."""
    responses = [response_cls.model_validate(link) for link in links]
    if role not in ("master",):
        for r in responses:
            r.supplier_price = None
            r.last_purchase_price = None
    return responses


@supplier_materials_router.post("/", response_model=SupplierMaterialResponse, status_code=201)
def link_supplier_material(data: SupplierMaterialCreate, db: Session = Depends(get_db),
                            auth=Depends(require_role("master"))):
    if not db.query(Supplier).filter(Supplier.id == data.supplier_id).first():
        raise HTTPException(status_code=404, detail="Supplier not found")
    if not db.query(Material).filter(Material.id == data.material_id).first():
        raise HTTPException(status_code=404, detail="Material not found")
    if db.query(SupplierMaterial).filter(
        SupplierMaterial.supplier_id == data.supplier_id, SupplierMaterial.material_id == data.material_id
    ).first():
        raise HTTPException(status_code=400, detail="This supplier is already linked to this material.")

    link = SupplierMaterial(**data.dict())
    db.add(link)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=400, detail="This supplier is already linked to this material.")
    db.refresh(link)
    return link


@supplier_materials_router.get("/by-material/{material_id}", response_model=List[SupplierMaterialWithSupplierName])
def list_suppliers_for_material(material_id: int, db: Session = Depends(get_db), auth=Depends(get_current_user)):
    """Every supplier who can provide this material, for the "compare
    suppliers" experience - preferred supplier first, then by price.
    Sorting by price is itself a financial signal (the first row is the
    cheapest even with the number hidden), so a non-privileged role gets
    a price-blind order instead - preferred first, then alphabetical."""
    role = auth.get("role", "user")
    query = db.query(SupplierMaterial).filter(SupplierMaterial.material_id == material_id)
    if role in ("master",):
        links = query.order_by(SupplierMaterial.is_preferred.desc(), SupplierMaterial.supplier_price.asc()).all()
    else:
        links = query.join(Supplier).order_by(SupplierMaterial.is_preferred.desc(), Supplier.name.asc()).all()
    return _serialize_links(links, SupplierMaterialWithSupplierName, role)


@supplier_materials_router.get("/by-supplier/{supplier_id}", response_model=List[SupplierMaterialWithMaterialName])
def list_materials_for_supplier(supplier_id: int, db: Session = Depends(get_db), auth=Depends(get_current_user)):
    links = db.query(SupplierMaterial).filter(SupplierMaterial.supplier_id == supplier_id).all()
    return _serialize_links(links, SupplierMaterialWithMaterialName, auth.get("role", "user"))


@supplier_materials_router.put("/{link_id}", response_model=SupplierMaterialResponse)
def update_supplier_material(link_id: int, data: SupplierMaterialUpdate, db: Session = Depends(get_db),
                              auth=Depends(require_role("master"))):
    link = db.query(SupplierMaterial).filter(SupplierMaterial.id == link_id).first()
    if not link:
        raise HTTPException(status_code=404, detail="Supplier-material link not found")
    for field, value in data.dict(exclude_unset=True).items():
        setattr(link, field, value)
    db.add(link)
    db.commit()
    db.refresh(link)
    return link


@supplier_materials_router.delete("/{link_id}", status_code=204)
def delete_supplier_material(link_id: int, request: Request, db: Session = Depends(get_db),
                              auth=Depends(require_role("master"))):
    link = db.query(SupplierMaterial).filter(SupplierMaterial.id == link_id).first()
    if not link:
        raise HTTPException(status_code=404, detail="Supplier-material link not found")
    old_value = {"supplier_id": link.supplier_id, "material_id": link.material_id}
    db.delete(link)
    db.commit()
    log_action(db, request, user_id=auth.get("user_id"), action="delete_supplier_material",
               module_name="supplier_materials", record_id=link_id, old_value=old_value)


# --- purchases.py ---
purchases_router = APIRouter(prefix="/api/purchases", tags=["purchases"])


class CartExportItem(BaseModel):
    """One row of the client-side purchase cart (redux, never persisted
    server-side) - not a domain model, just the shape needed to render
    a requisition list. material_id is informational only here (the
    export doesn't re-query it); name/quantity/unit/rate/supplier_name
    all come directly from what the cart already displayed on-screen,
    so the exported list can never show a number the user didn't
    already see in the cart drawer."""
    material_id: Optional[int] = None
    name: str
    quantity: float
    unit: str = ""
    rate: Optional[float] = None
    supplier_name: str = ""


class CartExportRequest(BaseModel):
    items: List[CartExportItem]


@purchases_router.get("/", response_model=List[PurchaseResponse])
def list_purchases(response: Response, supplier_id: Optional[int] = Query(None), material_id: Optional[int] = Query(None),
                    pending_payment_only: bool = Query(False),
                    limit: int = Query(500, ge=1, le=500), offset: int = Query(0, ge=0),
                    db: Session = Depends(get_db), auth=Depends(require_role("master"))):
    query = db.query(Purchase)
    if supplier_id:
        query = query.filter(Purchase.supplier_id == supplier_id)
    if material_id:
        query = query.filter(Purchase.material_id == material_id)
    if pending_payment_only:
        # Dashboard "pending purchases" widget - was previously derived
        # client-side from the same unbounded purchasesAPI.list() call
        # used for the recent-activity feed. A direct field filter.
        query = query.filter(Purchase.payment_status != "Paid")
    total = query.count()
    response.headers["X-Total-Count"] = str(total)
    return query.order_by(Purchase.date.desc()).offset(offset).limit(limit).all()


@purchases_router.post("/", response_model=PurchaseResponse, status_code=201)
def create_purchase(data: PurchaseCreate, request: Request, db: Session = Depends(get_db),
                     auth=Depends(require_role("master"))):
    purchase = ProcurementService.record_purchase(db, data)
    log_action(db, request, user_id=auth.get("user_id"), action="create_purchase", module_name="purchases",
               record_id=purchase.id, new_value={
                   "supplier_id": purchase.supplier_id, "material_id": purchase.material_id,
                   "quantity": float(purchase.quantity or 0), "invoice_total": float(purchase.invoice_total or 0),
               })
    return purchase


@purchases_router.get("/{purchase_id}", response_model=PurchaseResponse)
def get_purchase(purchase_id: int, db: Session = Depends(get_db), auth=Depends(require_role("master"))):
    purchase = db.query(Purchase).filter(Purchase.id == purchase_id).first()
    if not purchase:
        raise HTTPException(status_code=404, detail="Purchase not found")
    return purchase


@purchases_router.put("/{purchase_id}", response_model=PurchaseResponse)
def update_purchase(purchase_id: int, data: PurchaseUpdate, request: Request, db: Session = Depends(get_db),
                     auth=Depends(require_role("master"))):
    """Only payment_status can be edited after the fact - quantity/rate
    changes must go through a fresh purchase entry so stock stays auditable."""
    purchase = db.query(Purchase).filter(Purchase.id == purchase_id).first()
    if not purchase:
        raise HTTPException(status_code=404, detail="Purchase not found")
    updates = data.dict(exclude_unset=True)
    old_value = serializable_fields(purchase, updates.keys())
    for field, value in updates.items():
        setattr(purchase, field, value)
    db.add(purchase)
    db.commit()
    db.refresh(purchase)
    log_action(db, request, user_id=auth.get("user_id"), action="update_purchase", module_name="purchases",
               record_id=purchase.id, old_value=old_value, new_value=serializable_fields(purchase, updates.keys()))
    return purchase


@purchases_router.delete("/{purchase_id}", status_code=204)
def delete_purchase(purchase_id: int, request: Request, db: Session = Depends(get_db),
                     auth=Depends(require_role("master"))):
    """Only a purchase that has NOT yet been received can be deleted -
    a "Received" one has already increased Material.current_stock
    (StockService._apply_stock_receipt), and correctly reversing that
    is not a safe blind operation: other purchases/issues may have
    happened to the same material since, so undoing just this one's
    effect could easily leave stock at a wrong number rather than the
    right one. Correcting a received purchase's stock impact is a
    separate, deliberate action, not something this deletion silently
    attempts. Also blocked if a ProcurementRequirement is linked to
    this purchase (P0.2.5) - deleting it would leave that requirement
    pointing at a purchase that no longer exists."""
    purchase = db.query(Purchase).filter(Purchase.id == purchase_id).first()
    if not purchase:
        raise HTTPException(status_code=404, detail="Purchase not found")
    if purchase.receipt_status == "Received":
        raise HTTPException(
            status_code=409,
            detail="This purchase has already been received and its stock has been added - it cannot be deleted. Correct the stock separately if this entry was wrong.",
        )
    linked_requirement = db.query(ProcurementRequirement).filter(ProcurementRequirement.purchase_id == purchase.id).first()
    if linked_requirement:
        raise HTTPException(
            status_code=409,
            detail="This purchase is linked to a procurement requirement and cannot be deleted directly.",
        )

    old_value = serializable_fields(purchase, ["purchase_code", "material_id", "quantity", "rate", "receipt_status"])
    db.delete(purchase)
    db.commit()
    log_action(db, request, user_id=auth.get("user_id"), action="delete_purchase", module_name="purchases",
               record_id=purchase_id, old_value=old_value, new_value=None)


@purchases_router.post("/{purchase_id}/receive", response_model=PurchaseResponse)
def receive_purchase(purchase_id: int, data: Optional[PurchaseReceiveRequest] = None,
                      request: Request = None, db: Session = Depends(get_db),
                      auth=Depends(require_role("master"))):
    """Marks an Ordered/Partially Received purchase toward Received -
    the point stock actually increases. With no body (or an omitted
    quantity), receives everything still outstanding, exactly as
    before. A quantity can be passed to receive only part of the
    order, moving it to "Partially Received" until the rest arrives."""
    quantity_to_receive = data.quantity if data else None
    receive_location_id = data.location_id if data else None
    purchase = ProcurementService.mark_purchase_received(db, purchase_id, quantity_to_receive, receive_location_id)
    log_action(db, request, user_id=auth.get("user_id"), action="receive_purchase", module_name="purchases",
               record_id=purchase.id, new_value={
                   "material_id": purchase.material_id, "receipt_status": purchase.receipt_status,
                   "quantity_received": float(purchase.quantity_received or 0),
               })
    return purchase


@purchases_router.post("/cart-export")
def export_cart(data: CartExportRequest, db: Session = Depends(get_db), auth=Depends(get_current_user)):
    """Downloadable requisition list from the client-side purchase cart
    (redux, never persisted server-side) - so a Master/User can share
    "this is what needs buying" with the office/procurement team
    without first creating any Purchase records. Available to any
    authenticated user, matching the Materials page's own "Add to
    Cart" (not master-restricted) - unlike the rest of this module,
    which is master-only because it deals in real, committed purchase
    records. Rate/value columns are still gated behind is_privileged,
    matching every other export's redaction pattern."""
    is_privileged = auth.get("role", "user") in ("master",)
    rows = []
    for item in data.items:
        row = {"material": item.name, "quantity": item.quantity, "unit": item.unit,
               "supplier": item.supplier_name or "-"}
        if is_privileged:
            row["rate"] = float(item.rate) if item.rate is not None else None
            row["value"] = float(item.rate) * item.quantity if item.rate is not None else None
        rows.append(row)

    columns = ["material", "quantity", "unit", "supplier"]
    headers = ["Material", "Quantity", "Unit", "Preferred Supplier"]
    total_columns = []
    if is_privileged:
        columns[2:2] = ["rate", "value"]
        headers[2:2] = ["Rate", "Value"]
        total_columns = ["value"]

    buffer = build_workbook([{
        "sheet_name": "Purchase Cart", "title": "PURCHASE REQUISITION LIST",
        "columns": columns, "headers": headers, "rows": rows, "total_columns": total_columns,
        "subtitle": f"Generated on {datetime.utcnow().strftime('%d-%m-%Y %H:%M')}",
        "summary": [("Total Items", str(len(rows)))],
    }])
    return xlsx_response(buffer, "purchase-cart.xlsx")


# --- purchase_imports.py ---
purchase_imports_router = APIRouter(prefix="/api/purchase-imports", tags=["purchase-imports"])


@purchase_imports_router.get("/template")
def download_template(auth=Depends(require_role("master"))):
    buffer = build_import_template()
    return StreamingResponse(
        buffer, media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": "attachment; filename=Woodful_Purchase_Import_Template.xlsx"},
    )


@purchase_imports_router.post("/preview", response_model=ImportPreviewResponse)
def preview_import(file: UploadFile = File(...), db: Session = Depends(get_db),
                    auth=Depends(require_role("master"))):
    """Parses and validates the uploaded file - never writes anything to
    the database. The user reviews this, resolves any unmatched
    materials, and only then calls /commit."""
    original_name = file.filename or "import"
    ext = original_name.rsplit(".", 1)[-1].lower() if "." in original_name else ""
    if ext != "xlsx":
        raise HTTPException(status_code=400, detail=f"File must be a .xlsx workbook (got .{ext or 'unknown'}).")
    allowed_mime_types = {"application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"}
    if file.content_type not in allowed_mime_types:
        raise HTTPException(status_code=400, detail=f"Unrecognized file type: {file.content_type}")

    file_bytes = bytearray()
    while chunk := file.file.read(1024 * 1024):
        file_bytes.extend(chunk)
        if len(file_bytes) > settings.MAX_UPLOAD_SIZE:
            raise HTTPException(
                status_code=400,
                detail=f"File exceeds the {settings.MAX_UPLOAD_SIZE // (1024*1024)}MB size limit.",
            )
    try:
        raw_rows = parse_uploaded_workbook(bytes(file_bytes))
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except zipfile.BadZipFile:
        raise HTTPException(
            status_code=400,
            detail="Couldn't read this file - please upload a valid .xlsx file using the downloaded template.",
        )

    # Same normalize_match_key used when a row's typed name is looked up
    # (validate_and_match_row) - so whitespace/case differences on
    # either side never prevent a genuine match, without this ever
    # becoming fuzzy matching that could pick the wrong record.
    materials_by_name = {normalize_match_key(m.name): m for m in db.query(Material).all()}
    suppliers_by_name = {normalize_match_key(s.name): s for s in db.query(Supplier).all()}

    preview_rows = []
    matched_count = 0
    new_material_count = 0
    error_count = 0
    for idx, row in enumerate(raw_rows, start=1):
        result, errors = validate_and_match_row(row, db, materials_by_name, suppliers_by_name)
        if errors:
            error_count += 1
        elif result["is_new_material"]:
            new_material_count += 1
        else:
            matched_count += 1
        preview_rows.append(ImportRowPreview(row_number=idx, **result, errors=errors))

    return ImportPreviewResponse(
        total_rows=len(raw_rows), matched_rows=matched_count,
        new_material_rows=new_material_count, error_rows=error_count, rows=preview_rows,
    )


@purchase_imports_router.post("/error-report")
def download_error_report(file: UploadFile = File(...), db: Session = Depends(get_db),
                           auth=Depends(require_role("master"))):
    """Re-validates the same uploaded file (exactly the logic /preview
    uses) and returns a real .xlsx listing only the rejected rows,
    matching the established pattern from client_imports.py."""
    original_name = file.filename or "import"
    ext = original_name.rsplit(".", 1)[-1].lower() if "." in original_name else ""
    if ext != "xlsx":
        raise HTTPException(status_code=400, detail=f"File must be a .xlsx workbook (got .{ext or 'unknown'}).")
    file_bytes = bytearray()
    while chunk := file.file.read(1024 * 1024):
        file_bytes.extend(chunk)
        if len(file_bytes) > settings.MAX_UPLOAD_SIZE:
            raise HTTPException(status_code=400, detail=f"File exceeds the {settings.MAX_UPLOAD_SIZE // (1024*1024)}MB size limit.")
    try:
        raw_rows = parse_uploaded_workbook(bytes(file_bytes))
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except zipfile.BadZipFile:
        raise HTTPException(status_code=400, detail="Couldn't read this file - please upload a valid .xlsx file.")

    materials_by_name = {normalize_match_key(m.name): m for m in db.query(Material).all()}
    suppliers_by_name = {normalize_match_key(s.name): s for s in db.query(Supplier).all()}
    error_rows = []
    for idx, row in enumerate(raw_rows, start=1):
        result, errors = validate_and_match_row(row, db, materials_by_name, suppliers_by_name)
        if errors:
            error_rows.append({
                "row": idx, "material_name": result.get("material_name") or "",
                "quantity": str(result.get("quantity") or ""), "supplier_name": result.get("supplier_name") or "",
                "reason": "; ".join(errors),
            })

    from app.shared import build_workbook
    buffer = build_workbook([{
        "sheet_name": "Rejected Rows", "title": "Woodful Creations - Purchase Import Error Report",
        "subtitle": f"{len(error_rows)} of {len(raw_rows)} row(s) rejected. Fix these rows in your original "
                    f"spreadsheet and re-upload - only rejected rows need to be corrected.",
        "columns": ["row", "material_name", "quantity", "supplier_name", "reason"],
        "headers": ["Excel Row", "Material Name", "Quantity", "Supplier", "Reason Rejected"],
        "rows": error_rows,
    }])
    return StreamingResponse(
        buffer, media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": "attachment; filename=Woodful_Purchase_Import_Errors.xlsx"},
    )


@purchase_imports_router.post("/commit", response_model=ImportCommitResult)
def commit_import(data: ImportCommitRequest, request: Request, db: Session = Depends(get_db),
                   auth=Depends(require_role("master"))):
    """Actually creates records - only for rows the caller sends here,
    which should be exactly the rows the user reviewed and confirmed in
    the preview step. Each row commits individually (ProcurementService.
    record_purchase commits internally, same as manual purchase entry) -
    this is NOT one atomic all-or-nothing transaction. If a row fails
    partway through the batch, earlier rows in this same request are
    already committed; the response's created_purchases count and
    purchase_ids reflect exactly what succeeded before the failure, and
    the remaining rows are simply not processed - re-upload just the
    rows that didn't go through rather than the whole file."""
    created_materials = 0
    purchase_ids = []
    error_message = None

    for i, row in enumerate(data.rows):
        try:
            material_id = row.matched_material_id
            if row.create_new_material:
                if not row.material_name:
                    raise ValueError("Cannot create a material with no name")
                material_id = None
                for _ in range(5):
                    code = generate_unique_code(db, Material, "material_code", "MAT-")
                    material = Material(
                        material_code=code, business_id=generate_business_id(db), name=row.material_name,
                        brand_grade=row.specification, unit=row.unit, opening_stock=0,
                        current_stock=0, minimum_stock=0, average_rate=row.rate,
                    )
                    db.add(material)
                    try:
                        db.flush()
                        material_id = material.id
                        break
                    except Exception:
                        db.rollback()
                if material_id is None:
                    raise ValueError("Could not generate a unique material code")
                db.commit()
                created_materials += 1

            if not material_id:
                raise ValueError(f'Row for "{row.material_name}" has no resolved material - not imported.')

            purchase = ProcurementService.record_purchase(db, PurchaseCreate(
                date=row.invoice_date or datetime.utcnow(),
                supplier_id=row.matched_supplier_id, material_id=material_id,
                quantity=row.quantity, unit=row.unit, rate=row.rate,
                gst_percent=row.gst_percent, payment_status="Paid",
            ))
            purchase_ids.append(purchase.id)
        except (ValueError, HTTPException) as e:
            detail = e.detail if isinstance(e, HTTPException) else str(e)
            error_message = f"Stopped at row {i + 1}: {detail}"
            break

    log_action(
        db, request, user_id=auth.get("user_id"), action="import_purchases", module_name="purchases",
        new_value={"created_materials": created_materials, "created_purchases": len(purchase_ids)},
    )

    return ImportCommitResult(
        created_materials=created_materials, created_purchases=len(purchase_ids),
        purchase_ids=purchase_ids, error=error_message,
    )


# --- procurement_requirements.py ---
procurement_requirements_router = APIRouter(prefix="/api/procurement-requirements", tags=["procurement-requirements"])


def _serialize_requirement(db: Session, requirement: ProcurementRequirement) -> ProcurementRequirementResponse:
    response = ProcurementRequirementResponse.model_validate(requirement)
    if requirement.material:
        response.material_name = requirement.material.name
    if requirement.decision:
        if requirement.decision.recommended_supplier:
            response.decision.recommended_supplier_name = requirement.decision.recommended_supplier.name
        if requirement.decision.selected_supplier:
            response.decision.selected_supplier_name = requirement.decision.selected_supplier.name
    return response


@procurement_requirements_router.get("/", response_model=List[ProcurementRequirementResponse])
def list_procurement_requirements(order_id: Optional[int] = Query(None), status: Optional[str] = Query(None),
                                   response: Response = None,
                                   limit: int = Query(500, ge=1, le=500), offset: int = Query(0, ge=0),
                                   db: Session = Depends(get_db), auth=Depends(require_role("master"))):
    # Defect repair (F138 P1): ProcurementRequirement is a persisted,
    # never-pruned procurement decision record (see its own docstring)
    # that only accumulates over time - an unfiltered call (no order_id
    # or status) previously fetched every requirement ever created with
    # no limit at all. Paginated the same way every other transactional-
    # history list in this codebase already is (see list_purchases).
    query = db.query(ProcurementRequirement)
    if order_id:
        query = query.filter(ProcurementRequirement.order_id == order_id)
    if status:
        query = query.filter(ProcurementRequirement.status == status)
    total = query.count()
    if response is not None:
        response.headers["X-Total-Count"] = str(total)
    rows = query.order_by(ProcurementRequirement.created_at.desc()).offset(offset).limit(limit).all()
    return [_serialize_requirement(db, r) for r in rows]


@procurement_requirements_router.post("/", response_model=ProcurementRequirementResponse, status_code=201)
def create_procurement_requirement(data: ProcurementRequirementCreate, db: Session = Depends(get_db),
                                    auth=Depends(require_role("master"))):
    """Snapshots the CURRENT shortage from the one authoritative
    calculation (StockService.calculate_order_material_requirements) -
    required/available/shortage are never accepted from the client,
    exactly the P0.2.1 requirement that this must not become a second,
    independently-drifting shortage engine."""
    from app.modules.inventory.services import StockService

    result = StockService.calculate_order_material_requirements(db, data.order_id)
    row = next((r for r in result["materials"] if r["material_id"] == data.material_id), None)
    if row is None:
        raise HTTPException(
            status_code=400,
            detail="This order has no material requirement recorded for that material - nothing to snapshot.",
        )

    for _ in range(5):
        requirement = ProcurementRequirement(
            order_id=data.order_id, material_id=data.material_id,
            required_quantity=row["required"], available_quantity_at_creation=row["available"],
            shortage_quantity_at_creation=row["shortage"],
            priority=data.priority, required_by_date=data.required_by_date, remarks=data.remarks,
            created_by=auth.get("user_id"), business_id=generate_business_id(db),
        )
        db.add(requirement)
        try:
            db.commit()
        except IntegrityError:
            db.rollback()
            continue
        db.refresh(requirement)
        return _serialize_requirement(db, requirement)
    raise HTTPException(status_code=500, detail="Unable to generate a unique business ID, please try again")


@procurement_requirements_router.get("/{requirement_id}", response_model=ProcurementRequirementResponse)
def get_procurement_requirement(requirement_id: int, db: Session = Depends(get_db), auth=Depends(require_role("master"))):
    requirement = db.query(ProcurementRequirement).filter(ProcurementRequirement.id == requirement_id).first()
    if not requirement:
        raise HTTPException(status_code=404, detail="Procurement requirement not found")
    return _serialize_requirement(db, requirement)


@procurement_requirements_router.put("/{requirement_id}", response_model=ProcurementRequirementResponse)
def update_procurement_requirement(requirement_id: int, data: ProcurementRequirementUpdate,
                                    db: Session = Depends(get_db), auth=Depends(require_role("master"))):
    requirement = db.query(ProcurementRequirement).filter(ProcurementRequirement.id == requirement_id).with_for_update().first()
    if not requirement:
        raise HTTPException(status_code=404, detail="Procurement requirement not found")
    for field, value in data.dict(exclude_unset=True).items():
        setattr(requirement, field, value)
    db.add(requirement)
    db.commit()
    db.refresh(requirement)
    return _serialize_requirement(db, requirement)


@procurement_requirements_router.get("/{requirement_id}/supplier-options")
def get_requirement_supplier_options(requirement_id: int, db: Session = Depends(get_db), auth=Depends(require_role("master"))):
    """Read-only preview of the same recommendation
    record_supplier_decision itself uses - so the frontend can show
    "here are your options" before the Master commits to one. Not a
    second recommendation calculation: this and the decision endpoint
    both call ProcurementService._supplier_options_for_materials."""
    from app.modules.procurement.services import ProcurementService

    requirement = db.query(ProcurementRequirement).filter(ProcurementRequirement.id == requirement_id).first()
    if not requirement:
        raise HTTPException(status_code=404, detail="Procurement requirement not found")
    options = ProcurementService._supplier_options_for_materials(db, [requirement.material_id]).get(requirement.material_id, [])
    return {"requirement_id": requirement_id, "material_id": requirement.material_id, "options": options}


@procurement_requirements_router.post("/{requirement_id}/decision", response_model=SupplierDecisionResponse, status_code=201)
def record_supplier_decision(requirement_id: int, data: SupplierDecisionCreate, db: Session = Depends(get_db),
                              auth=Depends(require_role("master"))):
    """Preserves the distinction P0.2.3 requires: what the system
    recommended versus what the Master actually chose. The
    recommendation is snapshotted here, at decision time, from the
    same supplier-options calculation the material-requirements
    endpoint already surfaces - never re-derived later, so a
    subsequent price change can never retroactively change what this
    decision recorded as "recommended" at the time it was made."""
    if data.requirement_id != requirement_id:
        raise HTTPException(status_code=400, detail="requirement_id in the path and body must match")
    requirement = db.query(ProcurementRequirement).filter(ProcurementRequirement.id == requirement_id).with_for_update().first()
    if not requirement:
        raise HTTPException(status_code=404, detail="Procurement requirement not found")
    if requirement.decision is not None:
        raise HTTPException(status_code=409, detail="A supplier decision has already been recorded for this requirement.")

    # P0.2.4: the selected supplier must actually be able to supply this
    # material - never trust a frontend dropdown to have filtered this
    # correctly. A supplier with no SupplierMaterial link for this exact
    # material is rejected here, in the backend, regardless of what the
    # client sent.
    valid_link = db.query(SupplierMaterial).filter(
        SupplierMaterial.supplier_id == data.selected_supplier_id,
        SupplierMaterial.material_id == requirement.material_id,
    ).first()
    if not valid_link:
        raise HTTPException(
            status_code=400,
            detail="The selected supplier has no recorded supply relationship for this material - "
                   "add a SupplierMaterial link first, or choose a different supplier.",
        )

    from app.modules.procurement.services import ProcurementService
    options = ProcurementService._supplier_options_for_materials(db, [requirement.material_id]).get(requirement.material_id, [])
    top = options[0] if options else None
    recommended_reason = None
    if top:
        recommended_reason = "Preferred supplier" if top.get("is_preferred") else "Lowest price"
        if top.get("lead_time_days") is not None:
            recommended_reason += f", {top['lead_time_days']}d lead time"

    for _ in range(5):
        decision = SupplierDecision(
            requirement_id=requirement_id,
            recommended_supplier_id=top["supplier_id"] if top else None,
            recommended_reason=recommended_reason,
            selected_supplier_id=data.selected_supplier_id, decision_reason=data.decision_reason,
            decided_by=auth.get("user_id"), business_id=generate_business_id(db),
        )
        db.add(decision)
        try:
            db.commit()
        except IntegrityError:
            db.rollback()
            continue
        db.refresh(decision)
        response = SupplierDecisionResponse.model_validate(decision)
        if decision.recommended_supplier:
            response.recommended_supplier_name = decision.recommended_supplier.name
        if decision.selected_supplier:
            response.selected_supplier_name = decision.selected_supplier.name
        response.followed_recommendation = decision.followed_recommendation
        return response
    raise HTTPException(status_code=500, detail="Unable to generate a unique business ID, please try again")


@procurement_requirements_router.post("/{requirement_id}/purchase", response_model=PurchaseResponse, status_code=201)
def create_purchase_from_requirement(requirement_id: int, data: RequirementPurchaseCreate,
                                      db: Session = Depends(get_db), auth=Depends(require_role("master"))):
    """P0.2.5 traceability: the resulting Purchase is persisted back onto
    the requirement (requirement.purchase_id), and a requirement that
    already has one cannot create a second - the two known failure
    modes section 12 names ("known related records become disconnected"
    and "fulfilled requirements incorrectly create another purchase")
    are both a single row-lock + two checks, not separate mechanisms.
    supplier_id/material_id for the Purchase come from the requirement's
    own recorded SupplierDecision, never from this request body, so the
    purchase can never disagree with the decision actually made."""
    from app.modules.procurement.services import ProcurementService

    requirement = db.query(ProcurementRequirement).filter(ProcurementRequirement.id == requirement_id).with_for_update().first()
    if not requirement:
        raise HTTPException(status_code=404, detail="Procurement requirement not found")
    if requirement.status in ("Fulfilled", "Cancelled"):
        raise HTTPException(status_code=409, detail=f"This requirement is already {requirement.status.lower()} - cannot create a purchase from it.")
    if requirement.purchase_id is not None:
        raise HTTPException(status_code=409, detail="A purchase has already been created for this requirement.")
    if requirement.decision is None:
        raise HTTPException(status_code=400, detail="Record a supplier decision for this requirement before creating a purchase.")

    purchase_data = PurchaseCreate(
        date=datetime.utcnow(), expected_delivery_date=data.expected_delivery_date,
        supplier_id=requirement.decision.selected_supplier_id, material_id=requirement.material_id,
        quantity=data.quantity, unit=data.unit, rate=data.rate, gst_percent=data.gst_percent,
        receipt_status=data.receipt_status, location_id=data.location_id,
    )
    purchase = ProcurementService.record_purchase(db, purchase_data)

    requirement.purchase_id = purchase.id
    # A purchase recorded as already fully "Received" means the goods
    # are already in hand - the requirement is genuinely fulfilled, not
    # merely ordered (matching section 14's "do not mark a requirement
    # fulfilled merely because a Purchase exists" - this is the one
    # case where the Purchase itself confirms receipt has truly
    # happened, not an assumption).
    requirement.status = "Fulfilled" if data.receipt_status == "Received" else "Ordered"
    db.add(requirement)
    db.commit()
    db.refresh(purchase)
    return purchase


# --- personal_cart.py ---
personal_cart_router = APIRouter(prefix="/api/personal-cart", tags=["personal-cart"])


def _my_items_query(db: Session, auth):
    """Every query in this file starts here - scoped to the
    authenticated user's own id. There is no path in this personal_cart_router that
    accepts or trusts a client-supplied user_id; "whose cart" is always
    derived from the token, never a request parameter (matching the
    "Pankaj cannot see Garima's cart" requirement at the API layer, not
    just hidden in the UI)."""
    return db.query(PersonalCartItem).filter(
        PersonalCartItem.user_id == auth.get("user_id"), PersonalCartItem.status == "ACTIVE"
    )


def _serialize_cart_items(items, role: str):
    """rate is stored regardless of role (useful for a future
    master-side review of what's been requested), but genuinely
    redacted here in the response for non-privileged roles - an
    employee should not see a material's price by adding it to their
    own cart when the Materials page itself hides it from them."""
    responses = [PersonalCartItemResponse.model_validate(i) for i in items]
    if role not in ("master",):
        for r in responses:
            r.rate = None
    return responses


def _serialize_cart_item(item, role: str):
    return _serialize_cart_items([item], role)[0]


@personal_cart_router.get("/", response_model=List[PersonalCartItemResponse])
def list_my_cart(db: Session = Depends(get_db), auth=Depends(get_current_user)):
    items = _my_items_query(db, auth).order_by(PersonalCartItem.created_at.asc()).all()
    return _serialize_cart_items(items, auth.get("role", "user"))


@personal_cart_router.post("/", response_model=PersonalCartItemResponse, status_code=201)
def add_to_cart(data: PersonalCartItemCreate, db: Session = Depends(get_db), auth=Depends(get_current_user)):
    material = db.query(Material).filter(Material.id == data.material_id).first()
    if not material:
        raise HTTPException(status_code=404, detail="Material not found")

    supplier_name = None
    if data.supplier_id:
        supplier = db.query(Supplier).filter(Supplier.id == data.supplier_id).first()
        supplier_name = supplier.name if supplier else None

    # Adding the same material again increases quantity on the existing
    # active row, rather than creating a duplicate line - matches how
    # the previous client-side cart already behaved.
    existing = _my_items_query(db, auth).filter(PersonalCartItem.material_id == data.material_id).first()
    if existing:
        existing.quantity = existing.quantity + data.quantity
        db.add(existing)
        db.commit()
        db.refresh(existing)
        return _serialize_cart_item(existing, auth.get("role", "user"))

    item = PersonalCartItem(
        user_id=auth.get("user_id"), material_id=material.id, material_name=material.name,
        unit=material.unit, quantity=data.quantity, supplier_id=data.supplier_id,
        supplier_name=supplier_name, rate=material.average_rate, note=data.note, status="ACTIVE",
    )
    db.add(item)
    db.commit()
    db.refresh(item)
    return _serialize_cart_item(item, auth.get("role", "user"))


@personal_cart_router.put("/{item_id}", response_model=PersonalCartItemResponse)
def update_cart_item(item_id: int, data: PersonalCartItemUpdate, db: Session = Depends(get_db),
                      auth=Depends(get_current_user)):
    item = _my_items_query(db, auth).filter(PersonalCartItem.id == item_id).first()
    if not item:
        raise HTTPException(status_code=404, detail="Cart item not found")
    update_data = data.dict(exclude_unset=True)
    if "quantity" in update_data and update_data["quantity"] <= 0:
        snapshot = PersonalCartItemResponse(
            id=item.id, material_id=item.material_id, material_name=item.material_name, unit=item.unit,
            quantity=0, supplier_id=item.supplier_id, supplier_name=item.supplier_name,
            rate=item.rate if auth.get("role", "user") in ("master",) else None,
            note=item.note, status="REMOVED", created_at=item.created_at,
        )
        db.delete(item)
        db.commit()
        return snapshot
    for field, value in update_data.items():
        setattr(item, field, value)
    db.add(item)
    db.commit()
    db.refresh(item)
    return _serialize_cart_item(item, auth.get("role", "user"))


@personal_cart_router.delete("/{item_id}", status_code=204)
def remove_cart_item(item_id: int, db: Session = Depends(get_db), auth=Depends(get_current_user)):
    item = _my_items_query(db, auth).filter(PersonalCartItem.id == item_id).first()
    if not item:
        raise HTTPException(status_code=404, detail="Cart item not found")
    db.delete(item)
    db.commit()


@personal_cart_router.delete("/", status_code=204)
def clear_my_cart(db: Session = Depends(get_db), auth=Depends(get_current_user)):
    _my_items_query(db, auth).delete(synchronize_session=False)
    db.commit()
