"""Smoke test: the Streamlit dashboard renders without errors."""
import pytest
from streamlit.testing.v1 import AppTest

from src import config

APP = config.ROOT / "app" / "app.py"


@pytest.mark.skipif(not config.WAREHOUSE.exists(), reason="warehouse not built yet; run `make all`")
def test_dashboard_renders():
    app = AppTest.from_file(str(APP), default_timeout=60).run()
    assert not app.exception
    assert any("Recommendation" in s.value for s in [*app.success, *app.warning])
    assert len(app.metric) == 8
