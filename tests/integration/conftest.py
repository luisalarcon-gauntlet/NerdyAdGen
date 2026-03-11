"""Integration test fixtures: real test DB, run migrations, mocked APIs."""
import os

import pytest

from src.config.settings import get_settings


def _get_test_settings():
    try:
        return get_settings()
    except Exception:
        return None


@pytest.fixture(scope="module")
def test_db_url():
    """Require database_url_test for integration tests."""
    settings = _get_test_settings()
    if not settings or not getattr(settings, "database_url_test", None):
        pytest.skip("DATABASE_URL_TEST not set — skip integration tests")
    return settings.database_url_test


@pytest.fixture(scope="module")
def run_migrations(test_db_url):
    """Run Alembic migrations against test DB. Set DATABASE_URL so env.py uses test DB."""
    import src.config.settings as settings_mod
    old_url = os.environ.get("DATABASE_URL")
    old_cache = getattr(settings_mod, "_settings", None)
    os.environ["DATABASE_URL"] = test_db_url
    settings_mod._settings = None
    try:
        from alembic import command
        from alembic.config import Config
        config = Config("alembic.ini")
        command.upgrade(config, "head")
        yield
        command.downgrade(config, "base")
    finally:
        settings_mod._settings = old_cache
        if old_url is not None:
            os.environ["DATABASE_URL"] = old_url
        else:
            os.environ.pop("DATABASE_URL", None)
