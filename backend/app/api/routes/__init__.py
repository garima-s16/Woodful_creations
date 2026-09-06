from app.modules.auth.api import auth as auth
from app.api.routes import settings
from app.modules.procurement.api import suppliers
from app.modules.inventory.api import materials
from app.modules.inventory.api import material_categories
from app.modules.catalog.api import products
from app.modules.catalog.api import product_imports
from app.modules.inventory.api import material_imports
from app.modules.hr.api import holiday_imports
from app.modules.clients.api import import_routes as client_imports
from app.modules.catalog.api import rate_cards
from app.modules.catalog.api import rate_card_imports
from app.modules.clients.api import product_rate_routes as client_product_rates
from app.modules.procurement.api import supplier_materials
from app.modules.inventory.api import locations
from app.modules.communications.api import notifications
from app.modules.inventory.api import stock_transactions
from app.modules.procurement.api import purchase_imports
from app.modules.procurement.api import personal_cart
from app.modules.procurement.api import purchases
from app.modules.procurement.api import procurement_requirements
from app.modules.operations.api import issues
from app.modules.clients.api import routes as clients
from app.modules.clients.api import activity_routes as client_activities
from app.modules.reporting.api import search
from app.modules.sales.api import orders
from app.modules.sales.api import order_imports
from app.modules.sales.api import payments
from app.modules.operations.api import project_expenses
from app.modules.hr.api import employees
from app.modules.hr.api import attendance
from app.modules.hr.api import leaves
from app.modules.operations.api import daily_tasks
from app.modules.operations.api import production_jobs
from app.modules.operations.api import production_operations
from app.modules.operations.api import work_centres
from app.modules.operations.api import cutting_requirements
from app.modules.reporting.api import dashboard
from app.modules.reporting.api import business_decisions
from app.modules.inventory.api import reports as reports_inventory
from app.modules.sales.api import reports as reports_sales
from app.modules.hr.api import reports as reports_hr
from app.modules.operations.api import reports as reports_operations
from app.modules.clients.api import reports as reports_clients
from app.modules.catalog.api import reports as reports_catalog
from app.modules.sales.api import estimates
from app.modules.sales.api import estimate_imports
from app.modules.recruitment.api import candidates
from app.modules.recruitment.api import interviews
from app.modules.hr.api import salary_slips
from app.modules.hr.api import salary_advances
from app.modules.ai.api import chat
from app.modules.auth.api import users as users
from app.api.routes import audit_logs
from app.modules.hr.api import working_calendar
from app.modules.operations.api import milestones
from app.modules.documents.api import routes as documents
from app.modules.ai.api import agents
from app.modules.communications.api import automation
from app.modules.communications.api import communication
from app.modules.reporting.api import analytics

all_routers = [
    auth.router,
    settings.router,
    suppliers.router,
    materials.router,
    material_categories.router,
    products.router,
    product_imports.router,
    material_imports.router,
    holiday_imports.router,
    client_imports.router,
    rate_cards.router,
    rate_card_imports.router,
    client_product_rates.router,
    supplier_materials.router,
    locations.router,
    notifications.router,
    stock_transactions.router,
    purchase_imports.router,
    personal_cart.router,
    purchases.router,
    procurement_requirements.router,
    issues.router,
    clients.router,
    client_activities.router,
    search.router,
    orders.router,
    order_imports.router,
    payments.router,
    project_expenses.router,
    employees.router,
    attendance.router,
    leaves.router,
    daily_tasks.router,
    production_jobs.router,
    production_operations.router,
    work_centres.router,
    cutting_requirements.router,
    dashboard.router,
    business_decisions.router,
    reports_inventory.router,
    reports_sales.router,
    reports_hr.router,
    reports_operations.router,
    reports_clients.router,
    reports_catalog.router,
    estimates.router,
    estimate_imports.router,
    candidates.router,
    interviews.router,
    salary_slips.router,
    salary_advances.router,
    chat.router,
    users.router,
    audit_logs.router,
    working_calendar.router,
    milestones.router,
    documents.router,
    agents.router,
    automation.router,
    communication.router,
    analytics.router,
]
