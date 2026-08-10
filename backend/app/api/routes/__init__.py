from app.api.routes import auth

all_routers = [
    auth.router,
]

# The remaining domain routers (materials, suppliers, purchases, issues,
# clients, orders, payments, project_expenses, employees, attendance,
# daily_tasks, production_jobs, settings, dashboard, chat) are being
# rebuilt against the new schema - see Milestone 2.
