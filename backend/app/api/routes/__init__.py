from app.api.routes import auth
from app.api.routes import settings
from app.api.routes import suppliers
from app.api.routes import materials
from app.api.routes import purchases
from app.api.routes import issues
from app.api.routes import clients
from app.api.routes import orders
from app.api.routes import payments
from app.api.routes import project_expenses
from app.api.routes import employees
from app.api.routes import attendance
from app.api.routes import daily_tasks
from app.api.routes import production_jobs
from app.api.routes import dashboard

all_routers = [
    auth.router,
    settings.router,
    suppliers.router,
    materials.router,
    purchases.router,
    issues.router,
    clients.router,
    orders.router,
    payments.router,
    project_expenses.router,
    employees.router,
    attendance.router,
    daily_tasks.router,
    production_jobs.router,
    dashboard.router,
]
