from app.api.routes import settings
from app.api.routes import suppliers
from app.api.routes import materials
from app.api.routes import purchases
from app.api.routes import issues
from app.api.routes import orders
from app.api.routes import payments
from app.api.routes import clients
from app.api.routes import reports

all_routers = [
    settings.router,
    suppliers.router,
    materials.router,
    purchases.router,
    issues.router,
    orders.router,
    payments.router,
    clients.router,
    reports.router,
]
