from server.state import _postgres_connect_args


def test_postgres_connect_args_disables_prepare_for_pooler():
    url = "postgresql+psycopg://user:pass@aws.pooler.supabase.com:6543/postgres"
    args = _postgres_connect_args(url)
    assert args["prepare_threshold"] is None
    assert args["sslmode"] == "require"


def test_postgres_connect_args_respects_sslmode_in_url():
    url = "postgresql+psycopg://localhost/db?sslmode=disable"
    args = _postgres_connect_args(url)
    assert "sslmode" not in args
