"""Main module for functional testing."""

import json
import os
import time

import cfg_opts
import jubilant
import pytest

SERIES = [
    "noble",
    "jammy",
    "focal",
    "resolute",
]

# Juju 3.x uses bases instead of series names.
SERIES_TO_BASE = {
    "noble": "ubuntu@24.04",
    "jammy": "ubuntu@22.04",
    "focal": "ubuntu@20.04",
}

############
# FIXTURES #
############


@pytest.fixture(scope="module", params=SERIES)
def deploy_app(request, juju):
    """Deploy the advanced-routing charm as a subordinate of ubuntu.

    Yields the application name of the deployed advanced-routing charm as a string.
    """
    release = request.param
    base = SERIES_TO_BASE[release]
    built_charm = os.getenv("CHARM_PATH_{}".format(release.upper()))
    ubuntu_app = "ubuntu-{}".format(release)
    routing_app = "advanced-routing-{}".format(release)

    juju.deploy(
        "ubuntu",
        ubuntu_app,
        base=base,
        channel="stable",
    )
    juju.deploy(
        built_charm,
        routing_app,
        base=base,
    )
    juju.integrate(ubuntu_app, routing_app)

    yield routing_app


@pytest.fixture(scope="module")
def unit(juju, deploy_app):
    """Return the advanced-routing unit name for the deployed app.

    The unit name is resolved once from the live model status after the app has
    been deployed.  Using a stable string avoids the fragile ``.pop()`` pattern
    of the old python-libjuju tests, which could exhaust the unit list across
    parametrized test calls.
    """
    status = juju.status()
    units = status.get_units(deploy_app)
    return next(iter(units))


#########
# TESTS #
#########


def test_deploy(deploy_app, juju):
    """Test the deployment reaches the expected blocked state."""
    juju.wait(
        lambda status: (
            status.apps.get(deploy_app) is not None
            and status.apps[deploy_app].is_blocked
            and all(
                u.workload_status.message == "Advanced routing is disabled"
                for u in status.get_units(deploy_app).values()
            )
        ),
        timeout=1200,
    )


@pytest.mark.parametrize(
    "cfg",
    [pytest.param(cfg, id="cfg-{}".format(i)) for i, cfg in enumerate(cfg_opts.JSON_CONFIGS)],
)
def test_juju_routing(cfg, file_contents, file_exists, deploy_app, unit, juju):
    """Test juju routing file contents with config."""
    json_config = cfg["input"]
    juju.config(
        deploy_app,
        {
            "advanced-routing-config": json.dumps(json_config),
            "enable-advanced-routing": "true",
            "action-managed-update": "false",
        },
    )

    juju.wait(
        lambda status: (
            status.apps.get(deploy_app) is not None
            and status.apps[deploy_app].is_active
            and all(
                u.juju_status.current == "idle" and u.workload_status.message == "Unit is ready"
                for u in status.get_units(deploy_app).values()
            )
        ),
        timeout=300,
    )

    # NOTE(gabrielcocenza) files might take more time to be rendered.
    time.sleep(10)

    common_path = "/usr/local/lib/juju-charm-advanced-routing"
    up_path = "{}/if-up/95-juju_routing".format(common_path)
    cleanup_path = "{}/cleanup/95-juju_routing".format(common_path)

    if_up_content = file_contents(up_path, unit)
    if_down_content = file_contents(cleanup_path, unit)

    assert cfg["expected_ifup"] == if_up_content
    assert cfg["expected_ifdown"] == if_down_content

    series = deploy_app.split("-")[-1]
    if series >= "xenial" or series < "bionic":
        ifup_path = "/etc/network/if-up.d"
    else:
        ifup_path = "/etc/networkd-dispatcher/routable.d"

    ifup_expected_file_path = "{}/95-juju_routing".format(ifup_path)
    assert file_exists(ifup_expected_file_path, unit) == "1\n"


def test_juju_routing_disable(file_exists, unit, deploy_app, juju):
    """Test juju routing file non-existence when conf disabled."""
    juju.config(deploy_app, {"enable-advanced-routing": "false"})
    juju.wait(
        lambda status: (
            status.apps.get(deploy_app) is not None
            and status.apps[deploy_app].is_blocked
            and all(
                u.workload_status.message == "Advanced routing is disabled"
                for u in status.get_units(deploy_app).values()
            )
        ),
        timeout=300,
    )

    series = deploy_app.split("-")[-1]
    if series >= "xenial" or series < "bionic":
        ifup_path = "/etc/network/if-up.d"
        ifdown_path = "/etc/network/if-down.d"
    else:
        ifup_path = "/etc/networkd-dispatcher/routable.d"
        ifdown_path = "/etc/networkd-dispatcher/off.d"

    for if_path in [ifup_path, ifdown_path]:
        filename = "{}/95-juju_routing".format(if_path)
        assert file_exists(filename, unit) == "0\n"


def test_apply_changes_disabled(deploy_app, unit, juju):
    """Test that the apply-changes action fails when advanced routing is disabled."""
    juju.config(
        deploy_app,
        {"enable-advanced-routing": "false", "action-managed-update": "true"},
    )
    with pytest.raises(jubilant.TaskError):
        juju.run(unit, "apply-changes")


def test_apply_changes(file_exists, deploy_app, unit, juju):
    """Test that the apply-changes action completes when advanced routing is enabled."""
    ifup_path = "/etc/networkd-dispatcher/routable.d"
    ifup_filename = "{}/95-juju_routing".format(ifup_path)

    # ifup file doesn't exist before running the action
    assert file_exists(ifup_filename, unit) == "0\n"

    juju.config(
        deploy_app,
        {"enable-advanced-routing": "true", "action-managed-update": "true"},
    )
    juju.run(unit, "apply-changes")
    # TaskError would have been raised on failure; reaching here means the action completed.

    # ifup file exists after running the action
    assert file_exists(ifup_filename, unit) == "1\n"
