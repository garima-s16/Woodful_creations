from datetime import datetime, timedelta
from typing import List, Dict, Any
import math

def paginate(items: List[Any], offset: int = 0, limit: int = 20) -> Dict:
    total = len(items)
    pages = math.ceil(total / limit) if limit > 0 else 1
    current_page = (offset // limit) + 1 if limit > 0 else 1
    
    return {
        "data": items[offset:offset + limit],
        "total": total,
        "offset": offset,
        "limit": limit,
        "current_page": current_page,
        "total_pages": pages
    }

def calculate_days_until(target_date: datetime) -> int:
    return (target_date - datetime.utcnow()).days

def format_currency(amount: float, currency: str = "Rs") -> str:
    return f"{currency} {amount:,.2f}"

def generate_estimate_number() -> str:
    timestamp = datetime.utcnow()
    return f"EST-{timestamp.strftime('%Y%m%d%H%M%S')}"

def generate_invoice_number() -> str:
    timestamp = datetime.utcnow()
    return f"INV-{timestamp.strftime('%Y%m%d%H%M%S')}"

def calculate_gst(amount: float, gst_rate: float = 18.0) -> Dict:
    gst_amount = amount * (gst_rate / 100)
    total = amount + gst_amount
    return {
        "subtotal": amount,
        "gst_rate": gst_rate,
        "gst_amount": round(gst_amount, 2),
        "total": round(total, 2)
    }

def calculate_discount(amount: float, discount_percent: float) -> Dict:
    discount_amount = amount * (discount_percent / 100)
    final_amount = amount - discount_amount
    return {
        "original_amount": amount,
        "discount_percent": discount_percent,
        "discount_amount": round(discount_amount, 2),
        "final_amount": round(final_amount, 2)
    }

def format_datetime(dt: datetime, format_str: str = "%d-%m-%Y %H:%M:%S") -> str:
    return dt.strftime(format_str)

def get_week_date_range() -> tuple:
    today = datetime.utcnow()
    monday = today - timedelta(days=today.weekday())
    sunday = monday + timedelta(days=6)
    return monday, sunday

def get_month_date_range(year: int = None, month: int = None) -> tuple:
    if not year:
        year = datetime.utcnow().year
    if not month:
        month = datetime.utcnow().month
    
    first_day = datetime(year, month, 1)
    if month == 12:
        last_day = datetime(year + 1, 1, 1) - timedelta(days=1)
    else:
        last_day = datetime(year, month + 1, 1) - timedelta(days=1)
    
    return first_day, last_day