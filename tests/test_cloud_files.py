from __future__ import annotations

import types


def test_supabase_client_cache_does_not_return_factory_function(monkeypatch):
    import server.cloud_files as cloud_files

    fake_client = object()

    def fake_create_client(url: str, key: str):
        assert url == "https://example.supabase.co"
        assert key == "service-role"
        return fake_client

    monkeypatch.setattr(cloud_files, "_cached_client", None)
    monkeypatch.setattr(
        cloud_files,
        "get_server_settings",
        lambda: types.SimpleNamespace(
            supabase_url="https://example.supabase.co",
            supabase_service_role_key="service-role",
            supabase_bucket="vioci",
        ),
    )
    monkeypatch.setitem(
        __import__("sys").modules,
        "supabase",
        types.SimpleNamespace(create_client=fake_create_client),
    )

    assert cloud_files._client() is fake_client
    assert cloud_files._client() is fake_client
