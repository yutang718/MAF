import re
from datetime import datetime, timezone
from typing import Any

_FRACTION = re.compile(r"(\.\d{1,6})\d*")


def parse_time(value: Any) -> datetime | None:
    """Lenient ISO-8601 / epoch parse. Always aware UTC; None when empty or unparseable."""
    if value is None or value == "":
        return None
    if isinstance(value, datetime):
        return value if value.tzinfo else value.replace(tzinfo=timezone.utc)
    if isinstance(value, (int, float)):
        # GitHub's audit log uses epoch milliseconds.
        seconds = value / 1000 if value > 1e11 else value
        return datetime.fromtimestamp(seconds, timezone.utc)
    if not isinstance(value, str):
        return None
    text = value.strip().replace("Z", "+00:00")
    # Python 3.10's fromisoformat takes at most six fractional digits; Graph sends seven.
    text = _FRACTION.sub(r"\1", text, count=1)
    if " " in text and "T" not in text:
        text = text.replace(" ", "T", 1)
    try:
        dt = datetime.fromisoformat(text)
    except ValueError:
        return None
    return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)


def iso(dt: datetime | None) -> str | None:
    return dt.astimezone(timezone.utc).isoformat().replace("+00:00", "Z") if dt else None


def utcnow() -> datetime:
    return datetime.now(timezone.utc)
