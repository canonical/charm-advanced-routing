"""Routing module."""

import errno
import os
import pathlib
import subprocess

from charmhelpers.core import hookenv
from charmhelpers.core.host import CompareHostReleases, lsb_release

from routing_entry import RoutingEntryType

from routing_validator import RoutingConfigValidator


class PolicyRoutingExists(Exception):
    """Old charm-policy-routing configuration is in place."""

    pass


class AdvancedRoutingHelper:
    """Helper class for routing."""

    routing_script_name = "95-juju_routing"
    common_location = pathlib.Path("/usr/local/lib/juju-charm-advanced-routing")
    net_tools_up_dir_path = pathlib.Path("/etc/network/if-up.d")
    netplan_up_dir_path = pathlib.Path("/etc/networkd-dispatcher/routable.d")
    policy_routing_service_dir_path = pathlib.Path("/etc/systemd/system")
    table_name_path = pathlib.Path("/etc/iproute2/rt_tables.d/juju-managed.conf")
    networkd_conf_path = pathlib.Path("/usr/lib/systemd/networkd.conf.d/95-juju-networkd.conf")

    def __init__(self):
        """Init function."""
        hookenv.log("Init {}".format(self.__class__.__name__), level=hookenv.INFO)
        self.common_ifup_path = self.common_location / "if-up" / self.routing_script_name
        self.common_cleanup_path = self.common_location / "cleanup" / self.routing_script_name
        self.charm_config = hookenv.config()
        self.pre_setup()

    @property
    def is_advanced_routing_enabled(self):
        """Return boolean according to Juju config input."""
        return self.charm_config["enable-advanced-routing"]

    @property
    def is_action_managed(self):
        """Return boolean according to Juju config input."""
        return self.charm_config["action-managed-update"]

    def pre_setup(self):
        """Create folder path for the ifup/cleanup scripts."""
        for script_path in [self.common_ifup_path, self.common_cleanup_path]:
            script_path_parent = script_path.parent
            if not script_path_parent.exists():
                script_path_parent.mkdir(parents=True)
                hookenv.log("Created {}".format(script_path_parent), level=hookenv.INFO)

        # check for service file of charm-policy-routing, and block if its present
        policy_routing_svcname = "charm-pre-install-policy-routing.service"
        policy_routing_file = self.policy_routing_service_dir_path / policy_routing_svcname
        if policy_routing_file.exists():
            hookenv.log(
                "It looks like charm-policy-routing is enabled."
                " charm-pre-install-policy-routing.service",
                hookenv.ERROR,
            )
            raise PolicyRoutingExists("Please disable charm-policy-routing")

    def post_setup(self):
        """Symlinks the up script from the if.up or routable.d location."""
        hookenv.log("Symlinking into distro specific network manager", level=hookenv.INFO)
        self.symlink_force(str(self.common_ifup_path), str(self.etc_ifup_path))

    def setup(self):
        """Modify the interfaces configurations."""
        # Validate configuration options first
        routing_validator = RoutingConfigValidator()
        routing_validator.read_configurations(self.charm_config["advanced-routing-config"])
        routing_validator.verify_config()

        hookenv.log("Writing {}".format(self.common_ifup_path), level=hookenv.INFO)
        # Modify if-up.d
        with open(str(self.common_ifup_path), "w") as ifup_file:
            ifup_file.write("#!/bin/sh\n# This file is managed by Juju.\nip route flush cache\n")
            for entry in RoutingEntryType.entries:
                ifup_file.write(entry.addline)
        os.chmod(str(self.common_ifup_path), 0o755)

        hookenv.log("Writing {}".format(self.common_cleanup_path), level=hookenv.INFO)
        with open(str(self.common_cleanup_path), "w") as cleanup_file:
            cleanup_file.write("#!/bin/sh\n# This file is managed by Juju.\n")
            for entry in list(reversed(RoutingEntryType.entries)):
                cleanup_file.write(entry.removeline)
            cleanup_file.write("ip route flush cache\n")
        os.chmod(str(self.common_cleanup_path), 0o755)

        self.setup_persistent_rules()
        self.post_setup()

    def apply_config(self):
        """Apply the new routes to the system."""
        hookenv.log("Applying routing rules", level=hookenv.INFO)
        for entry in RoutingEntryType.entries:
            entry.apply()

    def remove_routes(self):
        """Cleanup job."""
        hookenv.log("Removing routing rules", level=hookenv.INFO)
        if self.common_cleanup_path.is_file():
            try:
                subprocess.check_call(["sh", "-c", str(self.common_cleanup_path)])
            except subprocess.CalledProcessError as err:
                # Either rules are removed or not valid
                hookenv.log(
                    "cleanup script {} failed. Maybe rules are already "
                    "gone? Error: {}".format(self.common_cleanup_path, err),
                    hookenv.WARNING,
                )

        # remove symlinks, start/stop scripts and iproute2 table name
        filelist = [
            self.common_ifup_path,
            self.common_cleanup_path,
            self.table_name_path,
            self.etc_ifup_path,
        ]
        for filename in filelist:
            try:
                filename.unlink()
            except FileNotFoundError as err:
                hookenv.log("Nothing to clean up: {}".format(err), hookenv.DEBUG)

    def symlink_force(self, target, link_name):
        """Ensure accurate symlink by removing any existing links."""
        try:
            os.symlink(target, link_name)
        except OSError as e:
            if e.errno == errno.EEXIST:
                os.remove(link_name)
                os.symlink(target, link_name)
            else:
                raise e

    def setup_persistent_rules(self):
        """Modify systemd config to not delete foreign rules."""
        hookenv.log("Changing networkd configuration", level=hookenv.INFO)
        conf_parent = self.networkd_conf_path.parent
        if not conf_parent.exists():
            conf_parent.mkdir(parents=True)
            hookenv.log("Created {}".format(conf_parent), level=hookenv.INFO)
        config = (
            "# This file is managed by Juju.\n"
            "[Network]\n"
            "ManageForeignRoutingPolicyRules=no\n"
            "ManageForeignRoutes=no\n"
        )
        with open(str(self.networkd_conf_path), "w") as config_file:
            config_file.write(config)

    @property
    def etc_ifup_path(self):
        """Return path to ifup etc folder based on series."""
        release = lsb_release()["DISTRIB_CODENAME"].lower()
        if CompareHostReleases(release) < "bionic":
            ifup_dir_path = self.net_tools_up_dir_path
        else:
            ifup_dir_path = self.netplan_up_dir_path
        ifup_path = ifup_dir_path / self.routing_script_name
        return ifup_path
