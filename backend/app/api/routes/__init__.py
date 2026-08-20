from app.api.routes import auth
from app.api.routes import settings
from app.api.routes import suppliers
from app.api.routes import materials
from app.api.routes import material_categories
from app.api.routes import supplier_materials
from app.api.routes import locations
from app.api.routes import notifications
from app.api.routes import stock_transactions
from app.api.routes import purchase_imports
from app.api.routes import personal_cart
from app.api.routes import purchases
from app.api.routes import issues
from app.api.routes import clients
from app.api.routes import client_activities
from app.api.routes import search
from app.api.routes import orders
from app.api.routes import payments
from app.api.routes import project_expenses
from app.api.routes import employees
from app.api.routes import attendance
from app.api.routes import leaves
from app.api.routes import daily_tasks
from app.api.routes import production_jobs
from app.api.routes import dashboard
from app.api.routes import reports
from app.api.routes import estimates
from app.api.routes import candidates
from app.api.routes import interviews
from app.api.routes import salary_slips
from app.api.routes import chat
from app.api.routes import users
from app.api.routes import audit_logs
from app.api.routes import working_calendar
from app.api.routes import milestones
from app.api.routes import documents
from app.api.routes import agents
from app.api.routes import integrations
from app.api.routes import automation
from app.api.routes import communication
from app.api.routes import analytics
from app.api.routes import product_categories
from app.api.routes import products
from app.api.routes import product_imports
from app.api.routes import demo_reset

all_routers = [
    auth.router,
    settings.router,
    suppliers.router,
    materials.router,
    material_categories.router,
    supplier_materials.router,
    locations.router,
    notifications.router,
    stock_transactions.router,
    purchase_imports.router,
    personal_cart.router,
    purchases.router,
    issues.router,
    clients.router,
    client_activities.router,
    search.router,
    orders.router,
    payments.router,
    project_expenses.router,
    employees.router,
    attendance.router,
    leaves.router,
    daily_tasks.router,
    production_jobs.router,
    dashboard.router,
    reports.router,
    estimates.router,
    candidates.router,
    interviews.router,
    salary_slips.router,
    chat.router,
    users.router,
    audit_logs.router,
    working_calendar.router,
    milestones.router,
    documents.router,
    agents.router,
    integrations.router,
    automation.router,
    communication.router,
    analytics.router,
    product_categories.router,
    products.router,
    product_imports.router,
    demo_reset.router,
]
