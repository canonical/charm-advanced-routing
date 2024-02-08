"""Reactive charm hooks."""

import sys

from advanced_routing_helper import AdvancedRoutingHelper, PolicyRoutingExists

from charms.layer import status
from charms.reactive import clear_flag, set_flag, when, when_not

from routing_validator import RoutingConfigValidatorError


try:
    advanced_routing = AdvancedRoutingHelper()
except PolicyRoutingExists as error:
    status.blocked(str(error))
    sys.exit(0)


def apply_config():
    """Set if-up/down scripts and run them."""
    status.maintenance("Installing routes")
    try:
        advanced_routing.setup()
        advanced_routing.apply_config()
        return True
    except RoutingConfigValidatorError as error:
        status.blocked(str(error))
        return False


@when_not("advanced-routing.installed")
def install_routing():
    """Install the charm."""
    if not advanced_routing.is_advanced_routing_enabled:
        status.blocked("Advanced routing is disabled")
        return

    if advanced_routing.is_action_managed:
        status.blocked("Changes pending via apply-changes action")
        return

    if not apply_config():
        return

    set_flag("advanced-routing.installed")
    status.active("Unit is ready")


@when("advanced-routing.installed")
@when("config.changed")
def reconfigure_routing():
    """Handle routing configuration change."""
    if advanced_routing.is_action_managed:
        status.blocked("Changes pending via apply-changes action")
        return

    status.maintenance("Removing routes")
    advanced_routing.remove_routes()
    if not advanced_routing.is_advanced_routing_enabled:
        clear_flag("advanced-routing.installed")
        return

    if not apply_config():
        return

    status.active("Unit is ready")
