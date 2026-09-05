"""Operations-domain report exports: production jobs, daily tasks,
project expenses, the automation audit log, and the daily status
report (Excel + email delivery). Split out of the former monolithic
reports.py - see modules/inventory/api/reports.py's docstring for why."""
from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy.orm import Session, selectinload
from sqlalchemy import func

from app.platform.database.database import get_db
from app.platform.security.security import get_current_user, require_role
from app.platform.security.rate_limit import rate_limit
from app.platform.configuration.config import settings
from app.modules.operations.models import DailyTask, ProductionJob
from app.modules.hr.models import Employee
from app.modules.sales.models import Order
from app.modules.communications.models import AutomationLog
from app.modules.operations.models import ProjectExpense
from app.shared.exporters import build_workbook, xlsx_response

router = APIRouter(prefix="/api/reports", tags=["reports"], dependencies=[
    Depends(rate_limit("export", settings.RATE_LIMIT_EXPORT_PER_MINUTE))
])


@router.get("/production.xlsx")
def export_production(
    employee_id: Optional[int] = Query(None), machine: Optional[str] = Query(None),
    order_id: Optional[int] = Query(None), stage: Optional[str] = Query(None),
    date_from: Optional[datetime] = Query(None), date_to: Optional[datetime] = Query(None),
    db: Session = Depends(get_db), auth=Depends(get_current_user),
):
    """One flexible, filterable endpoint covering "Production Jobs",
    "Daily/Weekly Production" (via date_from/date_to), and
    "Machine/Operator Work" (via machine/employee_id) - all genuinely
    the same underlying ProductionJob data with a different filter
    applied, matching the export_tasks precedent rather than
    proliferating near-duplicate routes for each named variant."""
    query = db.query(ProductionJob).options(selectinload(ProductionJob.employee), selectinload(ProductionJob.order))
    filters_applied = []
    if employee_id:
        query = query.filter(ProductionJob.employee_id == employee_id)
        employee = db.query(Employee).filter(Employee.id == employee_id).first()
        filters_applied.append(f"Operator: {employee.name if employee else employee_id}")
    if machine:
        query = query.filter(ProductionJob.machine == machine)
        filters_applied.append(f"Machine: {machine}")
    if order_id:
        query = query.filter(ProductionJob.order_id == order_id)
        order = db.query(Order).filter(Order.id == order_id).first()
        filters_applied.append(f"Order: {order.order_code if order else order_id}")
    if stage:
        query = query.filter(ProductionJob.stage == stage)
        filters_applied.append(f"Stage: {stage}")
    if date_from:
        query = query.filter(ProductionJob.date >= date_from)
        filters_applied.append(f"From: {date_from.strftime('%d-%m-%Y')}")
    if date_to:
        query = query.filter(ProductionJob.date <= date_to)
        filters_applied.append(f"To: {date_to.strftime('%d-%m-%Y')}")

    jobs = query.order_by(ProductionJob.date.desc()).all()
    rows = [{
        "job_id": j.business_id or "", "date": j.date.strftime("%d-%m-%Y") if j.date else "",
        "operator": j.employee.name if j.employee else "", "order": j.order.order_code if j.order else "",
        "machine": j.machine or "", "stage": j.stage or "", "operation": j.operation or "",
        "planned_qty": j.planned_qty, "completed_qty": j.completed_qty, "status": j.status,
        "completion_date": j.completion_date.strftime("%d-%m-%Y") if j.completion_date else "",
        "remarks": j.remarks or "",
    } for j in jobs]

    subtitle = f"Generated on {datetime.utcnow().strftime('%d-%m-%Y %H:%M')}"
    if filters_applied:
        subtitle += "  |  Filters: " + ", ".join(filters_applied)
    summary = [
        ("Total Jobs", str(len(jobs))),
        ("Completed", str(sum(1 for j in jobs if j.status == "Completed"))),
        ("Total Planned Qty", str(sum(j.planned_qty for j in jobs))),
        ("Total Completed Qty", str(sum(j.completed_qty for j in jobs))),
    ]

    buffer = build_workbook([{
        "sheet_name": "Production", "title": "PRODUCTION REPORT",
        "columns": ["job_id", "date", "operator", "order", "machine", "stage", "operation",
                    "planned_qty", "completed_qty", "status", "completion_date", "remarks"],
        "headers": ["Job ID", "Date", "Operator", "Order", "Machine", "Stage", "Operation",
                    "Planned Qty", "Completed Qty", "Status", "Completion Date", "Remarks"],
        "rows": rows, "subtitle": subtitle, "summary": summary,
    }])
    filename = f"production_{datetime.utcnow().strftime('%Y%m%d')}.xlsx"
    return xlsx_response(buffer, filename)


@router.get("/tasks.xlsx")
def export_tasks(employee_id: Optional[int] = Query(None), order_id: Optional[int] = Query(None),
                  db: Session = Depends(get_db), auth=Depends(get_current_user)):
    """Tasks & Production export - no financial fields exist on either
    model, so no role-based redaction is needed, matching "everyone can
    view tasks" for the Tasks sheet. employee_id covers "Employee-wise
    Tasks Excel", order_id covers "Project Tasks Excel" - one flexible,
    filterable endpoint rather than three separate routes for what's
    the same underlying data with a different filter applied."""
    task_query = db.query(DailyTask).options(
        selectinload(DailyTask.employee), selectinload(DailyTask.order), selectinload(DailyTask.order_item),
    )
    job_query = db.query(ProductionJob).options(selectinload(ProductionJob.employee), selectinload(ProductionJob.order))
    filters_applied = []
    if employee_id:
        task_query = task_query.filter(DailyTask.employee_id == employee_id)
        job_query = job_query.filter(ProductionJob.employee_id == employee_id)
        employee = db.query(Employee).filter(Employee.id == employee_id).first()
        filters_applied.append(f"Employee: {employee.name if employee else employee_id}")
    if order_id:
        task_query = task_query.filter(DailyTask.order_id == order_id)
        job_query = job_query.filter(ProductionJob.order_id == order_id)
        order = db.query(Order).filter(Order.id == order_id).first()
        filters_applied.append(f"Order: {order.order_code if order else order_id}")

    tasks = task_query.order_by(DailyTask.date.desc()).all()
    task_rows = [{
        "task_id": t.business_id or "", "date": t.date.strftime("%d-%m-%Y") if t.date else "",
        "employee": t.employee.name if t.employee else "", "task": t.task_description,
        "order": t.order.order_code if t.order else "",
        # Two useful fields the existing export was
        # missing, both already derivable from relationships DailyTask
        # already has (never duplicated onto the model itself).
        "category": t.task_category or "",
        "product": (t.order_item.product_name or t.order_item.description) if t.order_item else "",
        "due_date": t.due_date.strftime("%d-%m-%Y") if t.due_date else "",
        "priority": t.priority or "",
        "status": t.status, "completion_percent": t.completion_percent,
        "delay_reason": t.delay_reason or "", "remarks": t.remarks or "",
    } for t in tasks]

    jobs = job_query.order_by(ProductionJob.date.desc()).all()
    job_rows = [{
        "job_id": p.business_id or "", "date": p.date.strftime("%d-%m-%Y") if p.date else "",
        "employee": p.employee.name if p.employee else "", "order": p.order.order_code if p.order else "",
        "operation": p.operation or "", "planned_qty": p.planned_qty, "completed_qty": p.completed_qty,
        "status": p.status,
    } for p in jobs]

    subtitle = f"Generated on {datetime.utcnow().strftime('%d-%m-%Y %H:%M')}"
    if filters_applied:
        subtitle += "  |  Filters: " + ", ".join(filters_applied)

    buffer = build_workbook([
        {"sheet_name": "Tasks", "title": "STAFF TASKS",
         "columns": ["task_id", "date", "employee", "task", "order", "category", "product", "due_date",
                     "priority", "status", "completion_percent", "delay_reason", "remarks"],
         "headers": ["Task ID", "Date", "Employee", "Task", "Order", "Category", "Product", "Due Date",
                     "Priority", "Status", "Completion %", "Delay Reason", "Remarks"],
         "rows": task_rows, "subtitle": subtitle},
        {"sheet_name": "Production", "title": "PRODUCTION JOBS",
         "columns": ["job_id", "date", "employee", "order", "operation", "planned_qty", "completed_qty", "status"],
         "headers": ["Job ID", "Date", "Operator", "Order", "Operation", "Planned Qty", "Completed Qty", "Status"],
         "rows": job_rows, "subtitle": subtitle},
    ])
    filename = f"tasks_production_{datetime.utcnow().strftime('%Y%m%d')}.xlsx"
    return xlsx_response(buffer, filename)


@router.get("/project-expenses.xlsx")
def export_project_expenses(
    order_id: Optional[int] = Query(None), category: Optional[str] = Query(None),
    start_date: Optional[str] = Query(None), end_date: Optional[str] = Query(None),
    db: Session = Depends(get_db), auth=Depends(require_role("master")),
):
    """Expense Register export. Master-only, matching
    project_expenses.py's own require_role("master") gate - every field
    on ProjectExpense is financial, so there is no partial/redacted view."""
    query = db.query(ProjectExpense).options(selectinload(ProjectExpense.order))
    filters_applied = []
    if order_id:
        query = query.filter(ProjectExpense.order_id == order_id)
        order = db.query(Order).filter(Order.id == order_id).first()
        filters_applied.append(f"Order: {order.order_code if order else order_id}")
    if category:
        query = query.filter(ProjectExpense.category == category)
        filters_applied.append(f"Category: {category}")
    if start_date:
        query = query.filter(ProjectExpense.date >= datetime.fromisoformat(start_date))
        filters_applied.append(f"From {start_date}")
    if end_date:
        query = query.filter(ProjectExpense.date <= datetime.fromisoformat(end_date))
        filters_applied.append(f"To {end_date}")

    expenses = query.order_by(ProjectExpense.date.desc()).all()
    rows = [{
        "expense_id": e.business_id or "", "expense_code": e.expense_code,
        "date": e.date.strftime("%d-%m-%Y") if e.date else "",
        "order": e.order.order_code if e.order else "", "category": e.category,
        "description": e.description or "", "paid_to": e.paid_to or "",
        "amount": float(e.amount or 0), "approved_by": e.approved_by or "",
    } for e in expenses]
    columns = ["expense_id", "expense_code", "date", "order", "category", "description",
               "paid_to", "amount", "approved_by"]
    headers = ["Expense ID", "Expense Code", "Date", "Order", "Category", "Description",
               "Paid To", "Amount", "Approved By"]

    subtitle = f"Generated on {datetime.utcnow().strftime('%d-%m-%Y %H:%M')}"
    if filters_applied:
        subtitle += "  |  Filters: " + ", ".join(filters_applied)
    by_category = {}
    for e in expenses:
        by_category[e.category or "Uncategorized"] = by_category.get(e.category or "Uncategorized", 0) + float(e.amount or 0)
    summary = [("Total Expenses", str(len(expenses))), ("Total Amount", f"Rs {sum(float(e.amount or 0) for e in expenses):,.2f}")]
    summary += [(f"  {cat}", f"Rs {amt:,.2f}") for cat, amt in sorted(by_category.items())]

    buffer = build_workbook([{
        "sheet_name": "Expenses", "title": "PROJECT EXPENSE REGISTER",
        "columns": columns, "headers": headers, "rows": rows,
        "total_columns": ["amount"], "subtitle": subtitle, "summary": summary,
    }])
    filename = f"expense_register_{datetime.utcnow().strftime('%Y%m%d')}.xlsx"
    return xlsx_response(buffer, filename)


@router.get("/automation-log.xlsx")
def export_automation_log(rule_key: Optional[str] = None, status: Optional[str] = None,
                           db: Session = Depends(get_db), auth=Depends(require_role("master"))):
    """The automation audit trail as a downloadable report.
    Reuses this module's existing Excel infrastructure (build_workbook /
    write_sheet) rather than a separate export mechanism - same
    formatting, same formula-injection sanitization, as every other
    report here. Master-only, same as GET /api/automation/logs and
    /api/audit-logs."""
    query = db.query(AutomationLog)
    if rule_key:
        query = query.filter(AutomationLog.rule_key == rule_key)
    if status:
        query = query.filter(AutomationLog.status == status)
    logs = query.order_by(AutomationLog.created_at.desc()).limit(2000).all()
    rows = [{
        "created_at": log.created_at.strftime("%d-%m-%Y %H:%M") if log.created_at else "",
        "rule_key": log.rule_key, "trigger_event": log.trigger_event, "status": log.status,
        "action_taken": log.action_taken, "condition_summary": log.condition_summary,
        "related_entity_type": log.related_entity_type or "", "related_entity_id": log.related_entity_id or "",
        "error_message": log.error_message or "",
    } for log in logs]
    columns = ["created_at", "rule_key", "trigger_event", "status", "action_taken",
               "condition_summary", "related_entity_type", "related_entity_id", "error_message"]
    headers = ["When", "Rule", "Trigger", "Status", "Action Taken",
               "Condition", "Entity Type", "Entity ID", "Error"]
    buffer = build_workbook([{"sheet_name": "Automation Log", "title": "AUTOMATION AUDIT TRAIL",
                               "columns": columns, "headers": headers, "rows": rows}])
    return xlsx_response(buffer, f"automation-log_{datetime.utcnow().strftime('%Y%m%d')}.xlsx")


def _record_report_generated(db: Session, report_type: str, report_date, storage_identity: str = None) -> None:
    """Records this generation event and
    expires any report_history rows older than 15 days. Never touches
    any other table - the underlying business records (tasks, orders,
    etc) this report reads from are completely untouched by this
    retention sweep."""
    from app.modules.reporting.models import ReportHistory
    from datetime import timedelta
    db.query(ReportHistory).filter(
        ReportHistory.created_at < datetime.utcnow() - timedelta(days=15)
    ).delete(synchronize_session=False)
    db.add(ReportHistory(
        report_type=report_type, report_date=datetime(report_date.year, report_date.month, report_date.day),
        generated_at=datetime.utcnow(), storage_identity=storage_identity,
    ))
    db.commit()


def _daily_status_rows(db: Session, target_date):
    """The single, authoritative query behind both the Excel export and
    the email endpoint below - Employee Name / Assigned Task / Task
    Status / Pending Items from Task / Required Things, exactly as
    given in the product spec. Pending Items maps to delay_reason,
    Required Things maps to remarks - the same fields already visible
    on the task itself, not two new columns invented for this report."""
    from app.modules.operations.models import DailyTask
    from app.modules.hr.models import Employee
    tasks = (
        db.query(DailyTask).join(Employee, DailyTask.employee_id == Employee.id)
        .filter(func.date(DailyTask.date) == target_date)
        .order_by(Employee.name, DailyTask.id).all()
    )
    rows = [{
        "employee_name": t.employee.name if t.employee else "Unassigned",
        "assigned_task": t.task_description,
        "task_status": t.status,
        "pending_items": t.delay_reason or "",
        "required_things": t.remarks or "",
    } for t in tasks]
    return tasks, rows


@router.get("/daily-status-report.xlsx")
def export_daily_status_report(report_date: Optional[str] = Query(None, description="YYYY-MM-DD, defaults to today"),
                                db: Session = Depends(get_db), auth=Depends(require_role("master"))):
    """The end-of-day status report Master Users
    receive, with the exact column spec the product doc gives:
    Employee Name / Assigned Task / Task Status / Pending Items from
    Task / Required Things. Pending Items maps to delay_reason (the
    existing field DailyTask already uses for exactly this - "why
    isn't this done"), Required Things maps to remarks (the existing
    general-notes field) - not two new columns invented for this
    report, the same fields already visible on the task itself.

    Accepts an explicit date so a historical lookup
    ("last week mein kiska kya kaam reh gaya tha") can reuse this
    same endpoint/format rather than a second report implementation -
    the report and its Excel export must use the same authoritative
    information, so there is only one query here, not one for chat and
    a different one for Excel."""
    if report_date:
        try:
            target_date = datetime.strptime(report_date, "%Y-%m-%d").date()
        except ValueError:
            raise HTTPException(status_code=400, detail="report_date must be in YYYY-MM-DD format.")
    else:
        target_date = datetime.utcnow().date()

    tasks, rows = _daily_status_rows(db, target_date)
    _record_report_generated(db, "daily_status_report", target_date, storage_identity="download")
    columns = ["employee_name", "assigned_task", "task_status", "pending_items", "required_things"]
    headers = ["Employee Name", "Assigned Task", "Task Status", "Pending Items from Task", "Required Things"]
    buffer = build_workbook([{
        "sheet_name": "Daily Status Report", "title": f"WOODFUL DAILY STATUS REPORT - {target_date.strftime('%d %b %Y')}",
        "columns": columns, "headers": headers, "rows": rows,
        "summary": [("Total Tasks", str(len(tasks))), ("Date", target_date.strftime("%d %b %Y"))],
    }])
    return xlsx_response(buffer, f"woodful-daily-status_{target_date.strftime('%Y%m%d')}.xlsx")


@router.post("/daily-status-report/send")
def send_daily_status_report_email(request: Request,
                                    report_date: Optional[str] = Query(None, description="YYYY-MM-DD, defaults to today"),
                                    db: Session = Depends(get_db), auth=Depends(require_role("master"))):
    """Automatic end-of-day delivery - emails
    the same authoritative report export_daily_status_report builds
    (via the shared _daily_status_rows query above, not a second
    implementation) to every active Master User. This app has no
    in-process scheduler, so "automatic" delivery means this endpoint
    is meant to be triggered by an external daily cron/scheduled task
    hitting it once at end of day - the same lightweight approach
    already established for send_team_summary_email, not a new
    in-process scheduling engine."""
    from app.modules.auth.models import User
    if report_date:
        try:
            target_date = datetime.strptime(report_date, "%Y-%m-%d").date()
        except ValueError:
            raise HTTPException(status_code=400, detail="report_date must be in YYYY-MM-DD format.")
    else:
        target_date = datetime.utcnow().date()

    master_emails = [
        u.email for u in db.query(User).filter(User.role == "master", User.is_active == True).all()  # noqa: E712
        if u.email
    ]
    if not master_emails:
        raise HTTPException(status_code=400, detail="No active master account has an email on file.")

    tasks, rows = _daily_status_rows(db, target_date)
    if not tasks:
        raise HTTPException(status_code=404, detail=f"No tasks are recorded for {target_date.strftime('%d %b %Y')}.")
    _record_report_generated(db, "daily_status_report", target_date, storage_identity=f"email:{','.join(master_emails)}")

    lines = [f"Woodful Daily Status Report - {target_date.strftime('%d %b %Y')}", ""]
    for r in rows:
        lines.append(f"{r['employee_name']} - {r['assigned_task']} (Status: {r['task_status']})")
        if r["pending_items"]:
            lines.append(f"  Pending: {r['pending_items']}")
        if r["required_things"]:
            lines.append(f"  Required: {r['required_things']}")
    body = "\n".join(lines)
    subject = f"Woodful Daily Status Report - {target_date.strftime('%d %b %Y')}"

    from app.modules.communications.services.email_service import EmailService
    email_service = EmailService()
    results = {email: email_service.send_email(to_email=email, subject=subject, body=body, is_html=False)
               for email in master_emails}
    sent_count = sum(1 for ok in results.values() if ok)

    from app.platform.audit.audit import log_action
    log_action(db, request, user_id=auth.get("user_id"), action="send_daily_status_report_email",
               module_name="reports",
               new_value={"recipients": master_emails, "sent_count": sent_count, "task_count": len(tasks)})

    if sent_count == 0:
        raise HTTPException(
            status_code=502,
            detail="The daily status report could not be sent right now (email service unavailable or misconfigured).",
        )
    failed = [email for email, ok in results.items() if not ok]
    message = f"Daily status report ({len(tasks)} task(s)) emailed to {sent_count} of {len(master_emails)} master account(s)."
    if failed:
        message += f" Failed for: {', '.join(failed)}."
    return {"sent": True, "message": message, "task_count": len(tasks), "sent_count": sent_count, "failed_recipients": failed}
