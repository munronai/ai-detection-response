"""Pytest configuration for AIDR test suite."""

import pytest
from app.config import settings


@pytest.fixture(autouse=True)
def force_simulated_mode_for_tests():
    """Ensures unit and integration tests run in offline deterministic simulated mode."""
    prev_mode = settings.jev_mode
    settings.jev_mode = "simulated"
    yield
    settings.jev_mode = prev_mode
