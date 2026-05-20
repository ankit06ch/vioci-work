"""Server configuration from environment."""

from __future__ import annotations

import os

# JWT — override in production
JWT_SECRET = os.environ.get("VIOCI_JWT_SECRET", "dev-change-me-in-production-vioci-2026")
JWT_ALGORITHM = "HS256"
JWT_EXPIRE_HOURS = int(os.environ.get("VIOCI_JWT_EXPIRE_HOURS", "168"))

def auth_disabled() -> bool:
    """Read at call time so pytest monkeypatch works."""
    return os.environ.get("VIOCI_AUTH_DISABLED", "").lower() in ("1", "true", "yes")
