from app.api.routes import auth
from app.api.routes import clients
from app.api.routes import client_project
from app.api.routes import inventory
from app.api.routes import estimate
from app.api.routes import attendance
from app.api.routes import employee
from app.api.routes import candidate
from app.api.routes import interview
from app.api.routes import salary_slip
from app.api.routes import payments
from app.api.routes import settings
from app.api.routes import chat
from app.api.routes import dashboard

all_routers = [
    auth.router,
    clients.router,
    client_project.router,
    inventory.router,
    estimate.router,
    attendance.router,
    employee.router,
    candidate.router,
    interview.router,
    salary_slip.router,
    payments.router,
    settings.router,
    chat.router,
    dashboard.router,
]
