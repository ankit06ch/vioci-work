#!/usr/bin/env python3
"""Verify cloud .env settings and initialize database tables."""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from server.cloud_files import cloud_storage_enabled  # noqa: E402
from server.settings import get_server_settings  # noqa: E402
from server.state import init_db, get_engine  # noqa: E402


def main() -> int:
    s = get_server_settings()
    if not s.database_url:
        print("VIOCI_DATABASE_URL is not set — running in local SQLite mode.")
        print("See docs/cloud-setup.md to enable Supabase.")
        return 0

    print("Connecting to cloud database…")
    init_db()
    engine = get_engine()
    with engine.connect() as conn:
        conn.execute(__import__("sqlalchemy").text("SELECT 1"))
    print("Database OK (tables created if missing).")

    if cloud_storage_enabled():
        from server.cloud_files import _client, _bucket

        bucket = _bucket()
        try:
            _client().storage.from_(bucket).list("")
            print(f"Storage OK (bucket '{bucket}').")
        except Exception as e:
            print(f"Storage check failed: {e}")
            print(f"Create a private bucket named '{bucket}' in the Supabase dashboard.")
            return 1
    else:
        print("Storage not configured (optional). Set VIOCI_SUPABASE_URL + SERVICE_ROLE_KEY.")

    print("Cloud setup looks good.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
