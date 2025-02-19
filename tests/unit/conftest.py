#!/usr/bin/python3
"""Configurations for tests."""
import pathlib
import subprocess
import unittest.mock as mock

import pytest


@pytest.fixture
def mock_layers(monkeypatch):
    """Layers mock."""
    import sys

    sys.modules["charms"] = mock.MagicMock()
    sys.modules["charms.layer"] = mock.MagicMock()
    sys.modules["charms.reactive"] = mock.MagicMock()


@pytest.fixture
def mock_hookenv_config(monkeypatch):
    """Hookenv mock."""
    import yaml

    def mock_config():
        cfg = {}
        yml = yaml.safe_load(open("./config.yaml"))

        # Load all defaults
        for key, value in yml["options"].items():
            cfg[key] = value["default"]

        # Manually add cfg from other layers
        # cfg['my-other-layer'] = 'mock'
        return cfg

    monkeypatch.setattr("advanced_routing_helper.hookenv.config", mock_config)


@pytest.fixture
def mock_remote_unit(monkeypatch):
    """Remote unit mock."""
    monkeypatch.setattr("advanced_routing_helper.hookenv.remote_unit", lambda: "unit-mock/0")


@pytest.fixture
def mock_charm_dir(monkeypatch):
    """Charm dir mock."""
    monkeypatch.setattr("advanced_routing_helper.hookenv.charm_dir", lambda: "/mock/charm/dir")


@pytest.fixture
def advanced_routing_helper(mock_layers, tmpdir, mock_hookenv_config, mock_charm_dir, monkeypatch):
    """Routing fixture."""
    from advanced_routing_helper import AdvancedRoutingHelper

    AdvancedRoutingHelper.common_location = pathlib.Path("/tmp/test/charm-advanced-routing")
    helper = AdvancedRoutingHelper()
    monkeypatch.setattr("advanced_routing_helper.AdvancedRoutingHelper", lambda: helper)

    return helper


@pytest.fixture
def mock_check_call(monkeypatch):
    """Requests.get() mocked to return {'mock_key':'mock_response'}."""

    def mock_get(*args, **kwargs):
        return True

    monkeypatch.setattr(subprocess, "check_call", mock_get)
