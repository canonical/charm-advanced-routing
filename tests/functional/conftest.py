#!/usr/bin/python3
"""
Reusable pytest fixtures for functional testing.

Environment variables
---------------------

PYTEST_KEEP_MODEL:
    If set, the testing model won't be torn down at the end of the testing session.

PYTEST_CLOUD_NAME:
    Name of the cloud (and optionally region as ``cloud/region``) to use for the model.

PYTEST_CLOUD_REGION:
    Cloud region. If set alongside PYTEST_CLOUD_NAME, the two are combined as
    ``cloud/region`` when adding the model.

PYTEST_CLOUD_CREDENTIAL:
    Credential name to use when adding the model.
"""

import os
import uuid

import jubilant
import pytest


@pytest.fixture(scope="module")
def juju():
    """Create a temporary Juju model and yield a :class:`jubilant.Juju` instance.

    Destroys the model after the tests complete unless ``PYTEST_KEEP_MODEL`` is set.
    """
    model_name = "functest-{}".format(uuid.uuid4().hex[:12])
    cloud_name = os.getenv("PYTEST_CLOUD_NAME")
    cloud_region = os.getenv("PYTEST_CLOUD_REGION")
    credential = os.getenv("PYTEST_CLOUD_CREDENTIAL")
    cloud_arg = (
        "{}/{}".format(cloud_name, cloud_region) if cloud_name and cloud_region else cloud_name
    )

    juju = jubilant.Juju()
    juju.add_model(model_name, cloud=cloud_arg, credential=credential)
    yield juju
    if not os.getenv("PYTEST_KEEP_MODEL"):
        juju.destroy_model(model_name)


@pytest.fixture
def file_contents(juju):
    """Return the contents of a file on a remote unit.

    :param path: Absolute file path on the remote unit.
    :param unit: Unit name, e.g. ``advanced-routing-noble/0``.
    """

    def _file_contents(path, unit):
        return juju.exec("cat {}".format(path), unit=unit).stdout

    return _file_contents


@pytest.fixture
def file_exists(juju):
    """Return '1' or '0' (with trailing newline) based on whether a file exists on a remote unit.

    :param path: Absolute file path on the remote unit.
    :param unit: Unit name, e.g. ``advanced-routing-noble/0``.
    """

    def _file_exists(path, unit):
        return juju.exec('[ -f "{}" ] && echo 1 || echo 0'.format(path), unit=unit).stdout

    return _file_exists


@pytest.fixture
def reconfigure_app(juju):
    """Apply a config mapping to an application and wait for it to become active."""

    def _reconfigure_app(cfg, app):
        juju.config(app, cfg)
        juju.wait(
            lambda status: status.apps[app].is_active,
            timeout=300,
        )

    return _reconfigure_app
