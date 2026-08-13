"""
Seed the database with the sample data from the three source workbooks
(Stock Management, Staff & Tasks Management, Order & Sales Management).

Idempotent - safe to re-run; skips any table that already has rows.
Does NOT create any users - run create_master_user.py for that.
"""
import logging
import os
import sys
from datetime import datetime, date, time
from decimal import Decimal

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.core.database import Base, SessionLocal, engine
from app import models  # noqa: F401
from app.models.setting import (
    Unit, StockStatus, StockPaymentStatus, SupplierTerm,
    Department, TaskStatus, AttendanceStatus, Machine,
    ProjectStatus, Priority, PaymentMode, LeadSource, ProjectType, ExpenseCategory,
)
from app.models.material_category import MaterialCategory
from app.models.location import Location
from app.models.supplier import Supplier
from app.models.material import Material
from app.models.purchase import Purchase
from app.models.issue import Issue
from app.models.client import Client
from app.models.order import Order
from app.models.payment import Payment
from app.models.project_expense import ProjectExpense
from app.models.employee import Employee
from app.models.attendance import Attendance
from app.models.daily_task import DailyTask
from app.models.production_job import ProductionJob

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def _d(s):
    return datetime.strptime(s, "%Y-%m-%d")


def _dt(s):
    return datetime.strptime(s, "%Y-%m-%d %H:%M")


def _t(s):
    return datetime.strptime(s, "%H:%M").time()


LOOKUPS = {
    Unit: ["Sheets", "Nos", "Kg", "Litres", "Metres", "Feet", "Sq Ft", "Boxes", "Sets"],
    MaterialCategory: ["Plywood", "HDHMR", "MDF", "Particle Board", "Block Board", "Laminate",
                        "Edge Band", "Hardware", "Adhesive", "Paint/PU", "Acrylic", "ACP", "WPC",
                        "Solid Wood", "Packaging", "Consumable"],
    StockStatus: ["STOCK OK", "LOW STOCK", "OUT OF STOCK"],
    StockPaymentStatus: ["Paid", "Part Paid", "Credit"],
    Location: ["Rack A1", "Rack A2", "Rack A3", "Rack B1", "Rack B2", "Bin H1", "Bin H2",
               "Chemical Area", "Paint Store", "Open Yard"],
    SupplierTerm: ["Cash", "7 Days", "15 Days", "30 Days", "45 Days"],
    Department: ["CNC", "Laser", "Panel Saw", "Edge Banding", "Assembly", "Painting",
                 "Installation", "Design", "Accounts", "Sales & Marketing", "Store"],
    TaskStatus: ["Not Started", "In Progress", "Completed", "On Hold"],
    AttendanceStatus: ["Present", "Absent", "Half Day", "Leave"],
    Machine: ["CNC Router", "CO2 Laser", "Panel Saw", "Edge Bander", "Cold Press", "PU Paint Setup"],
    ProjectStatus: ["Enquiry", "Designing", "Approved", "Material Purchase", "Cutting",
                     "Edge Banding", "Assembly", "Painting", "Ready for Dispatch",
                     "Installation", "Completed", "On Hold"],
    Priority: ["Low", "Medium", "High", "Urgent"],
    PaymentMode: ["Cash", "UPI", "Bank", "Credit Card"],
    LeadSource: ["Instagram", "Facebook", "Architect", "Referral", "Google", "Walk-in", "Existing Client"],
    ProjectType: ["Bedroom Furniture", "Modular Kitchen", "Wardrobe", "TV Unit", "Mandir",
                  "CNC Wall Panel", "Office Furniture", "Showroom Display", "Other"],
    ExpenseCategory: ["Raw Material", "Hardware", "Transport", "Installation", "Labour",
                       "Design", "Marketing", "Miscellaneous"],
}


def seed_lookups(db):
    for model, names in LOOKUPS.items():
        if db.query(model).count() > 0:
            continue
        for n in names:
            db.add(model(name=n))
        logger.info("Seeded %d rows into %s", len(names), model.__tablename__)
    db.commit()


def seed_suppliers(db):
    if db.query(Supplier).count() > 0:
        return {s.supplier_code: s for s in db.query(Supplier).all()}
    rows = [
        ("SUP-001", "Century Plywood Dealer", "Plywood", "Rajesh", "98XXXXXX21", "23ABCDE1234F1Z5", "15 Days", "Primary plywood supplier"),
        ("SUP-002", "Greenpanel Distributor", "HDHMR", "Mukesh", "98XXXXXX22", "23ABCDE2234F1Z5", "Cash", "HDHMR and MDF"),
        ("SUP-003", "Merino Laminates", "Laminate", "Deepak", "98XXXXXX23", "23ABCDE3234F1Z5", "30 Days", "Decorative laminates"),
        ("SUP-004", "Hardware Hub", "Hardware", "Vikas", "98XXXXXX24", "23ABCDE4234F1Z5", "7 Days", "Hinges and channels"),
        ("SUP-005", "Paint Solutions", "Paint/PU", "Ajay", "98XXXXXX25", "23ABCDE5234F1Z5", "Cash", "PU and polish material"),
    ]
    out = {}
    for code, name, cat, contact, phone, gstin, terms, remarks in rows:
        s = Supplier(supplier_code=code, name=name, category=cat, contact_person=contact,
                      phone=phone, gstin=gstin, payment_terms=terms, remarks=remarks)
        db.add(s)
        out[code] = s
    db.commit()
    logger.info("Seeded %d suppliers", len(rows))
    return out


def seed_materials(db, suppliers):
    if db.query(Material).count() > 0:
        return {m.material_code: m for m in db.query(Material).all()}
    rows = [
        ("MAT-001", "HDHMR 18mm", "HDHMR", "Greenpanel", "8x4 ft / 18mm", "Sheets", 35, 20, 32, 23, 20, 1800, "SUP-002", "Rack A1"),
        ("MAT-002", "Plywood BWP 18mm", "Plywood", "Century", "8x4 ft / 18mm", "Sheets", 28, 15, 20, 23, 15, 2400, "SUP-001", "Rack A2"),
        ("MAT-003", "MDF 12mm", "MDF", "Action Tesa", "8x4 ft / 12mm", "Sheets", 22, 0, 12, 10, 10, 1250, "SUP-002", "Rack A3"),
        ("MAT-004", "White Laminate 1mm", "Laminate", "Merino", "8x4 ft / 1mm", "Sheets", 40, 30, 22, 48, 15, 950, "SUP-003", "Rack B1"),
        ("MAT-005", "Walnut Laminate 1mm", "Laminate", "Merino", "8x4 ft / 1mm", "Sheets", 18, 0, 0, 18, 10, 1150, "SUP-003", "Rack B2"),
        ("MAT-006", "Soft Close Hinges", "Hardware", "Hettich", "Full Overlay", "Nos", 120, 100, 90, 130, 50, 145, "SUP-004", "Bin H1"),
        ("MAT-007", "Telescopic Channel 18in", "Hardware", "Ebco", "18 inch pair", "Sets", 35, 20, 18, 37, 15, 480, "SUP-004", "Bin H2"),
        ("MAT-008", "Fevicol HeatX", "Adhesive", "Pidilite", "50 kg drum", "Kg", 65, 0, 0, 65, 20, 210, "SUP-004", "Chemical Area"),
        ("MAT-009", "PVC Edge Band White", "Edge Band", "Rehau", "22mm x 0.8mm", "Metres", 450, 300, 380, 370, 150, 18, "SUP-004", "Rack B2"),
        ("MAT-010", "PU White Paint", "Paint/PU", "Asian Paints", "20 Litre", "Litres", 24, 20, 9, 35, 10, 620, "SUP-005", "Paint Store"),
    ]
    out = {}
    for code, name, cat, brand, size, unit, opening, purchased, issued, current, minimum, rate, sup_code, loc in rows:
        m = Material(material_code=code, name=name, category=cat, brand_grade=brand,
                      thickness_size=size, unit=unit, opening_stock=opening,
                      total_purchased=purchased, total_issued=issued, current_stock=current,
                      minimum_stock=minimum, average_rate=Decimal(str(rate)),
                      supplier_id=suppliers[sup_code].id, location=loc)
        db.add(m)
        out[code] = m
    db.commit()
    logger.info("Seeded %d materials", len(rows))
    return out


def seed_clients(db):
    if db.query(Client).count() > 0:
        return {c.client_code: c for c in db.query(Client).all()}
    rows = [
        ("CL-001", "Rahul Sir", "93XXXXXX54", "rahul@example.com", "Indore", "Referral", "2026-07-10", "Bedroom furniture"),
        ("CL-002", "Sharma Family", "98XXXXXX31", "sharma@example.com", "Bicholi, Indore", "Architect", "2026-07-12", "Modular kitchen"),
        ("CL-003", "Architect Studio", "98XXXXXX32", "studio@example.com", "Vijay Nagar", "Instagram", "2026-07-18", "CNC wall panel"),
        ("CL-004", "Rakesh Ji", "98XXXXXX33", "rakesh@example.com", "Rau", "Existing Client", "2026-07-19", "Mandir"),
        ("CL-005", "Factory Display", "93XXXXXX00", "info@woodful.local", "Woodful Creations", "Internal", "2026-07-20", "Showroom display"),
    ]
    out = {}
    for code, name, phone, email, addr, source, contact_date, remarks in rows:
        c = Client(client_code=code, name=name, phone=phone, email=email, address=addr,
                   lead_source=source, first_contact_date=_d(contact_date), remarks=remarks)
        db.add(c)
        out[code] = c
    db.commit()
    logger.info("Seeded %d clients", len(rows))
    return out


def seed_orders(db, clients):
    if db.query(Order).count() > 0:
        return {o.order_code: o for o in db.query(Order).all()}
    rows = [
        ("WC-2026-001", "CL-001", "Bedroom Furniture", "2026-07-20", "2026-08-20", 325000, 32500, 97500, "Cutting", 45, "High", "Ravi", "Indore", "Bedroom and wardrobe"),
        ("WC-2026-002", "CL-002", "Modular Kitchen", "2026-07-22", "2026-08-25", 216000, 21600, 64800, "Material Purchase", 30, "Urgent", "Amit", "Bicholi, Indore", "Base and wall cabinets"),
        ("WC-2026-003", "CL-003", "CNC Wall Panel", "2026-07-25", "2026-08-10", 85000, 25000, 0, "Designing", 10, "Medium", "Amit", "Vijay Nagar", "3D carved panel"),
        ("WC-2026-004", "CL-004", "Mandir", "2026-07-26", "2026-08-18", 125000, 25000, 0, "Approved", 20, "High", "Ravi", "Rau", "HDHMR mandir"),
        ("WC-2026-005", "CL-005", "Showroom Display", "2026-07-27", "2026-09-01", 180000, 0, 0, "Designing", 10, "Low", "Manish", "Woodful Creations", "Internal work"),
    ]
    out = {}
    for code, cl_code, ptype, odate, ddate, value, advance, other, status, progress, priority, sup, addr, remarks in rows:
        total_received = Decimal(str(advance)) + Decimal(str(other))
        o = Order(order_code=code, client_id=clients[cl_code].id, project_type=ptype,
                  order_date=_d(odate), delivery_date=_d(ddate), order_value=Decimal(str(value)),
                  advance=Decimal(str(advance)), other_received=Decimal(str(other)),
                  total_received=total_received, balance=Decimal(str(value)) - total_received,
                  project_status=status, progress_percent=progress, priority=priority,
                  supervisor=sup, site_address=addr, remarks=remarks)
        db.add(o)
        out[code] = o
    db.commit()
    logger.info("Seeded %d orders", len(rows))
    return out


def seed_payments(db, orders):
    if db.query(Payment).count() > 0:
        return
    rows = [
        ("RCPT-001", "2026-07-20", "WC-2026-001", "Advance", "Bank", 32500, "UTR001"),
        ("RCPT-002", "2026-07-25", "WC-2026-001", "Progress Payment", "UPI", 97500, "UPI001"),
        ("RCPT-003", "2026-07-22", "WC-2026-002", "Advance", "Bank", 21600, "UTR002"),
        ("RCPT-004", "2026-07-27", "WC-2026-002", "Progress Payment", "Bank", 64800, "UTR003"),
        ("RCPT-005", "2026-07-25", "WC-2026-003", "Advance", "UPI", 25000, "UPI003"),
        ("RCPT-006", "2026-07-26", "WC-2026-004", "Advance", "Cash", 25000, "CASH001"),
        ("RCPT-007", "2026-07-28", "WC-2026-005", "Internal", "Bank", 0, None),
    ]
    for code, pdate, order_code, ptype, mode, amount, ref in rows:
        db.add(Payment(receipt_code=code, date=_d(pdate), order_id=orders[order_code].id,
                        payment_type=ptype, payment_mode=mode, amount=Decimal(str(amount)),
                        reference_number=ref, received_by="Nikhil"))
    db.commit()
    logger.info("Seeded %d payments", len(rows))


def seed_project_expenses(db, orders):
    if db.query(ProjectExpense).count() > 0:
        return
    rows = [
        ("EXP-001", "2026-07-21", "WC-2026-001", "Raw Material", "HDHMR and laminate", "Supplier", 85000),
        ("EXP-002", "2026-07-24", "WC-2026-001", "Labour", "Carpentry labour", "Ravi Team", 28000),
        ("EXP-003", "2026-07-23", "WC-2026-002", "Raw Material", "Plywood and laminate", "Supplier", 72000),
        ("EXP-004", "2026-07-25", "WC-2026-002", "Hardware", "Hinges and channels", "Hardware Hub", 26000),
        ("EXP-005", "2026-07-26", "WC-2026-003", "Raw Material", "MDF sheets", "Supplier", 18000),
        ("EXP-006", "2026-07-27", "WC-2026-004", "Paint/PU", "PU material", "Paint Solutions", 14000),
        ("EXP-007", "2026-07-28", "WC-2026-004", "Labour", "Carving labour", "CNC Team", 12000),
    ]
    for code, edate, order_code, cat, desc, paid_to, amount in rows:
        db.add(ProjectExpense(expense_code=code, date=_d(edate), order_id=orders[order_code].id,
                               category=cat, description=desc, paid_to=paid_to,
                               amount=Decimal(str(amount)), approved_by="Nikhil"))
    db.commit()
    logger.info("Seeded %d project expenses", len(rows))


def seed_purchases(db, suppliers, materials):
    if db.query(Purchase).count() > 0:
        return
    rows = [
        ("PUR-001", "2026-07-20", "SUP-002", "MAT-001", 20, "Sheets", 1800, 36000, 18, 6480, 42480, "Paid"),
        ("PUR-002", "2026-07-21", "SUP-001", "MAT-002", 15, "Sheets", 2400, 36000, 18, 6480, 42480, "Part Paid"),
        ("PUR-003", "2026-07-22", "SUP-003", "MAT-004", 30, "Sheets", 950, 28500, 18, 5130, 33630, "Credit"),
        ("PUR-004", "2026-07-22", "SUP-004", "MAT-006", 100, "Nos", 145, 14500, 18, 2610, 17110, "Paid"),
        ("PUR-005", "2026-07-23", "SUP-004", "MAT-009", 300, "Metres", 18, 5400, 18, 972, 6372, "Paid"),
        ("PUR-006", "2026-07-24", "SUP-005", "MAT-010", 20, "Litres", 620, 12400, 18, 2232, 14632, "Credit"),
        ("PUR-007", "2026-07-25", "SUP-004", "MAT-007", 20, "Sets", 480, 9600, 18, 1728, 11328, "Paid"),
    ]
    for code, pdate, sup_code, mat_code, qty, unit, rate, taxable, gst_pct, gst_amt, total, status in rows:
        db.add(Purchase(purchase_code=code, date=_d(pdate), supplier_id=suppliers[sup_code].id,
                         material_id=materials[mat_code].id, quantity=Decimal(str(qty)), unit=unit,
                         rate=Decimal(str(rate)), taxable_value=Decimal(str(taxable)),
                         gst_percent=Decimal(str(gst_pct)), gst_amount=Decimal(str(gst_amt)),
                         invoice_total=Decimal(str(total)), payment_status=status))
    db.commit()
    logger.info("Seeded %d purchases", len(rows))


def seed_issues(db, orders, materials):
    if db.query(Issue).count() > 0:
        return
    rows = [
        ("ISS-001", "2026-07-23", "WC-2026-001", "MAT-001", 18, "Sheets", "Ravi", "Assembly", "Wardrobe and bed"),
        ("ISS-002", "2026-07-23", "WC-2026-001", "MAT-004", 22, "Sheets", "Sohan", "Edge Banding", "Interior laminate"),
        ("ISS-003", "2026-07-24", "WC-2026-002", "MAT-002", 20, "Sheets", "Amit", "CNC", "Kitchen boxes"),
        ("ISS-004", "2026-07-24", "WC-2026-002", "MAT-006", 90, "Nos", "Ravi", "Assembly", "Kitchen shutters"),
        ("ISS-005", "2026-07-25", "WC-2026-003", "MAT-003", 12, "Sheets", "Amit", "CNC", "3D carving"),
        ("ISS-006", "2026-07-25", "WC-2026-001", "MAT-009", 380, "Metres", "Sohan", "Edge Banding", "Wardrobe edges"),
        ("ISS-007", "2026-07-26", "WC-2026-004", "MAT-001", 14, "Sheets", "Amit", "CNC", "Mandir panels"),
        ("ISS-008", "2026-07-27", "WC-2026-004", "MAT-010", 9, "Litres", "Rahul", "Painting", "PU finishing"),
        ("ISS-009", "2026-07-28", "WC-2026-002", "MAT-007", 18, "Sets", "Ravi", "Assembly", "Drawers"),
    ]
    for code, idate, order_code, mat_code, qty, unit, issued_to, dept, purpose in rows:
        db.add(Issue(issue_code=code, date=_d(idate), order_id=orders[order_code].id,
                      material_id=materials[mat_code].id, quantity_issued=Decimal(str(qty)),
                      unit=unit, issued_to=issued_to, department=dept, purpose=purpose,
                      approved_by="Nikhil"))
    db.commit()
    logger.info("Seeded %d issues", len(rows))


def seed_employees(db):
    if db.query(Employee).count() > 0:
        return {e.employee_code: e for e in db.query(Employee).all()}
    rows = [
        ("EMP-001", "Amit Verma", "CNC", "98XXXXXX01", "2026-04-01", 22000, "98XXXXXX11", "CNC operator"),
        ("EMP-002", "Ravi Prajapati", "Assembly", "98XXXXXX02", "2026-04-10", 19000, "98XXXXXX12", "Senior carpenter"),
        ("EMP-003", "Sohan Patel", "Edge Banding", "98XXXXXX03", "2026-05-01", 18000, "98XXXXXX13", "Edge band operator"),
        ("EMP-004", "Rahul Solanki", "Painting", "98XXXXXX04", "2026-05-15", 18500, "98XXXXXX14", "PU finishing"),
        ("EMP-005", "Manish Yadav", "Installation", "98XXXXXX05", "2026-06-01", 20000, "98XXXXXX15", "Site installation"),
    ]
    out = {}
    for code, name, dept, phone, joined, salary, emergency, remarks in rows:
        e = Employee(employee_code=code, name=name, department=dept, phone=phone,
                     joining_date=_d(joined), monthly_salary=Decimal(str(salary)),
                     status="Active", emergency_contact=emergency, remarks=remarks)
        db.add(e)
        out[code] = e
    db.commit()
    logger.info("Seeded %d employees", len(rows))
    return out


def seed_attendance(db, employees):
    if db.query(Attendance).count() > 0:
        return
    rows = [
        ("2026-07-28", "EMP-001", "2026-07-28 09:00", "2026-07-28 18:30", "Present", None),
        ("2026-07-28", "EMP-002", "2026-07-28 09:10", "2026-07-28 18:15", "Present", None),
        ("2026-07-28", "EMP-003", "2026-07-28 09:05", "2026-07-28 18:00", "Present", None),
        ("2026-07-28", "EMP-004", "2026-07-28 09:20", "2026-07-28 17:50", "Present", None),
        ("2026-07-28", "EMP-005", "2026-07-28 08:45", "2026-07-28 19:00", "Present", "Site visit"),
        ("2026-07-27", "EMP-004", None, None, "Absent", None),
    ]
    for adate, emp_code, in_t, out_t, status, remarks in rows:
        db.add(Attendance(date=_d(adate), employee_id=employees[emp_code].id,
                           in_time=_dt(in_t) if in_t else None, out_time=_dt(out_t) if out_t else None,
                           standard_hours=Decimal("8"), attendance_status=status, remarks=remarks))
    db.commit()
    logger.info("Seeded %d attendance records", len(rows))


def seed_daily_tasks(db, employees, orders):
    if db.query(DailyTask).count() > 0:
        return
    rows = [
        ("TSK-001", "2026-07-28", "EMP-001", "WC-2026-002", "Cut base cabinet panels", "Urgent", "09:00", "12:00", "Completed", 100, None),
        ("TSK-002", "2026-07-28", "EMP-003", "WC-2026-001", "Edge band wardrobe shutters", "High", "09:30", "13:30", "In Progress", 65, None),
        ("TSK-003", "2026-07-28", "EMP-002", "WC-2026-001", "Assemble bed storage boxes", "High", "10:00", "17:00", "In Progress", 50, None),
        ("TSK-004", "2026-07-28", "EMP-004", "WC-2026-004", "First PU primer coat", "Medium", "11:00", "16:00", "Not Started", 0, None),
        ("TSK-005", "2026-07-28", "EMP-005", "WC-2026-001", "Site measurement verification", "Urgent", "09:00", "11:00", "Completed", 100, None),
        ("TSK-006", "2026-07-29", "EMP-001", "WC-2026-003", "3D roughing toolpath", "High", "09:00", "14:00", "Not Started", 0, None),
        ("TSK-007", "2026-07-29", "EMP-003", "WC-2026-002", "Edge band base cabinets", "High", "10:00", "16:00", "Not Started", 0, None),
        ("TSK-008", "2026-07-29", "EMP-002", "WC-2026-002", "Assemble wall cabinets", "High", "09:00", "17:00", "Not Started", 0, None),
        ("TSK-009", "2026-07-29", "EMP-004", "WC-2026-004", "Sanding after primer", "Medium", "10:00", "15:00", "Not Started", 0, None),
        ("TSK-010", "2026-07-29", "EMP-005", "WC-2026-001", "Prepare installation hardware", "Medium", "12:00", "16:00", "Not Started", 0, None),
    ]
    for code, tdate, emp_code, order_code, desc, priority, start, end, status, completion, delay in rows:
        db.add(DailyTask(task_code=code, date=_d(tdate), employee_id=employees[emp_code].id,
                          order_id=orders[order_code].id, task_description=desc, priority=priority,
                          planned_start=_t(start), planned_end=_t(end), status=status,
                          completion_percent=completion, checked_by="Nikhil", delay_reason=delay))
    db.commit()
    logger.info("Seeded %d daily tasks", len(rows))


def seed_production_jobs(db, employees, orders, materials):
    if db.query(ProductionJob).count() > 0:
        return
    rows = [
        ("JOB-001", "2026-07-28", "CNC Router", "EMP-001", "WC-2026-002", "Panel cutting", "MAT-002", 18, 18, "09:00", "12:00", "Completed"),
        ("JOB-002", "2026-07-28", "Edge Bander", "EMP-003", "WC-2026-001", "Edge banding", "MAT-009", 32, 20, "09:30", "13:30", "In Progress"),
        ("JOB-003", "2026-07-28", "Cold Press", "EMP-002", "WC-2026-001", "Laminate pressing", "MAT-001", 12, 12, "10:00", "12:30", "Completed"),
        ("JOB-004", "2026-07-28", "PU Paint Setup", "EMP-004", "WC-2026-004", "Primer coat", "MAT-010", 8, 0, "11:00", "16:00", "Not Started"),
        ("JOB-005", "2026-07-29", "CNC Router", "EMP-001", "WC-2026-003", "3D roughing", "MAT-003", 4, 0, "09:00", "14:00", "Not Started"),
        ("JOB-006", "2026-07-29", "Panel Saw", "EMP-002", "WC-2026-002", "Strip cutting", "MAT-002", 15, 0, "09:00", "11:00", "Not Started"),
    ]
    for code, jdate, machine, emp_code, order_code, op, mat_code, planned, completed, start, end, status in rows:
        db.add(ProductionJob(job_code=code, date=_d(jdate), machine=machine,
                              employee_id=employees[emp_code].id, order_id=orders[order_code].id,
                              operation=op, material_id=materials[mat_code].id,
                              planned_qty=planned, completed_qty=completed,
                              start_time=_t(start), end_time=_t(end), status=status))
    db.commit()
    logger.info("Seeded %d production jobs", len(rows))


if __name__ == "__main__":
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    try:
        seed_lookups(db)
        suppliers = seed_suppliers(db)
        materials = seed_materials(db, suppliers)
        clients = seed_clients(db)
        orders = seed_orders(db, clients)
        seed_payments(db, orders)
        seed_project_expenses(db, orders)
        seed_purchases(db, suppliers, materials)
        seed_issues(db, orders, materials)
        employees = seed_employees(db)
        seed_attendance(db, employees)
        seed_daily_tasks(db, employees, orders)
        seed_production_jobs(db, employees, orders, materials)
        logger.info("Seed complete.")
    finally:
        db.close()
