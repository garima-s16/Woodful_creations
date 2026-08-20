from typing import List, Optional
import secrets

from fastapi import APIRouter, Depends, HTTPException, Query, UploadFile, File
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.security import require_role
from app.core.audit import log_action, serializable_fields
from app.core.config import settings
from fastapi import Request
from app.models.payment import Payment
from app.models.payment_document import PaymentDocument
from app.models.order import Order
from app.schemas.payment import PaymentCreate, PaymentUpdate, PaymentResponse
from app.schemas.payment_document import PaymentDocumentResponse
from app.services.order_service import OrderService

from app.utils.validators import validate_file_signature
from app.core.storage import get_storage_backend


router = APIRouter(prefix="/api/payments", tags=["payments"])

PAYMENT_DOC_ALLOWED_EXTENSIONS = {"pdf", "jpg", "jpeg", "png"}
PAYMENT_DOC_ALLOWED_MIME_TYPES = {"application/pdf", "image/jpeg", "image/png"}


@router.get("/", response_model=List[PaymentResponse])
def list_payments(order_id: Optional[int] = Query(None), client_id: Optional[int] = Query(None),
                   db: Session = Depends(get_db), auth=Depends(require_role("master"))):
    query = db.query(Payment)
    if order_id:
        query = query.filter(Payment.order_id == order_id)
    if client_id:
        # One join instead of the caller fetching per-order and merging -
        # a client with many orders would otherwise mean many round trips.
        query = query.join(Order, Payment.order_id == Order.id).filter(Order.client_id == client_id)
    return query.order_by(Payment.date.desc()).all()


@router.post("/", response_model=PaymentResponse, status_code=201)
def create_payment(data: PaymentCreate, request: Request, db: Session = Depends(get_db),
                    auth=Depends(require_role("master"))):
    payment = OrderService.record_payment(db, data)
    log_action(db, request, user_id=auth.get("user_id"), action="create_payment",
               module_name="payments", record_id=payment.id, new_value={"amount": str(payment.amount)})
    return payment


@router.get("/{payment_id}", response_model=PaymentResponse)
def get_payment(payment_id: int, db: Session = Depends(get_db),
                 auth=Depends(require_role("master"))):
    payment = db.query(Payment).filter(Payment.id == payment_id).first()
    if not payment:
        raise HTTPException(status_code=404, detail="Payment not found")
    return payment


@router.put("/{payment_id}", response_model=PaymentResponse)
def update_payment(payment_id: int, data: PaymentUpdate, request: Request, db: Session = Depends(get_db),
                    auth=Depends(require_role("master"))):
    payment = db.query(Payment).filter(Payment.id == payment_id).first()
    if not payment:
        raise HTTPException(status_code=404, detail="Payment not found")
    updates = data.dict(exclude_unset=True)
    old_value = serializable_fields(payment, updates.keys())
    for field, value in updates.items():
        setattr(payment, field, value)
    db.add(payment)
    payment.order.recompute_totals()
    db.add(payment.order)
    db.commit()
    db.refresh(payment)
    log_action(db, request, user_id=auth.get("user_id"), action="update_payment", module_name="payments",
               record_id=payment.id, old_value=old_value, new_value=serializable_fields(payment, updates.keys()))
    return payment


@router.delete("/{payment_id}", status_code=204)
def delete_payment(payment_id: int, request: Request, db: Session = Depends(get_db),
                    auth=Depends(require_role("master"))):
    """Was entirely missing - a payment recorded in error (wrong order,
    duplicate entry, wrong amount typed in) had no way to actually be
    removed, only edited, which is not the same thing and leaves a
    phantom record. Recomputes the order's total_received/balance the
    same way record_payment and update_payment do, so a deleted
    payment can never leave a stale balance behind."""
    payment = db.query(Payment).filter(Payment.id == payment_id).first()
    if not payment:
        raise HTTPException(status_code=404, detail="Payment not found")
    old_value = {
        "receipt_code": payment.receipt_code, "order_id": payment.order_id,
        "amount": str(payment.amount), "payment_type": payment.payment_type,
        "payment_mode": payment.payment_mode, "date": str(payment.date),
    }
    order = payment.order
    db.delete(payment)
    db.flush()
    order.recompute_totals()
    db.add(order)
    db.commit()
    log_action(db, request, user_id=auth.get("user_id"), action="delete_payment", module_name="payments",
               record_id=payment_id, old_value=old_value)


@router.get("/{payment_id}/documents", response_model=List[PaymentDocumentResponse])
def list_payment_documents(payment_id: int, db: Session = Depends(get_db), auth=Depends(require_role("master"))):
    if not db.query(Payment).filter(Payment.id == payment_id).first():
        raise HTTPException(status_code=404, detail="Payment not found")
    return db.query(PaymentDocument).filter(PaymentDocument.payment_id == payment_id).order_by(
        PaymentDocument.created_at.desc()
    ).all()


@router.post("/{payment_id}/documents", response_model=PaymentDocumentResponse, status_code=201)
def upload_payment_document(payment_id: int, file: UploadFile = File(...), description: Optional[str] = None,
                             request: Request = None, db: Session = Depends(get_db),
                             auth=Depends(require_role("master"))):
    """Proof of payment - cheque scan, UPI screenshot, bank transfer
    receipt. Same validation discipline already established for
    client documents and candidate resumes: extension allowlist, MIME
    check, a real streamed byte count against the size limit, and a
    random server-side filename never derived from user input."""
    payment = db.query(Payment).filter(Payment.id == payment_id).first()
    if not payment:
        raise HTTPException(status_code=404, detail="Payment not found")

    original_name = file.filename or "document"
    ext = original_name.rsplit(".", 1)[-1].lower() if "." in original_name else ""
    if ext not in PAYMENT_DOC_ALLOWED_EXTENSIONS:
        raise HTTPException(status_code=400, detail=f"File must be a PDF, JPG, or PNG (got .{ext or 'unknown'}).")
    if file.content_type not in PAYMENT_DOC_ALLOWED_MIME_TYPES:
        raise HTTPException(status_code=400, detail=f"Unrecognized file type: {file.content_type}")

    backend = get_storage_backend()
    stored_filename = f"payment_documents/{secrets.token_hex(16)}.{ext}"

    size = 0
    first_chunk = True
    chunks = []
    try:
        while chunk := file.file.read(1024 * 1024):
            if first_chunk:
                if not validate_file_signature(ext, chunk):
                    raise HTTPException(
                        status_code=400,
                        detail="The file's contents don't match its extension. Please upload a genuine file of the stated type.",
                    )
                first_chunk = False
            size += len(chunk)
            if size > settings.MAX_UPLOAD_SIZE:
                raise HTTPException(
                    status_code=400,
                    detail=f"File exceeds the {settings.MAX_UPLOAD_SIZE // (1024*1024)}MB size limit.",
                )
            chunks.append(chunk)
        backend.save(stored_filename, b"".join(chunks))
    except HTTPException:
        raise
    except Exception:
        raise HTTPException(status_code=500, detail="Failed to save the uploaded file.")

    document = PaymentDocument(
        payment_id=payment_id, original_filename=original_name, stored_filename=stored_filename,
        content_type=file.content_type, description=description, uploaded_by=str(auth.get("user_id", "")),
    )
    db.add(document)
    db.commit()
    db.refresh(document)
    if request is not None:
        log_action(db, request, user_id=auth.get("user_id"), action="upload_payment_document", module_name="payments",
                   record_id=document.id, new_value={"payment_id": payment_id, "filename": original_name})
    return document


@router.get("/{payment_id}/documents/{document_id}/download")
def download_payment_document(payment_id: int, document_id: int, db: Session = Depends(get_db),
                               auth=Depends(require_role("master"))):
    """Object-level check: the document must actually belong to the
    payment_id in the URL, not just exist by document_id - the same
    IDOR protection already established for client documents."""
    document = db.query(PaymentDocument).filter(
        PaymentDocument.id == document_id, PaymentDocument.payment_id == payment_id,
    ).first()
    if not document:
        raise HTTPException(status_code=404, detail="Document not found")
    backend = get_storage_backend()
    if not backend.exists(document.stored_filename):
        raise HTTPException(status_code=404, detail="The stored file could not be found.")
    file_path = backend.local_path_for_serving(document.stored_filename)
    return FileResponse(
        file_path, media_type=document.content_type or "application/octet-stream",
        filename=document.original_filename,
        headers={"Cache-Control": "no-store, private"},
    )


@router.delete("/{payment_id}/documents/{document_id}", status_code=204)
def delete_payment_document(payment_id: int, document_id: int, request: Request, db: Session = Depends(get_db),
                             auth=Depends(require_role("master"))):
    document = db.query(PaymentDocument).filter(
        PaymentDocument.id == document_id, PaymentDocument.payment_id == payment_id,
    ).first()
    if not document:
        raise HTTPException(status_code=404, detail="Document not found")
    get_storage_backend().delete(document.stored_filename)
    old_value = {"payment_id": payment_id, "filename": document.original_filename}
    db.delete(document)
    db.commit()
    log_action(db, request, user_id=auth.get("user_id"), action="delete_payment_document", module_name="payments",
               record_id=document_id, old_value=old_value)
