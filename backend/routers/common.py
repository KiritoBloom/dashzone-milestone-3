"""Helpers shared by the routers.

date_range: the default reporting window is the last 30 days up to today.
Endpoints that take ?from= and ?to= query parameters use it so the window
is the same everywhere.
"""

from datetime import date, timedelta
from typing import Optional


def date_range(from_date: Optional[date], to_date: Optional[date]):
    """(start, end) for a report, defaulting to the last 30 days."""
    today = date.today()
    return (from_date or today - timedelta(days=30), to_date or today)
