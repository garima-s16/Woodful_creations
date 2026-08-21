"""Keeps Material.current_stock / total_purchased / total_issued consistent
with the Purchase and Issue registers. All writes go through here rather
than routes touching Material directly, so stock can never drift from its
transaction history."""
from decimal import Decimal, ROUND_HALF_UP
from typing import Optional

from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.models.material import Material
from app.models.purchase import Purchase
from app.models.issue import Issue
from app.models.location import Location
from app.models.stock_transaction import StockTransfer, StockAdjustment
from app.models.stock_ledger_entry import StockLedgerEntry
from app.models.supplier_material import SupplierMaterial
from app.services.notification_service import NotificationService
from app.schemas.purchase import PurchaseCreate
from app.schemas.issue import IssueCreate
from app.schemas.stock_transaction import StockTransferCreate, StockAdjustmentCreate
from app.utils.id_generator import generate_unique_code, generate_business_id


class StockService:

    @staticmethod
    def _apply_stock_receipt(db: Session, material: Material, quantity: Decimal, rate: Decimal, supplier_id: int = None, material_id_for_link: int = None, reference_id: int = None, location_id: int = None):
        """The actual stock-increase math, shared by record_purchase
        (when goods are received immediately, the default and existing
        behavior) and mark_purchase_received (when a purchase was
        recorded as Ordered and goods arrive later) - one implementation,
        so the weighted-average-rate calculation can't drift between the
        two call sites. Also writes the permanent ledger entry for this
        receipt - reference_id links it back to the actual Purchase row.

        location_id records WHERE the stock landed (falls back to the
        material's own primary location_id when not given, so unlocated
        materials/receipts behave exactly as before). If the material had
        no primary location yet, the first receipt's location becomes it -
        a material's location_id then stays a genuine "primary/most
        recent" location for the existing single-location consumers,
        while the ledger keeps the full per-location breakdown."""
        resolved_location_id = location_id or material.location_id
        if resolved_location_id and not material.location_id:
            loc = db.query(Location).filter(Location.id == resolved_location_id).first()
            if loc:
                material.location_id = loc.id
                material.location = loc.full_path

        material.total_purchased = (material.total_purchased or 0) + quantity
        material.current_stock = (material.current_stock or 0) + quantity
        prior_value = Decimal(str(material.average_rate or 0)) * Decimal(str((material.current_stock or 0) - quantity))
        new_value = prior_value + (quantity * rate)
        if material.current_stock:
            material.average_rate = (new_value / Decimal(str(material.current_stock))).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
        db.add(material)
        db.add(StockLedgerEntry(
            material_id=material.id, entry_type="Receipt", quantity_delta=quantity,
            balance_after=material.current_stock, reference_type="purchase", reference_id=reference_id,
            location_id=resolved_location_id,
        ))

        if supplier_id and material_id_for_link:
            link = db.query(SupplierMaterial).filter(
                SupplierMaterial.supplier_id == supplier_id, SupplierMaterial.material_id == material_id_for_link
            ).first()
            if link:
                link.last_purchase_price = rate
                db.add(link)

    @staticmethod
    def record_purchase(db: Session, data: PurchaseCreate) -> Purchase:
        material = db.query(Material).filter(Material.id == data.material_id).first()
        if not material:
            raise HTTPException(status_code=404, detail="Material not found")

        purchase_code = generate_unique_code(db, Purchase, "purchase_code", "PUR-")

        taxable_value = (data.quantity * data.rate).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
        gst_amount = (taxable_value * data.gst_percent / Decimal("100")).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
        invoice_total = taxable_value + gst_amount

        purchase = Purchase(
            purchase_code=purchase_code, business_id=generate_business_id(db), date=data.date,
            expected_delivery_date=data.expected_delivery_date, supplier_id=data.supplier_id,
            material_id=data.material_id, quantity=data.quantity, unit=data.unit, rate=data.rate,
            taxable_value=taxable_value, gst_percent=data.gst_percent, gst_amount=gst_amount,
            invoice_total=invoice_total, payment_status=data.payment_status,
            receipt_status=data.receipt_status, location_id=data.location_id,
            quantity_received=data.quantity if data.receipt_status != "Ordered" else Decimal("0"),
        )
        db.add(purchase)
        db.flush()  # assigns purchase.id without committing, needed as the ledger entry's reference_id below

        # "Ordered" means the supplier has been asked for stock that
        # hasn't arrived yet - the material must stay completely
        # untouched until it's explicitly marked received (see
        # mark_purchase_received). "Received" (the default, and the
        # only option that previously existed) increases stock now,
        # exactly as before - existing callers that don't set
        # receipt_status keep their current behavior unchanged.
        if data.receipt_status != "Ordered":
            StockService._apply_stock_receipt(db, material, data.quantity, data.rate, data.supplier_id, data.material_id, reference_id=purchase.id, location_id=data.location_id)
        db.commit()
        db.refresh(purchase)
        if data.receipt_status != "Ordered":
            NotificationService.notify_purchase_received(db, purchase)
        return purchase

    @staticmethod
    def record_issue(db: Session, data: IssueCreate) -> Issue:
        material = db.query(Material).filter(Material.id == data.material_id).first()
        if not material:
            raise HTTPException(status_code=404, detail="Material not found")

        issue_code = generate_unique_code(db, Issue, "issue_code", "ISS-")

        if data.quantity_issued > (material.current_stock or 0):
            raise HTTPException(
                status_code=400,
                detail=f"Cannot issue {data.quantity_issued} {data.unit} - only {material.current_stock} in stock",
            )

        resolved_location_id = data.location_id or material.location_id
        if data.location_id:
            # A location was explicitly requested - it must actually have
            # enough stock, not just the material overall (a material can
            # be split across racks; issuing from an empty rack while
            # another rack is full must be rejected even though the
            # material-wide total would cover it).
            location_balance = StockService._location_balance(db, material.id, resolved_location_id)
            if data.quantity_issued > location_balance:
                raise HTTPException(
                    status_code=400,
                    detail=f"Cannot issue {data.quantity_issued} {data.unit} from that location - only {location_balance} available there",
                )

        issue = Issue(
            issue_code=issue_code, date=data.date, order_id=data.order_id,
            material_id=data.material_id, quantity_issued=data.quantity_issued, unit=data.unit,
            issued_to=data.issued_to, department=data.department, purpose=data.purpose,
            approved_by=data.approved_by, remarks=data.remarks, location_id=data.location_id,
        )
        db.add(issue)
        db.flush()  # assigns issue.id without committing, needed as the ledger entry's reference_id below

        material.total_issued = (material.total_issued or 0) + data.quantity_issued
        material.current_stock = (material.current_stock or 0) - data.quantity_issued
        db.add(material)
        db.add(StockLedgerEntry(
            material_id=material.id, entry_type="Issue", quantity_delta=-data.quantity_issued,
            balance_after=material.current_stock, reference_type="issue", reference_id=issue.id,
            location_id=resolved_location_id,
        ))

        db.commit()
        db.refresh(issue)
        return issue

    @staticmethod
    def record_transfer(db: Session, data: StockTransferCreate) -> StockTransfer:
        """Logs a location move and updates Material's single
        location_id/location fields - not a second stock-by-location
        number (see the model's own docstring for why)."""
        material = db.query(Material).filter(Material.id == data.material_id).first()
        if not material:
            raise HTTPException(status_code=404, detail="Material not found")
        to_location = db.query(Location).filter(Location.id == data.to_location_id).first()
        if not to_location:
            raise HTTPException(status_code=404, detail="Destination location not found")
        if data.quantity <= 0:
            raise HTTPException(status_code=400, detail="Transfer quantity must be positive")
        if data.quantity > (material.current_stock or 0):
            raise HTTPException(
                status_code=400,
                detail=f"Cannot transfer {data.quantity} {material.unit} - only {material.current_stock} in stock.",
            )

        from_location_id = data.from_location_id or material.location_id
        if from_location_id:
            from_balance = StockService._location_balance(db, material.id, from_location_id)
            if data.quantity > from_balance:
                raise HTTPException(
                    status_code=400,
                    detail=f"Cannot transfer {data.quantity} {material.unit} - only {from_balance} at the source location.",
                )

        transfer = StockTransfer(
            material_id=data.material_id, quantity=data.quantity, from_location_id=from_location_id,
            to_location_id=data.to_location_id, transferred_by=data.transferred_by, remarks=data.remarks,
            business_id=generate_business_id(db),
        )
        db.add(transfer)
        db.flush()  # assigns transfer.id, needed as the ledger entries' reference_id below

        # Total material-wide stock never changes on a transfer - only
        # WHERE it sits. Two ledger entries whose quantity_delta sums to
        # zero (a decrease at from_location, an increase at to_location)
        # keep verify_stock_matches_ledger's material-wide reconciliation
        # untouched while still letting per-location balances be derived
        # from the ledger, same as receipts/issues/adjustments.
        # Always write the "from" entry, even when from_location_id is
        # None (a material with no location history yet) - its balance
        # must still be debited from wherever the ledger currently
        # attributes that stock (the "Unassigned" bucket), or the
        # per-location total would stop summing to the material-wide total.
        db.add(StockLedgerEntry(
            material_id=material.id, entry_type="Transfer", quantity_delta=-data.quantity,
            balance_after=material.current_stock, reference_type="stock_transfer", reference_id=transfer.id,
            location_id=from_location_id, remarks=f"Transferred to {to_location.full_path}",
        ))
        db.add(StockLedgerEntry(
            material_id=material.id, entry_type="Transfer", quantity_delta=data.quantity,
            balance_after=material.current_stock, reference_type="stock_transfer", reference_id=transfer.id,
            location_id=data.to_location_id, remarks=f"Transferred from {from_location_id or 'unassigned'}",
        ))

        # material.location_id/location keep meaning "primary/most recent
        # location" for the existing single-location consumers (dashboard,
        # PDF, chatbot) - unchanged behavior, now backed by real
        # per-location detail in the ledger for anything that wants it.
        material.location_id = data.to_location_id
        material.location = to_location.full_path
        db.add(material)

        db.commit()
        db.refresh(transfer)
        return transfer

    @staticmethod
    def record_adjustment(db: Session, data: StockAdjustmentCreate) -> StockAdjustment:
        """Every change to current_stock outside a purchase/issue must
        go through here - never a silent direct edit. Records the exact
        before/after so the adjustment is fully auditable, and rejects
        anything that would push stock negative. "Return from Issue" is
        validated against the actual originating Issue - the returned
        quantity can never exceed what was genuinely issued minus what's
        already been returned against it, so a return can't become a
        disguised arbitrary quantity increase."""
        material = db.query(Material).filter(Material.id == data.material_id).first()
        if not material:
            raise HTTPException(status_code=404, detail="Material not found")
        if data.quantity_delta == 0:
            raise HTTPException(status_code=400, detail="Adjustment quantity cannot be zero")

        if data.adjustment_type == "Return from Issue":
            if not data.related_issue_id:
                raise HTTPException(status_code=400, detail="A return must reference the issue it's returning material against.")
            if data.quantity_delta <= 0:
                raise HTTPException(status_code=400, detail="A return must increase stock (a positive quantity).")
            issue = db.query(Issue).filter(Issue.id == data.related_issue_id).first()
            if not issue:
                raise HTTPException(status_code=404, detail="The referenced issue was not found.")
            if issue.material_id != data.material_id:
                raise HTTPException(status_code=400, detail="The referenced issue is for a different material.")
            already_returned = db.query(StockAdjustment).filter(
                StockAdjustment.related_issue_id == data.related_issue_id,
            ).with_entities(StockAdjustment.quantity_delta).all()
            already_returned_total = sum((r[0] for r in already_returned), Decimal("0"))
            remaining = (issue.quantity_issued or Decimal("0")) - already_returned_total
            if data.quantity_delta > remaining:
                raise HTTPException(
                    status_code=400,
                    detail=f"Cannot return {data.quantity_delta} {material.unit} - only {remaining} {material.unit} "
                           f"from this issue remains un-returned.",
                )

        stock_before = material.current_stock or 0
        stock_after = stock_before + data.quantity_delta
        if stock_after < 0:
            raise HTTPException(
                status_code=400,
                detail=f"This adjustment would take stock negative ({stock_before} {data.quantity_delta:+} = {stock_after}).",
            )

        resolved_location_id = data.location_id or material.location_id
        if data.location_id and data.quantity_delta < 0:
            # A decrease at a specific location must not take that
            # location's own balance negative, even if the material-wide
            # total has room (stock at other locations doesn't help here).
            location_balance = StockService._location_balance(db, material.id, resolved_location_id)
            if -data.quantity_delta > location_balance:
                raise HTTPException(
                    status_code=400,
                    detail=f"This adjustment would take that location's stock negative - only {location_balance} recorded there.",
                )

        adjustment = StockAdjustment(
            material_id=data.material_id, adjustment_type=data.adjustment_type,
            related_issue_id=data.related_issue_id,
            quantity_delta=data.quantity_delta, stock_before=stock_before, stock_after=stock_after,
            reason=data.reason, adjusted_by=data.adjusted_by, business_id=generate_business_id(db),
            location_id=data.location_id,
        )
        db.add(adjustment)
        db.flush()  # assigns adjustment.id without committing, needed as the ledger entry's reference_id below

        material.current_stock = stock_after
        db.add(StockLedgerEntry(
            material_id=material.id, entry_type="Adjustment", quantity_delta=data.quantity_delta,
            balance_after=stock_after, reference_type="stock_adjustment", reference_id=adjustment.id,
            remarks=data.reason, location_id=resolved_location_id,
        ))
        db.add(material)

        db.commit()
        db.refresh(adjustment)
        return adjustment

    @staticmethod
    def mark_purchase_received(db: Session, purchase_id: int, quantity_to_receive: Optional[Decimal] = None, location_id: Optional[int] = None) -> Purchase:
        """Transitions a purchase toward Received - the point stock
        actually increases. Supports genuine partial receipts:
        quantity_to_receive defaults to everything still outstanding
        (the original all-or-nothing behavior, unchanged for existing
        callers), but a smaller amount can be passed to receive only
        part of the order. Stock is applied only for the incremental
        amount each call - never the full purchase.quantity again -
        so receiving in two steps can never double-count. Rejects
        anything already fully Received, and rejects receiving more
        than genuinely remains outstanding (the quantity-integrity
        check this feature exists for)."""
        purchase = db.query(Purchase).filter(Purchase.id == purchase_id).first()
        if not purchase:
            raise HTTPException(status_code=404, detail="Purchase not found")
        if purchase.receipt_status == "Received":
            raise HTTPException(status_code=400, detail="This purchase has already been received.")

        remaining = (purchase.quantity or Decimal("0")) - (purchase.quantity_received or Decimal("0"))
        if quantity_to_receive is None:
            quantity_to_receive = remaining
        if quantity_to_receive <= 0:
            raise HTTPException(status_code=400, detail="Quantity to receive must be positive.")
        if quantity_to_receive > remaining:
            raise HTTPException(
                status_code=400,
                detail=f"Cannot receive {quantity_to_receive} {purchase.unit} - only {remaining} {purchase.unit} remains outstanding on this purchase.",
            )

        material = db.query(Material).filter(Material.id == purchase.material_id).first()
        if not material:
            raise HTTPException(status_code=404, detail="Material not found")

        receive_location_id = location_id or purchase.location_id
        StockService._apply_stock_receipt(db, material, quantity_to_receive, purchase.rate, purchase.supplier_id, purchase.material_id, reference_id=purchase.id, location_id=receive_location_id)
        purchase.quantity_received = (purchase.quantity_received or Decimal("0")) + quantity_to_receive
        purchase.receipt_status = "Received" if purchase.quantity_received >= purchase.quantity else "Partially Received"
        if receive_location_id and not purchase.location_id:
            purchase.location_id = receive_location_id
        db.add(purchase)
        db.commit()
        db.refresh(purchase)
        NotificationService.notify_purchase_received(db, purchase)
        return purchase

    @staticmethod
    def verify_stock_matches_ledger(db: Session, material_id: int) -> dict:
        """Proves (or disproves) that Material.current_stock genuinely
        equals opening_stock + every ledger entry ever recorded for
        this material - the actual verification the "ledger is the
        source of truth" requirement depends on, not just a claim that
        a ledger exists alongside current_stock. Returns a dict rather
        than raising, so this can be used both as a route response and
        directly in tests without needing to catch an exception."""
        material = db.query(Material).filter(Material.id == material_id).first()
        if not material:
            raise HTTPException(status_code=404, detail="Material not found")
        entries = db.query(StockLedgerEntry).filter(StockLedgerEntry.material_id == material_id).all()
        ledger_sum = sum((e.quantity_delta for e in entries), Decimal("0"))
        computed_stock = (material.opening_stock or Decimal("0")) + ledger_sum
        current_stock = material.current_stock or Decimal("0")
        return {
            "material_id": material_id, "matches": computed_stock == current_stock,
            "current_stock": current_stock, "computed_stock": computed_stock,
            "opening_stock": material.opening_stock or Decimal("0"), "ledger_entry_count": len(entries),
        }

    @staticmethod
    def _location_balance(db: Session, material_id: int, location_id: Optional[int]) -> Decimal:
        """The derived balance for one material at one location - the
        ledger entries for that (material_id, location_id) pair, summed,
        plus opening_stock if this is the material's own primary location
        (opening_stock predates the ledger, so it must count here too or
        a location-specific check could wrongly reject a valid issue/
        transfer/adjustment against genuinely available opening stock).
        Never a stored number; always computed on read - same rule
        get_location_balances follows for the full breakdown."""
        material = db.query(Material).filter(Material.id == material_id).first()
        entries = db.query(StockLedgerEntry.quantity_delta).filter(
            StockLedgerEntry.material_id == material_id, StockLedgerEntry.location_id == location_id,
        ).all()
        balance = sum((e[0] for e in entries), Decimal("0"))
        if material and material.location_id == location_id:
            balance += material.opening_stock or Decimal("0")
        return balance

    @staticmethod
    def get_location_balances(db: Session, material_id: int) -> dict:
        """The genuine per-location breakdown of a material's stock,
        derived entirely from the ledger - e.g. HDHMR 18mm: Rack A2 -> 12,
        Rack B1 -> 6, Total -> 18. Never a second, independently edited
        stock number: this is StockLedgerEntry.quantity_delta grouped by
        location_id, nothing else. Old ledger rows written before
        multi-location support existed have location_id = NULL; they're
        attributed to the material's own (single) location_id so historic
        stock isn't silently dropped from the total, and the remainder
        (if the material never had a location either) falls into an
        explicit "Unassigned" bucket rather than vanishing."""
        material = db.query(Material).filter(Material.id == material_id).first()
        if not material:
            raise HTTPException(status_code=404, detail="Material not found")

        entries = db.query(StockLedgerEntry).filter(StockLedgerEntry.material_id == material_id).all()
        balances: dict[Optional[int], Decimal] = {}
        # opening_stock predates the ledger (it's the material's baseline,
        # not itself a ledger entry) but must still be included or the
        # location breakdown would under-count the material-wide total -
        # attribute it to the material's own primary location, same
        # fallback used for pre-multi-location ledger rows below.
        opening = material.opening_stock or Decimal("0")
        if opening:
            balances[material.location_id] = balances.get(material.location_id, Decimal("0")) + opening
        for entry in entries:
            key = entry.location_id or material.location_id  # backfill pre-multi-location rows
            balances[key] = balances.get(key, Decimal("0")) + entry.quantity_delta

        location_ids = [loc_id for loc_id in balances.keys() if loc_id is not None]
        locations_by_id = {}
        if location_ids:
            for loc in db.query(Location).filter(Location.id.in_(location_ids)).all():
                locations_by_id[loc.id] = loc

        rows = []
        for loc_id, qty in balances.items():
            if qty == 0:
                continue  # a location that's been fully drawn down/transferred out has nothing to show
            loc = locations_by_id.get(loc_id) if loc_id else None
            rows.append({
                "location_id": loc_id,
                "location_name": loc.full_path if loc else "Unassigned",
                "quantity": qty,
            })
        rows.sort(key=lambda r: r["location_name"])

        return {
            "material_id": material.id, "material_name": material.name, "unit": material.unit,
            "total": material.current_stock or Decimal("0"), "locations": rows,
        }
