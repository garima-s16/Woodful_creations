ROLE_PERMISSIONS = {
    "master": ["view_all", "edit_all", "delete_all", "manage_users", "view_payments", "view_employees"],
    "manager": ["view_all", "edit_own", "manage_inventory", "create_estimates"],
    "employee": ["view_own", "edit_own", "log_attendance"],
    "user": ["view_limited", "create_orders"]
}

STATUS_CHOICES = {
    "estimate": ["draft", "sent", "approved", "rejected", "completed"],
    "project": ["pending", "in_progress", "on_hold", "completed", "cancelled"],
    "payment": ["pending", "partial", "completed", "failed", "refunded"],
    "interview": ["scheduled", "completed", "rescheduled", "cancelled"],
    "stock": ["available", "reserved", "damaged", "returned"]
}

ALERT_TYPES = {
    "LOW_STOCK": "Material stock below minimum quantity",
    "ETA_NEARING": "Delivery deadline approaching within 7 days",
    "PAYMENT_DUE": "Payment due from client",
    "OVERDUE_PAYMENT": "Payment overdue from client",
    "LOW_INVENTORY_VALUE": "Total inventory value low",
    "PENDING_APPROVAL": "Estimate pending approval"
}

USER_ROLES = ["master", "manager", "employee", "user"]
DEFAULT_ROLE = "user"
MASTER_ROLE = "master"

PAGINATION = {
    "DEFAULT_LIMIT": 20,
    "MAX_LIMIT": 100,
    "DEFAULT_OFFSET": 0
}

GST_RATE = 18.0
DEFAULT_PAYMENT_TERMS = "Net 30"
DEFAULT_ESTIMATE_VALIDITY_DAYS = 30