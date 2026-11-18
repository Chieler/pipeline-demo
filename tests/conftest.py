import pytest


@pytest.fixture(autouse=True)
def no_live_background_models(monkeypatch):
    """Tests must never start real CLI agents or spend model quota."""
    monkeypatch.setenv("TRACKB_AUTO_REVIEW", "0")
