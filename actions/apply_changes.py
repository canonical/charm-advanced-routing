#!/usr/local/sbin/charm-env python3
"""apply-changes action."""

import sys
import traceback

from advanced_routing_helper import AdvancedRoutingHelper, PolicyRoutingExists
from charmhelpers.core import unitdata
from charmhelpers.core.hookenv import action_fail, action_set
from charms.layer import status
from charms.reactive import is_flag_set, set_flag
from routing_validator import RoutingConfigValidatorError

try:
    advanced_routing = AdvancedRoutingHelper()
except PolicyRoutingExists:
    status.blocked("Please disable charm-policy-routing")
    action_fail("Disable charm-policy-routing and run again the action.")
    sys.exit(0)


def apply_config():
    """Set if-up/down/netplan scripts and run them."""
    status.maintenance("Installing routes")
    try:
        advanced_routing.setup()
        advanced_routing.apply_config()
        return True
    except RoutingConfigValidatorError:
        print(traceback.format_exc(), file=sys.stderr)
        status.blocked("Route config validation failed.")
        return False


def action():
    """Run action flow."""
    if not advanced_routing.is_advanced_routing_enabled:
        # Juju status is already set by the reactive script
        action_fail("Charm is not enabled.")
        sys.exit(0)

    initialized = is_flag_set("advanced-routing.installed")
    if initialized:
        status.maintenance("Removing routes")
        advanced_routing.remove_routes()

    if not apply_config():
        # Juju status is already set by apply_config()
        action_fail("Routing changes could not be applied.")
        sys.exit(0)

    if not initialized:
        set_flag("advanced-routing.installed")

    status.active("Unit is ready")
    action_set({"message": "Routing changes applied."})
    # Flags aren't auto-committed outside of hook contexts, so commit them.
    unitdata.kv().flush()


if __name__ == "__main__":
    action()
