from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Request
import zipfile
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError
from fastapi.responses import StreamingResponse

from app.core.database import get_db
from app.core.config import settings
from app.core.security import require_role
from app.core.audit import log_action
from app.models.product import Product
from app.models.product_category import ProductSubcategory
from app.schemas.product_import import (
    ProductImportPreviewResponse, ProductImportRowPreview, ProductImportCommitRequest, ProductImportCommitResult,
)
from app.utils.id_generator import generate_unique_code, generate_short_id
from app.utils.product_import import (
    build_product_import_template, PRODUCT_IMPORT_COLUMNS, HEADER_ALIASES, validate_and_match_row,
)
from app.utils.bulk_import import parse_uploaded_workbook, normalize_match_key

router = APIRouter(prefix="/api/product-imports", tags=["product-imports"])


@router.get("/template")
def download_template():
    """Family 21's "Download Template" step - real branded .xlsx, built
    on the same reusable infrastructure (utils/bulk_import.py) every
    future bulk import in this app should build on. Master-only would be
    over-restrictive here (downloading a blank template reveals nothing
    sensitive) but every other step below is master-gated, matching
    "Protect ... imports" from the brief."""
    buffer = build_product_import_template()
    return StreamingResponse(
        buffer, media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": "attachment; filename=Woodful_Product_Import_Template.xlsx"},
    )


@router.post("/preview", response_model=ProductImportPreviewResponse)
def preview_import(file: UploadFile = File(...), db: Session = Depends(get_db),
                    auth=Depends(require_role("master"))):
    """Parses and validates the uploaded file - never writes anything to
    the database. The user reviews this (and can fix any row that
    references a Category/Subcategory that doesn't exist yet) before
    calling /commit."""
    original_name = file.filename or "import"
    ext = original_name.rsplit(".", 1)[-1].lower() if "." in original_name else ""
    if ext != "xlsx":
        raise HTTPException(status_code=400, detail=f"File must be a .xlsx workbook (got .{ext or 'unknown'}).")
    if file.content_type not in {"application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"}:
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
        raw_rows = parse_uploaded_workbook(bytes(file_bytes), PRODUCT_IMPORT_COLUMNS, HEADER_ALIASES)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except zipfile.BadZipFile:
        raise HTTPException(
            status_code=400,
            detail="Couldn't read this file - please upload a valid .xlsx file using the downloaded template.",
        )

    subcategories_by_name = {normalize_match_key(s.name): s for s in db.query(ProductSubcategory).all()}

    preview_rows = []
    valid_count = 0
    error_count = 0
    for idx, row in enumerate(raw_rows, start=1):
        result, errors = validate_and_match_row(row, db, subcategories_by_name=subcategories_by_name)
        if errors:
            error_count += 1
        else:
            valid_count += 1
        preview_rows.append(ProductImportRowPreview(row_number=idx, **result, errors=errors))

    return ProductImportPreviewResponse(
        total_rows=len(raw_rows), valid_rows=valid_count, error_rows=error_count, rows=preview_rows,
    )


@router.post("/commit", response_model=ProductImportCommitResult)
def commit_import(data: ProductImportCommitRequest, request: Request, db: Session = Depends(get_db),
                   auth=Depends(require_role("master"))):
    """Actually creates Products - only for rows the caller sends here,
    which should be exactly the rows the user reviewed and confirmed in
    preview. Each row is its own retry-on-IntegrityError insert (same
    discipline as create_product in api/routes/products.py) - product_code/
    business_id are always generated here, never accepted from the
    uploaded file. NOT one atomic all-or-nothing transaction, matching
    Purchase Import's existing behavior: if a row fails partway through,
    earlier rows in this same request are already committed; re-upload
    just the rows that didn't go through."""
    created_ids = []
    error_message = None

    for i, row in enumerate(data.rows):
        try:
            payload = row.dict()
            product = None
            for _ in range(5):
                code = generate_unique_code(db, Product, "product_code", "PROD-")
                product = Product(**payload, product_code=code, business_id=generate_short_id(db))
                db.add(product)
                try:
                    db.commit()
                    break
                except IntegrityError:
                    db.rollback()
                    product = None
            if product is None:
                raise ValueError(f'Could not generate a unique product code for "{row.name}"')
            db.refresh(product)
            created_ids.append(product.id)
            log_action(db, request, user_id=auth.get("user_id"), action="import_product", module_name="products",
                       record_id=product.id, new_value={"name": product.name, "product_code": product.product_code})
        except (ValueError, HTTPException) as e:
            detail = e.detail if isinstance(e, HTTPException) else str(e)
            error_message = f"Stopped at row {i + 1}: {detail}"
            break

    return ProductImportCommitResult(created_products=len(created_ids), product_ids=created_ids, error=error_message)
