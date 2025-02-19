"""RoutingValidator Class.

Validates the entire json configuration constructing a model.
"""

import ipaddress
import json
import pprint
import re

from charmhelpers.core import hookenv

import netifaces

from routing_entry import (
    RoutingEntryRoute,
    RoutingEntryRule,
    RoutingEntryTable,
    RoutingEntryType,
)

TABLE_NAME_PATTERN = r"[a-zA-Z0-9]+[a-zA-Z0-9-]*"
TABLE_NAME_PATTERN_RE = r"^{}$".format(TABLE_NAME_PATTERN)


class RoutingConfigValidatorError(Exception):
    """Validation error exception."""

    pass


class RoutingConfigValidator:
    """Validates the entire json configuration constructing model of rules."""

    def __init__(self):
        """Init function."""
        hookenv.log("Init {}".format(self.__class__.__name__), level=hookenv.INFO)

        self.pattern = re.compile(TABLE_NAME_PATTERN)
        self.tables = set([])
        self.config = []

    def read_configurations(self, conf):
        """Read and parse the JSON configuration file."""
        json_decoded = []

        if not conf:
            msg = "JSON data empty in charm config option 'advanced-routing-config'."
            self.report_error(msg)

        try:
            json_decoded = json.loads(conf)
            hookenv.log("Read json config from juju config", level=hookenv.INFO)
        except ValueError as err:
            msg = "JSON format invalid, conf: {}, Error: {}".format(conf, err)
            self.report_error(msg)

        self.config = json_decoded

    def verify_config(self):
        """Iterate entries in the config checking each type for sanity."""
        hookenv.log("Verifying json config", level=hookenv.INFO)
        type_order = ["table", "route", "rule"]

        dispatch_table = {
            "table": self.verify_table,
            "route": self.verify_route,
            "rule": self.verify_rule,
        }

        for entry_type in type_order:
            # get all the tables together first, so that we can provide strict relations
            for conf in self.config:
                try:
                    type = conf["type"]
                    verifier = dispatch_table[type]
                except KeyError as error:
                    msg = "Bad config: routing entry error, {}".format(error)
                    self.report_error(msg)

                if entry_type != type:
                    continue

                verifier(conf)

    def verify_table(self, conf):
        """Verify tables."""
        hookenv.log("Verifying table {}".format(pprint.pformat(conf)), level=hookenv.INFO)

        is_valid_name = self.pattern.match(conf["table"])
        if is_valid_name and conf["table"] not in self.tables:
            self.tables.add(conf["table"])
            RoutingEntryType.add_entry(RoutingEntryTable(conf))
            return

        if not is_valid_name:
            msg = "Bad network config: table name {} must match {}.".format(
                conf["table"], TABLE_NAME_PATTERN
            )
        else:
            msg = 'Bad network config: duplicate table name "{}"'.format(conf["table"])
        self.report_error(msg)

    def verify_route(self, conf):
        """Verify routes."""
        hookenv.log("Verifying route {}".format(pprint.pformat(conf)), level=hookenv.INFO)

        # Verify items in configuration
        self.verify_route_gateway(conf)
        self.verify_route_network(conf)
        table_exists = self.verify_route_table(conf)
        self.verify_route_default_route(conf, table_exists)
        self.verify_route_device(conf)
        self.verify_route_metric(conf)

        RoutingEntryType.add_entry(RoutingEntryRoute(conf))

    def verify_route_gateway(self, conf):
        """Verify route gateway in conf.

        "gateway" key is a required configuration parameter for default routes
        """
        if not conf.get("default_route"):
            return
        try:
            ipaddress.ip_address(conf["gateway"])
            return
        except KeyError:
            msg = "Bad network config: routing entries need the 'gateway' def"
        except ValueError as error:
            msg = "Bad gateway IP: {} - {}".format(conf["gateway"], error)
        self.report_error(msg)

    def verify_route_network(self, conf):
        """Verify route network in conf.

        "net" key is a required configuration parameter.
        """
        try:
            ipaddress.ip_network(conf["net"])
            return
        except KeyError:
            if "default_route" in conf:
                return
            msg = "Bad network config: routing entries need the 'net' def"
        except ValueError as error:
            msg = "Bad network config: {} - {}".format(conf["net"], error)
        self.report_error(msg)

    def verify_route_table(self, conf):
        """Verify route table in conf.

        "table" key is an optional configuration parameter.
        """
        try:
            is_valid_name = self.pattern.match(conf["table"])
            if is_valid_name and conf["table"] in self.tables:
                return True

            if not is_valid_name:
                msg = "Bad network config: table name {} must match {} in {}".format(
                    conf["table"], TABLE_NAME_PATTERN, conf
                )
            else:
                msg = "Bad network config: table {} reference not defined".format(conf["table"])
            self.report_error(msg)
        except KeyError:
            # key is optional
            return False

    def verify_route_default_route(self, conf, table_exists):
        """Verify route default route.

        "default_route" is an optional configuration parameter. However, if it is
        defined, the "table" key will also need to be defined, and not be the main
        routing table.
        """
        try:
            is_valid_bool_value = isinstance(conf["default_route"], bool)
            if is_valid_bool_value and table_exists and conf["table"] != "main":
                return

            if not is_valid_bool_value:
                msg = "Bad network config: default_route should be bool in {}".format(conf)
            elif not table_exists:
                msg = "Bad network config: Key 'table' missing in " "default route {}".format(conf)
            else:
                msg = (
                    "Bad network config: Key 'table' cannot be 'main' in "
                    "default route {}".format(conf)
                )
            self.report_error(msg)
        except KeyError:
            # key is mutually exclusive with "net"
            # "net" has been checked before
            pass

    def verify_route_device(self, conf):
        """Verify route device.

        Need either "device" or "gateway"
        """
        try:
            if conf["device"] not in netifaces.interfaces():
                msg = "Device {} does not exist".format(conf["device"])
                self.report_error(msg)
        except KeyError:
            if "gateway" in conf:
                return
            self.report_error("Need either 'gateway' or 'device'")

    def verify_route_metric(self, conf):
        """Verify route metric.

        "metric" is an optional configuration parameter.
        """
        try:
            int(conf["metric"])
        except KeyError:
            # key is optional
            pass
        except ValueError:
            msg = "Bad network config: metric expected to be integer"
            self.report_error(msg)

    def verify_rule(self, conf):
        """Verify rules."""
        hookenv.log("Verifying rule {}".format(pprint.pformat(conf)), level=hookenv.INFO)

        # Verify items in configuration
        self.verify_rule_mark(conf)
        self.verify_rule_iif(conf)
        self.verify_rule_from_net(conf)
        self.verify_rule_to_net(conf)
        self.verify_rule_table(conf)
        self.verify_rule_prirority(conf)

        RoutingEntryType.add_entry(RoutingEntryRule(conf))

    def verify_rule_mark(self, conf):
        """
        Verify fwmark config.

        "fwmark" key isn't required.
        if fwmark is correct and from-net is unset -- set from-net=all
        """
        fwmark = conf.get("fwmark")
        if not fwmark:
            return None

        fwmark_hex = RoutingEntryRule.fwmark_user(fwmark)
        from_net = conf.get("from-net")
        if not fwmark_hex:
            msg = "fwmark {} is in the wrong format".format(fwmark)
            self.report_error(msg)
        else:
            # now that its valid, update the config with hex version
            conf["fwmark"] = fwmark_hex

        if fwmark_hex and not from_net:
            conf["from-net"] = "all"

    def verify_rule_iif(self, conf):
        """
        Verify rule input interface.

        "iif" key isn't required, but verify the network device exists
        """
        iif = conf.get("iif")
        if iif and iif not in netifaces.interfaces():
            msg = "Device {} does not exist".format(iif)
            self.report_error(msg)

    def verify_rule_from_net(self, conf):
        """Verify rule source network.

        "from-net" key is a required configuration parameter.
        """
        try:
            fro = conf["from-net"]
            if fro == "all" or ipaddress.ip_network(fro):
                return
        except KeyError:
            msg = "Bad network config: rule entries need the 'from-net' def"
        except ValueError as error:
            msg = "Bad network config: {} - {}".format(conf["from-net"], error)
        self.report_error(msg)

    def verify_rule_to_net(self, conf):
        """Verify rule destination network.

        "to-net" key is a optional configuration parameter.
        """
        try:
            to = conf["to-net"]
            if to == "all" or ipaddress.ip_network(to):
                return
        except KeyError:
            # key is optional
            pass
        except ValueError as error:
            msg = "Bad network config: {} - {}".format(conf["to-net"], error)
            self.report_error(msg)

    def verify_rule_table(self, conf):
        """Verify rule table.

        "table" key is a required configuration parameter.
        """
        # True if it exists, False if it does not
        # raises an exception if it is wrong
        return self.verify_route_table(conf)

    def verify_rule_prirority(self, conf):
        """Verify rule priority.

        "priority" key is an optional configuration parameter.
        """
        try:
            int(conf["priority"])
        except KeyError:
            # key is optional
            pass
        except ValueError:
            msg = "Bad network config: priority expected to be integer at {}".format(conf)
            self.report_error(msg)

    def report_error(self, msg):
        """Error reporting."""
        hookenv.log(msg, level=hookenv.ERROR)
        raise RoutingConfigValidatorError(msg)
