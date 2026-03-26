"""Datetime utilities with local timezone support."""
from datetime import datetime, timezone
from zoneinfo import ZoneInfo

# Brazil timezone (São Paulo)
LOCAL_TZ = ZoneInfo("America/Sao_Paulo")


def now_local() -> datetime:
    """Get current datetime in local timezone (São Paulo, Brazil).
    
    Returns a timezone-aware datetime object in local time.
    """
    return datetime.now(LOCAL_TZ)


def now_utc() -> datetime:
    """Get current datetime in UTC timezone.
    
    Returns a timezone-aware datetime object in UTC.
    """
    return datetime.now(timezone.utc)


def to_local(dt: datetime | None) -> datetime | None:
    """Convert a datetime to local timezone.
    
    Args:
        dt: datetime object (naive or aware)
    
    Returns:
        timezone-aware datetime in local timezone, or None if input is None
    """
    if dt is None:
        return None
    
    if dt.tzinfo is None:
        # Assume UTC if naive
        dt = dt.replace(tzinfo=timezone.utc)
    
    return dt.astimezone(LOCAL_TZ)


def format_local(dt: datetime | None, fmt: str = "%d/%m/%Y %H:%M:%S") -> str:
    """Format a datetime in local timezone.
    
    Args:
        dt: datetime object
        fmt: format string
    
    Returns:
        formatted string in local timezone
    """
    if dt is None:
        return "—"
    
    local_dt = to_local(dt)
    return local_dt.strftime(fmt)
