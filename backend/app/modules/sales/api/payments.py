from typing import List, Optional
from decimal import Decimal
import secrets
import logging

logger = logging.getLogger(__name__)

from fastapi import APIRouter, Depends, HTTPException, Query, UploadFile, File, Response
from sqlalchemy.orm import Session

from app.platform.database.database import get_db
from app.platform.security.security import require_role
from app.platform.audit.audit import log_action, serializable_fields
from app.platform.configuration.config import settings
from fastapi import Request
from app.modules.sales.models import Payment, PaymentDocument, Order
from app.modules.sales.schemas import PaymentCreate, PaymentUpdate, PaymentResponse, PaymentDocumentResponse
from app.modules.clients.schemas import ClientEmailPreview, ClientEmailSendRequest, ClientEmailSendResult
from app.modules.sales.pdf_generator import generate_invoice_pdf
from app.modules.communications.services.email_service import EmailService
from app.modules.clients.models import ClientActivity
from app.modules.sales.order_service import OrderService

from app.shared.validators import validate_file_signature
from app.platform.storage.storage import get_storage_backend, get_storage_backend_for_record


router = APIRouter(prefix="/api/payments", tags=["payments"])

PAYMENT_DOC_ALLOWED_EXTENSIONS = {"pdf", "jpg", "jpeg", "png"}
PAYMENT_DOC_ALLOWED_MIME_TYPES = {"application/pdf", "image/jpeg", "image/png"}


@router.get("/", response_model=List[PaymentResponse])
def list_payments(order_id: Optional[int] = Query(None), client_id: Optional[int] = Query(None),
                   limit: Optional[int] = Query(None, ge=1, le=500), offset: int = Query(0, ge=0),
                   db: Session = Depends(get_db), auth=Depends(require_role("master"))):
    query = db.query(Payment)
    if order_id:
        query = query.filter(Payment.order_id == order_id)
    if client_id:
        # One join instead of the caller fetching per-order and merging -
        # a client with many orders would otherwise mean many round trips.
        query = query.join(Order, Payment.order_id == Order.id).filter(Order.client_id == client_id)
    query = query.order_by(Payment.date.desc())
    if limit is not None:
        # Optional and unbounded by default on purpose - PaymentsPage
        # renders the full list with no client-side pagination of its
        # own, so a default limit here would silently truncate that
        # page. Only callers that explicitly ask (the dashboard) get a
        # bounded result.
        query = query.offset(offset).limit(limit)
    return query.all()


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


@router.get("/{payment_id}/email-preview", response_model=ClientEmailPreview)
def preview_payment_receipt_email(payment_id: int, db: Session = Depends(get_db), auth=Depends(require_role("master"))):
    payment = db.query(Payment).filter(Payment.id == payment_id).first()
    if not payment:
        raise HTTPException(status_code=404, detail="Payment not found")
    order = payment.order
    client = order.client
    subject = f"Payment Receipt - {order.order_code} - Woodful Creations"
    body = (
        f"Dear {client.name},\n\n"
        f"Thank you for your payment of Rs {payment.amount:,.2f} against order {order.order_code}.\n\n"
        f"Please find the receipt attached.\n\n"
        f"Regards,\nWoodful Creations"
    )
    return ClientEmailPreview(
        recipient_email=client.email, client_has_email=bool(client.email),
        subject=subject, body=body,
        attachment_filename=f"Receipt-{payment.receipt_code or payment.id}.pdf",
    )


@router.post("/{payment_id}/send-email", response_model=ClientEmailSendResult)
def send_payment_receipt_email(payment_id: int, data: ClientEmailSendRequest, request: Request,
                                db: Session = Depends(get_db), auth=Depends(require_role("master"))):
    payment = db.query(Payment).filter(Payment.id == payment_id).first()
    if not payment:
        raise HTTPException(status_code=404, detail="Payment not found")
    if not data.recipient_email or "@" not in data.recipient_email:
        raise HTTPException(status_code=400, detail="A valid recipient email is required")

    order = payment.order
    # Prefer the actual uploaded receipt scan if one exists for this
    # payment (the real proof of payment) - only fall back to the
    # invoice PDF (which shows payment/received-amount detail) when
    # nothing was ever uploaded.
    uploaded_receipt = db.query(PaymentDocument).filter(PaymentDocument.payment_id == payment.id).first()
    if uploaded_receipt:
        backend, storage_ref = get_storage_backend_for_record(uploaded_receipt)
        attachment_bytes = backend.read(storage_ref)
        attachment_filename = uploaded_receipt.original_filename
    else:
        all_payments = db.query(Payment).filter(Payment.order_id == order.id).order_by(Payment.date).all()
        pdf_buffer = generate_invoice_pdf(order, all_payments)
        attachment_bytes = pdf_buffer.read()
        attachment_filename = f"Receipt-{payment.receipt_code or payment.id}.pdf"

    email_service = EmailService()
    sent = email_service.send_email(
        to_email=data.recipient_email, subject=data.subject, body=data.body, is_html=False,
        attachment_bytes=attachment_bytes, attachment_filename=attachment_filename,
    )

    db.add(ClientActivity(
        client_id=order.client_id, activity_type="Email",
        summary=f"Emailed payment receipt for {order.order_code} to {data.recipient_email} - amount Rs {payment.amount:,.2f}"
                + ("" if sent else " (SEND FAILED - see server logs)"),
        logged_by=auth.get("email") or "system",
    ))
    db.commit()
    log_action(db, request, user_id=auth.get("user_id"), action="send_payment_receipt_email",
               module_name="payments", record_id=payment.id,
               new_value={"recipient": data.recipient_email, "sent": sent})

    if not sent:
        raise HTTPException(
            status_code=502,
            detail="The receipt could not be emailed right now (email service unavailable or misconfigured). "
                   "The payment itself is unaffected - this only failed to send.",
        )
    return ClientEmailSendResult(sent=True, message=f"Receipt emailed to {data.recipient_email}.")


@router.put("/{payment_id}", response_model=PaymentResponse)
def update_payment(payment_id: int, data: PaymentUpdate, request: Request, db: Session = Depends(get_db),
                    auth=Depends(require_role("master"))):
    payment = db.query(Payment).filter(Payment.id == payment_id).first()
    if not payment:
        raise HTTPException(status_code=404, detail="Payment not found")
    updates = data.dict(exclude_unset=True)

    # Locked before validating, same as record_payment - a concurrent
    # update/create/delete against the same order must not be able to
    # observe a pre-lock total and let this update through based on
    # stale numbers.
    order = db.query(Order).filter(Order.id == payment.order_id).with_for_update().first()

    if "amount" in updates:
        other_payments_total = sum(
            (p.amount for p in order.payments if p.id != payment.id), Decimal("0")
        )
        prospective_total = (order.advance or Decimal("0")) + other_payments_total + updates["amount"]
        if prospective_total > (order.order_value or Decimal("0")):
            raise HTTPException(
                status_code=400,
                detail=f"Changing this payment to Rs {updates['amount']} would bring total received to "
                       f"Rs {prospective_total}, which exceeds the order value of Rs {order.order_value}.",
            )

    old_value = serializable_fields(payment, updates.keys())
    for field, value in updates.items():
        setattr(payment, field, value)
    db.add(payment)
    order.recompute_totals()
    db.add(order)
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
    # Locked before mutating, same as record_payment/update_payment -
    # a concurrent create/update against the same order must always
    # see this deletion's effect or be blocked until it commits, never
    # interleave with it.
    order = db.query(Order).filter(Order.id == payment.order_id).with_for_update().first()
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
        storage_ref = backend.save(stored_filename, b"".join(chunks))
    except HTTPException:
        raise
    except Exception:
        raise HTTPException(status_code=500, detail="Failed to save the uploaded file.")

    document = PaymentDocument(
        payment_id=payment_id, original_filename=original_name, stored_filename=stored_filename,
        content_type=file.content_type, description=description, uploaded_by=str(auth.get("user_id", "")),
        storage_backend=storage_ref.backend, drive_file_id=storage_ref.drive_file_id,
    )
    db.add(document)
    try:
        db.commit()
    except Exception:
        db.rollback()
        try:
            backend.delete(storage_ref)
        except Exception:
            pass
        raise HTTPException(status_code=500, detail="Failed to save the document record.")
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
    backend, storage_ref = get_storage_backend_for_record(document)
    if not backend.exists(storage_ref):
        raise HTTPException(status_code=404, detail="The stored file could not be found.")
    file_bytes = backend.read(storage_ref)
    return Response(
        content=file_bytes, media_type=document.content_type or "application/octet-stream",
        headers={
            "Cache-Control": "no-store, private",
            "Content-Disposition": f'attachment; filename="{document.original_filename}"',
        },
    )


@router.delete("/{payment_id}/documents/{document_id}", status_code=204)
def delete_payment_document(payment_id: int, document_id: int, request: Request, db: Session = Depends(get_db),
                             auth=Depends(require_role("master"))):
    document = db.query(PaymentDocument).filter(
        PaymentDocument.id == document_id, PaymentDocument.payment_id == payment_id,
    ).first()
    if not document:
        raise HTTPException(status_code=404, detail="Document not found")
    backend, storage_ref = get_storage_backend_for_record(document)
    old_value = {"payment_id": payment_id, "filename": document.original_filename}
    db.delete(document)
    try:
        db.commit()
    except Exception:
        db.rollback()
        raise HTTPException(status_code=500, detail="Failed to delete the document record.")
    try:
        backend.delete(storage_ref)
    except Exception:
        logger.error(f"Orphaned file after payment document {document_id} delete: {storage_ref}")
    log_action(db, request, user_id=auth.get("user_id"), action="delete_payment_document", module_name="payments",
               record_id=document_id, old_value=old_value)
