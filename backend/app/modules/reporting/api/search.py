from typing import List, Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.platform.database.database import get_db
from app.platform.security.security import get_current_user
from app.modules.clients.models import Client
from app.modules.sales.models import Order, Estimate
from app.modules.inventory.models import Material, Supplier
from app.modules.hr.models import Employee
from app.modules.operations.models import DailyTask

router = APIRouter(prefix="/api/search", tags=["search"])

RESULTS_PER_TYPE = 5


@router.get("/", response_model=List[dict])
def global_search(q: Optional[str] = Query(None, min_length=1), db: Session = Depends(get_db),
                   auth=Depends(get_current_user)):
    """Searches across the entities named in the product brief - client
    name/phone, order reference, estimate reference, material, supplier,
    employee, task - matching against both the human-scannable sequential
    code (CL-001, MAT-011, ...) and the opaque 10-character business_id,
    since a user might paste either. Returns a single ranked list, each
    result tagged with its record type so the frontend can route to the
    right detail page. Every entity here is already visible to all
    authenticated roles, so this endpoint doesn't need its own extra RBAC
    beyond that - it deliberately excludes role-restricted data (payments,
    salary, candidates, interviews) rather than complicate that per-result."""
    if not q or not q.strip():
        return []
    like = f"%{q.strip()}%"
    results = []

    for c in db.query(Client).filter(
        (Client.name.ilike(like)) | (Client.phone.ilike(like)) |
        (Client.client_code.ilike(like)) | (Client.business_id.ilike(like))
    ).limit(RESULTS_PER_TYPE).all():
        results.append({"type": "Client", "id": c.id, "label": c.name, "sublabel": c.client_code, "path": f"/clients/{c.id}"})

    for o in db.query(Order).filter(
        (Order.order_code.ilike(like)) | (Order.project_type.ilike(like)) | (Order.business_id.ilike(like))
    ).limit(RESULTS_PER_TYPE).all():
        results.append({"type": "Order", "id": o.id, "label": o.order_code,
                         "sublabel": o.project_type or (o.client.name if o.client else ""), "path": f"/orders/{o.id}"})

    for e in db.query(Estimate).filter(
        (Estimate.estimate_code.ilike(like)) | (Estimate.business_id.ilike(like))
    ).limit(RESULTS_PER_TYPE).all():
        results.append({"type": "Estimate", "id": e.id, "label": e.estimate_code,
                         "sublabel": e.client.name if e.client else "", "path": f"/estimates/{e.id}"})

    for m in db.query(Material).filter(
        (Material.name.ilike(like)) | (Material.material_code.ilike(like)) | (Material.business_id.ilike(like))
    ).limit(RESULTS_PER_TYPE).all():
        results.append({"type": "Material", "id": m.id, "label": m.name, "sublabel": m.material_code, "path": f"/materials/{m.id}"})

    for s in db.query(Supplier).filter(
        (Supplier.name.ilike(like)) | (Supplier.supplier_code.ilike(like)) | (Supplier.business_id.ilike(like))
    ).limit(RESULTS_PER_TYPE).all():
        results.append({"type": "Supplier", "id": s.id, "label": s.name, "sublabel": s.supplier_code, "path": f"/suppliers/{s.id}"})

    for emp in db.query(Employee).filter(
        (Employee.name.ilike(like)) | (Employee.employee_code.ilike(like)) | (Employee.business_id.ilike(like))
    ).limit(RESULTS_PER_TYPE).all():
        results.append({"type": "Employee", "id": emp.id, "label": emp.name,
                         "sublabel": emp.department or emp.employee_code, "path": f"/employees/{emp.id}"})

    for t in db.query(DailyTask).filter(
        (DailyTask.task_description.ilike(like)) | (DailyTask.task_code.ilike(like)) | (DailyTask.business_id.ilike(like))
    ).limit(RESULTS_PER_TYPE).all():
        results.append({"type": "Task", "id": t.id, "label": t.task_description,
                         "sublabel": t.task_code, "path": f"/daily-tasks/{t.id}"})

    return results
