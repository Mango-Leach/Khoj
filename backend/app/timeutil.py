from __future__ import annotations

from datetime import datetime, timezone


def utcnow() -> datetime:
    """Timezone-aware UTC now. Tests patch this to move the clock."""
    return datetime.now(timezone.utc)


def ensure_aware(value: datetime) -> datetime:
    """MongoDB can hand back naive datetimes; they are always UTC here."""
    return value if value.tzinfo is not None else value.replace(tzinfo=timezone.utc)
