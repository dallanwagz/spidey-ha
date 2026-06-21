"""Fixtures for the Sphero Spider-Man tests.

The integration tests (test_config_flow.py) require the Home Assistant test harness
(`pytest-homeassistant-custom-component`) and Python <= 3.13. The pure-protocol tests in
test_protocol.py have no such dependency and run anywhere — so the HA plugin/fixtures are
only wired up when the harness is actually installed.
"""
import importlib.util

if importlib.util.find_spec("pytest_homeassistant_custom_component") is not None:
    import pytest

    pytest_plugins = ["pytest_homeassistant_custom_component"]

    @pytest.fixture(autouse=True)
    def auto_enable_custom_integrations(enable_custom_integrations):
        """Enable loading the custom integration in tests."""
        yield
