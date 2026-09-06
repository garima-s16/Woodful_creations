"""Keeps Material.current_stock / total_purchased / total_issued consistent
with the Purchase and Issue registers. All writes go through here rather
than routes touching Material directly, so stock can never drift from its
transaction history."""
from decimal import Decimal, ROUND_HALF_UP
from typing import Optional

from fastapi import HTTPException
from sqlalchemy.orm import Session, selectinload

from app.modules.inventory.models import Material
from app.modules.procurement.models import Purchase
from app.modules.operations.models import Issue
from app.modules.inventory.models import Location, StockTransfer, StockAdjustment, StockLedgerEntry
from app.modules.procurement.models import SupplierMaterial
from app.modules.operations.schemas import IssueCreate
from app.modules.inventory.schemas import StockTransferCreate, StockAdjustmentCreate
from app.platform.database.id_generator import generate_unique_code, generate_business_id

# Cross-module: order/product/BOM live in sales/catalog, but shortage
# calculation is authoritative here (inventory owns current_stock) -
# same established pattern as the Issue import above (operations).
from app.modules.sales.models import Order, OrderItem
from app.modules.catalog.models import ProductMaterial

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
    def record_issue(db: Session, data: IssueCreate) -> Issue:
        material = db.query(Material).filter(Material.id == data.material_id).with_for_update().first()
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
            rate_at_issue=material.average_rate,
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
        material = db.query(Material).filter(Material.id == data.material_id).with_for_update().first()
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
        if from_location_id == data.to_location_id:
            # A transfer has no business meaning when the source and
            # destination are the same location - net stock movement is
            # zero, but recording it anyway would still create two
            # offsetting ledger rows that look like real activity.
            raise HTTPException(
                status_code=400, detail="Source and destination location cannot be the same.",
            )
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
        material = db.query(Material).filter(Material.id == data.material_id).with_for_update().first()
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
        plus opening_stock if this location is where the opening stock
        was originally recorded (opening_stock predates the ledger, so
        it must count here too or a location-specific check could
        wrongly reject a valid issue/transfer/adjustment against
        genuinely available opening stock). Never a stored number;
        always computed on read - same rule get_location_balances
        follows for the full breakdown.

        Every ledger entry's location_id is a fixed fact about that row
        (see migration 0061, which backfilled legacy pre-multi-location
        rows once) - it is matched exactly here, never re-derived from
        the material's current (mutable) primary location, so a later
        change to Material.location_id can't retroactively move where
        old entries appear to belong."""
        material = db.query(Material).filter(Material.id == material_id).first()
        query = db.query(StockLedgerEntry.quantity_delta).filter(
            StockLedgerEntry.material_id == material_id, StockLedgerEntry.location_id == location_id,
        )
        balance = sum((e[0] for e in query.all()), Decimal("0"))
        opening_location_id = material.opening_stock_location_id if material else None
        if material and opening_location_id == location_id:
            balance += material.opening_stock or Decimal("0")
        return balance

    @staticmethod
    def get_location_balances(db: Session, material_id: int) -> dict:
        """The genuine per-location breakdown of a material's stock,
        derived entirely from the ledger - e.g. HDHMR 18mm: Rack A2 -> 12,
        Rack B1 -> 6, Total -> 18. Never a second, independently edited
        stock number: this is StockLedgerEntry.quantity_delta grouped by
        location_id, nothing else.

        Each entry's location_id is used exactly as stored - never
        re-derived from the material's current primary location, so a
        material being relocated later can't retroactively move where
        old stock appears to have been. Old ledger rows written before
        multi-location support existed were backfilled once, in
        migration 0061, onto whatever the material's location was at
        that time; a material that never had any location keeps
        location_id = NULL on those rows, shown as an explicit
        "Unassigned" bucket rather than a fabricated one."""
        material = db.query(Material).filter(Material.id == material_id).first()
        if not material:
            raise HTTPException(status_code=404, detail="Material not found")

        entries = db.query(StockLedgerEntry).filter(StockLedgerEntry.material_id == material_id).all()
        balances: dict[Optional[int], Decimal] = {}
        # opening_stock predates the ledger (it's the material's baseline,
        # not itself a ledger entry) but must still be included or the
        # location breakdown would under-count the material-wide total -
        # attributed to wherever it was originally recorded
        # (opening_stock_location_id), not the material's current
        # primary location, for the same reason as ledger entries above.
        opening = material.opening_stock or Decimal("0")
        if opening:
            key = material.opening_stock_location_id
            balances[key] = balances.get(key, Decimal("0")) + opening
        for entry in entries:
            balances[entry.location_id] = balances.get(entry.location_id, Decimal("0")) + entry.quantity_delta

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

    @staticmethod
    def calculate_reserved_stock(db: Session, material_ids: list, exclude_order_id: int = None) -> dict:
        """Reserved Qty (spec section 9.2/5.4): unfulfilled BOM demand
        for the given materials across every still-open order
        (project_status not in "Completed"/"Cancelled" - the two
        terminal states where a material's demand no longer counts
        against future planning). "Unfulfilled" means the order's own
        BOM requirement for that material, minus whatever has already
        actually been issued against that same order+material pair -
        an order that's already had its materials issued no longer
        reserves anything further for them.

        Computed fresh every call, not a stored column - this can
        never silently drift out of sync the way a stored reservation
        record could (nothing to release on order cancellation/
        completion; the exclusion above already handles that).

        exclude_order_id: when checking "how much of this material is
        reserved by OTHER orders" for a specific order's own shortage
        calculation, that order's own demand must not double-count
        against itself.

        Returns {material_id: reserved_quantity}; a material with no
        open-order demand is simply absent from the dict (treat a
        missing key as zero).
        """
        if not material_ids:
            return {}

        orders_query = db.query(Order.id).filter(Order.project_status.notin_(["Completed", "Cancelled"]))
        if exclude_order_id is not None:
            orders_query = orders_query.filter(Order.id != exclude_order_id)
        open_order_ids = [row[0] for row in orders_query.all()]
        if not open_order_ids:
            return {}

        items = (
            db.query(OrderItem)
            .filter(OrderItem.order_id.in_(open_order_ids), OrderItem.product_id.isnot(None))
            .all()
        )
        product_ids = list({item.product_id for item in items})
        if not product_ids:
            return {}

        bom_rows = (
            db.query(ProductMaterial)
            .filter(ProductMaterial.product_id.in_(product_ids), ProductMaterial.material_id.in_(material_ids))
            .all()
        )
        bom_by_product: dict = {}
        for row in bom_rows:
            bom_by_product.setdefault(row.product_id, []).append(row)
        if not bom_by_product:
            return {}

        required_by_order_material: dict = {}
        for item in items:
            for bom_line in bom_by_product.get(item.product_id, []):
                key = (item.order_id, bom_line.material_id)
                needed = Decimal(str(item.quantity)) * bom_line.quantity_required
                required_by_order_material[key] = required_by_order_material.get(key, Decimal("0")) + needed

        issued_rows = (
            db.query(Issue.order_id, Issue.material_id, Issue.quantity_issued)
            .filter(Issue.order_id.in_(open_order_ids), Issue.material_id.in_(material_ids))
            .all()
        )
        issued_by_order_material: dict = {}
        for order_id, material_id, quantity_issued in issued_rows:
            key = (order_id, material_id)
            issued_by_order_material[key] = issued_by_order_material.get(key, Decimal("0")) + quantity_issued

        reserved_by_material: dict = {}
        for (order_id, material_id), required in required_by_order_material.items():
            issued = issued_by_order_material.get((order_id, material_id), Decimal("0"))
            unfulfilled = max(Decimal("0"), required - issued)
            if unfulfilled > 0:
                reserved_by_material[material_id] = reserved_by_material.get(material_id, Decimal("0")) + unfulfilled

        return reserved_by_material

    @staticmethod
    def calculate_order_material_requirements(db: Session, order_id: int) -> dict:
        """Material Requirement + Shortage Intelligence (Phase B, section
        9.3): for every ordered Product with a BOM (ProductMaterial),
        multiply quantity_required by the ordered quantity to get real
        material demand, then compare against current_stock and any
        purchase already placed but not yet received (Purchase rows
        with receipt_status != "Received" for the same material).

        Formula per spec: Shortage = max(0, Required - Available -
        Relevant Pending Supply), where Available = Current Stock -
        Reserved Qty (this order excluded from the reservation count -
        see calculate_reserved_stock). Worked example: 5 sheets
        required, 2 available, 1 already-pending purchase -> shortage
        2 (not 3; the pending purchase is netted directly into the
        shortage figure, not applied as a separate later adjustment).
        gap_before_pending_supply (required - available, before netting
        pending) is kept alongside it purely for explanation/
        traceability, not as the number to act on.

        Every number here traces to a real row - no estimate, no
        forecast. Reserved Qty is computed fresh from every other open
        order's own unfulfilled BOM demand (see
        calculate_reserved_stock), not a stored field - matching the
        client reference's Reserved Qty/Available Qty concept (see
        docs/ARCHITECTURE.md) without the drift risk of a stored
        reservation record.
        """
        order = db.query(Order).filter(Order.id == order_id).first()
        if not order:
            raise HTTPException(status_code=404, detail="Order not found")

        items = (
            db.query(OrderItem)
            .filter(OrderItem.order_id == order_id, OrderItem.product_id.isnot(None))
            .all()
        )
        product_ids = list({item.product_id for item in items})
        if not product_ids:
            return {"order_id": order_id, "materials": []}

        bom_rows = db.query(ProductMaterial).filter(ProductMaterial.product_id.in_(product_ids)).all()
        bom_by_product = {}
        for row in bom_rows:
            bom_by_product.setdefault(row.product_id, []).append(row)

        required_by_material: dict = {}
        for item in items:
            for bom_line in bom_by_product.get(item.product_id, []):
                needed = Decimal(str(item.quantity)) * bom_line.quantity_required
                required_by_material[bom_line.material_id] = (
                    required_by_material.get(bom_line.material_id, Decimal("0")) + needed
                )

        if not required_by_material:
            return {"order_id": order_id, "materials": []}

        material_ids = list(required_by_material.keys())
        materials_by_id = {m.id: m for m in db.query(Material).filter(Material.id.in_(material_ids)).all()}

        pending_purchases = (
            db.query(Purchase)
            .filter(Purchase.material_id.in_(material_ids), Purchase.receipt_status != "Received")
            .all()
        )
        pending_by_material: dict = {}
        for p in pending_purchases:
            pending_by_material[p.material_id] = pending_by_material.get(p.material_id, Decimal("0")) + p.quantity

        # What OTHER open orders have already claimed against this same
        # stock - this order's own demand must not double-count against
        # itself, hence exclude_order_id.
        reserved_by_material = StockService.calculate_reserved_stock(db, material_ids, exclude_order_id=order_id)

        results = []
        for material_id, required in required_by_material.items():
            material = materials_by_id.get(material_id)
            if not material:
                continue
            reserved_by_others = reserved_by_material.get(material_id, Decimal("0"))
            available = max(Decimal("0"), (material.current_stock or Decimal("0")) - reserved_by_others)
            pending = pending_by_material.get(material_id, Decimal("0"))
            # Formula per spec section 9.3: Shortage = max(0, Required -
            # Available - Relevant Pending Supply). "Relevant" here means
            # already scoped to this exact material_id (not a blind
            # subtraction across unrelated purchases) and to receipt_status
            # != "Received" (an already-received purchase is already
            # inside current_stock, not still "pending").
            shortage = max(Decimal("0"), required - available - pending)
            # Kept for traceability/explanation (spec: "explain
            # recommendation inputs") - the raw gap before pending supply
            # is netted in, so a user can see *why* the shortage is lower
            # than a naive required-minus-available would suggest.
            gap_before_pending = max(Decimal("0"), required - available)
            results.append({
                "material_id": material.id, "material_name": material.name, "unit": material.unit,
                "required": required, "available": available,
                "reserved_by_other_orders": reserved_by_others,
                "gap_before_pending_supply": gap_before_pending,
                "pending_purchase_quantity": pending,
                "shortage": shortage,
                "recommended_purchase_quantity": shortage,
            })
        results.sort(key=lambda r: r["shortage"], reverse=True)

        shortage_material_ids = [r["material_id"] for r in results if r["shortage"] > 0]
        from app.modules.procurement.services import ProcurementService
        supplier_options = ProcurementService._supplier_options_for_materials(db, shortage_material_ids)
        for row in results:
            row["supplier_options"] = supplier_options.get(row["material_id"], [])

        return {"order_id": order_id, "materials": results}

    @staticmethod
    def calculate_at_risk_orders(db: Session) -> list:
        """Business-wide version of calculate_order_material_requirements -
        which open orders have a real, current material shortage, computed
        once across the whole open-order book rather than by looping the
        per-order function (which would be its own N+1 at this scale: ~9
        queries per order). Same formula, same semantics, same source
        data - this only changes where the reserved-by-other-orders
        subtraction comes from (derived from a business-wide total
        already in memory instead of a second per-order query); it is
        not a second, independent way of computing a shortage that
        could drift from the per-order figure used elsewhere.

        Returns one entry per at-risk order (shortage > 0 on at least
        one material), sorted so the most materially at-risk order
        (highest total shortage across its materials) is first. Each
        order's materials list uses the same field names
        calculate_order_material_requirements returns, so a dashboard
        card and the order detail page can share one frontend
        rendering path.
        """
        open_orders = (
            db.query(Order)
            .options(selectinload(Order.client))
            .filter(Order.project_status.notin_(["Completed", "Cancelled"]))
            .all()
        )
        if not open_orders:
            return []
        orders_by_id = {o.id: o for o in open_orders}
        open_order_ids = list(orders_by_id.keys())

        items = (
            db.query(OrderItem)
            .filter(OrderItem.order_id.in_(open_order_ids), OrderItem.product_id.isnot(None))
            .all()
        )
        product_ids = list({item.product_id for item in items})
        if not product_ids:
            return []

        bom_rows = db.query(ProductMaterial).filter(ProductMaterial.product_id.in_(product_ids)).all()
        bom_by_product: dict = {}
        for row in bom_rows:
            bom_by_product.setdefault(row.product_id, []).append(row)
        if not bom_by_product:
            return []

        # required(order, material) - identical multiplication the
        # per-order function uses, just keyed by order this time
        # instead of scoped to a single order.
        required_by_order_material: dict = {}
        for item in items:
            for bom_line in bom_by_product.get(item.product_id, []):
                key = (item.order_id, bom_line.material_id)
                needed = Decimal(str(item.quantity)) * bom_line.quantity_required
                required_by_order_material[key] = required_by_order_material.get(key, Decimal("0")) + needed
        if not required_by_order_material:
            return []

        material_ids = list({key[1] for key in required_by_order_material})

        issued_rows = (
            db.query(Issue.order_id, Issue.material_id, Issue.quantity_issued)
            .filter(Issue.order_id.in_(open_order_ids), Issue.material_id.in_(material_ids))
            .all()
        )
        issued_by_order_material: dict = {}
        for order_id, material_id, quantity_issued in issued_rows:
            key = (order_id, material_id)
            issued_by_order_material[key] = issued_by_order_material.get(key, Decimal("0")) + quantity_issued

        # unfulfilled(order, material) = max(0, required - issued) - this
        # order's own still-outstanding claim. Summing it across every
        # open order for one material, then subtracting one order's own
        # share, gives exactly what calculate_reserved_stock computes
        # per-order via a second query - derived here from rows already
        # in memory instead of queried again.
        unfulfilled_by_order_material: dict = {}
        total_unfulfilled_by_material: dict = {}
        for key, required in required_by_order_material.items():
            issued = issued_by_order_material.get(key, Decimal("0"))
            unfulfilled = max(Decimal("0"), required - issued)
            unfulfilled_by_order_material[key] = unfulfilled
            material_id = key[1]
            total_unfulfilled_by_material[material_id] = (
                total_unfulfilled_by_material.get(material_id, Decimal("0")) + unfulfilled
            )

        materials_by_id = {m.id: m for m in db.query(Material).filter(Material.id.in_(material_ids)).all()}

        pending_purchases = (
            db.query(Purchase)
            .filter(Purchase.material_id.in_(material_ids), Purchase.receipt_status != "Received")
            .all()
        )
        pending_by_material: dict = {}
        for p in pending_purchases:
            pending_by_material[p.material_id] = pending_by_material.get(p.material_id, Decimal("0")) + p.quantity

        at_risk: dict = {}
        for (order_id, material_id), required in required_by_order_material.items():
            material = materials_by_id.get(material_id)
            if not material:
                continue
            this_order_unfulfilled = unfulfilled_by_order_material.get((order_id, material_id), Decimal("0"))
            reserved_by_others = total_unfulfilled_by_material.get(material_id, Decimal("0")) - this_order_unfulfilled
            available = max(Decimal("0"), (material.current_stock or Decimal("0")) - reserved_by_others)
            pending = pending_by_material.get(material_id, Decimal("0"))
            shortage = max(Decimal("0"), required - available - pending)
            if shortage <= 0:
                continue
            at_risk.setdefault(order_id, []).append({
                "material_id": material.id, "material_name": material.name, "unit": material.unit,
                "required": required, "available": available,
                "shortage": shortage, "recommended_purchase_quantity": shortage,
            })

        all_shortage_material_ids = list({
            m["material_id"] for materials in at_risk.values() for m in materials
        })
        from app.modules.procurement.services import ProcurementService
        supplier_options = ProcurementService._supplier_options_for_materials(db, all_shortage_material_ids)

        results = []
        for order_id, materials in at_risk.items():
            order = orders_by_id[order_id]
            for m in materials:
                m["supplier_options"] = supplier_options.get(m["material_id"], [])
            materials.sort(key=lambda m: m["shortage"], reverse=True)
            results.append({
                "order_id": order.id, "order_code": order.order_code,
                "client_name": order.client.name if order.client else None,
                "delivery_date": order.delivery_date.isoformat() if order.delivery_date else None,
                "project_status": order.project_status,
                "total_shortage_lines": len(materials),
                "materials": materials,
            })
        results.sort(key=lambda r: sum(m["shortage"] for m in r["materials"]), reverse=True)
        return results
