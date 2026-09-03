from datetime import datetime
from typing import Optional


def format_currency(amount: float, currency: str = "USD") -> str:
    """Format numeric float amount as formatted currency string."""
    return f"{currency} {amount:,.2f}"


def get_utc_now() -> datetime:
    """Get current UTC timestamp."""
    return datetime.utcnow()
