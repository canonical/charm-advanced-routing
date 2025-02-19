"""RoutingEntry Classes.

This module contains the following abstract types and
concrete implementations, that model a routing table

                       RoutingEntryType
            ---------------------------------------
           |                    |                  |
     RoutingEntryTable  RoutingEntryRoute  RoutingEntryRule
"""

import collections
import re
import subprocess
from abc import ABCMeta, abstractmethod, abstractproperty


from charmhelpers.core import hookenv


class RoutingEntryType(metaclass=ABCMeta):
    """Abstract type RoutingEntryType."""

    entries = []  # static <RoutingEntryType>[]
    config = None  # config entry

    def __init__(self):
        """Init this class."""
        hookenv.log("Init {}".format(self.__class__.__name__), level=hookenv.INFO)

    def exec_cmd(self, cmd, pipe=False):
        """Run a subprocess and return True or False on success."""
        try:
            if pipe:
                hookenv.log(
                    "Subprocess check shell: {} {}".format(self.__class__.__name__, cmd),
                    level=hookenv.INFO,
                )
                command = " ".join(cmd)
                ps = subprocess.Popen(
                    command,
                    shell=True,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.STDOUT,
                )
                ps.communicate()
                return ps.returncode == 0
            else:
                hookenv.log(
                    "Subprocess check: {} {}".format(self.__class__.__name__, cmd),
                    level=hookenv.INFO,
                )
                subprocess.check_call(cmd)
                return True
        except subprocess.CalledProcessError as error:
            hookenv.log(error, level=hookenv.ERROR)
            return False

    @staticmethod
    def add_entry(entry):
        """Add routing entry type.

        The validator may be called multiple times
        The static list will get duplicate items added

        :param entry: routing entry
        """
        for rule in RoutingEntryType.entries:
            if rule.addline == entry.addline:
                return
        RoutingEntryType.entries.append(entry)

    @abstractmethod
    def apply(self):
        """Apply a rule object to the system.

        Not implemented, should override in strategy.
        """
        pass

    @abstractmethod
    def create_line(self):
        """Create and return the command line for this rule object.

        Not implemented, should override in strategy.
        """
        pass

    @abstractproperty
    def addline(self):
        """Return the add line for the ifup script.

        Not implemented, should override in strategy.
        """
        pass

    @abstractproperty
    def removeline(self):
        """Return the remove line for the ifdown script.

        Not implemented, should override in strategy.
        """
        pass


class RoutingEntryTable(RoutingEntryType):
    """RoutingEntryType used for routing tables."""

    default_table_file = "/etc/iproute2/rt_tables"
    table_name_file = "/etc/iproute2/rt_tables.d/juju-managed.conf"
    table_index_offset = 100  # static
    tables = set([])
    tables_all = set([])
    builtin_tables = {"main", "local", "default"}

    def __init__(self, config):
        """Add unique tables to the tables list."""
        hookenv.log("Created {}".format(self.__class__.__name__), level=hookenv.INFO)
        super().__init__()
        self.config = config
        RoutingEntryTable.tables_all.update(self.builtin_tables)

        if not self.table_exists:
            RoutingEntryTable.tables.add(self.config["table"])
            RoutingEntryTable.tables_all.add(self.config["table"])

    @property
    def table_exists(self):
        """Verify if the table shared is reserved by iproute2."""
        return self.config["table"] in RoutingEntryTable.tables_all

    def create_line(self):
        """Not implemented in this base class."""
        pass

    def apply(self):
        """Open iproute tables and add the known list of tables into this file."""
        with open(RoutingEntryTable.table_name_file, "w") as rt_table_file:
            num = RoutingEntryTable.table_index_offset
            for num, tbl in enumerate(RoutingEntryTable.tables):
                rt_table_file.write(
                    "{} {}\n".format(num + RoutingEntryTable.table_index_offset, tbl)
                )

    @property
    def addline(self):
        """Return the add line for the ifup script."""
        return "# Table: name {}\n".format(self.config["table"])

    @property
    def removeline(self):
        """Return the remove line for the ifdown script.

        Will skip built-in tables (main, local or default table)
        """
        table = self.config["table"]
        if table in self.builtin_tables:
            hookenv.log("Skip removeline for builtin table {table}".format(table=table))
            return "# Skip removing builtin table {table}\n".format(table=table)
        return ("ip route flush table {table}\nip rule del table {table}\n").format(table=table)


class RoutingEntryRoute(RoutingEntryType):
    """RoutingEntryType used for routes."""

    def __init__(self, config):
        """Object init function."""
        hookenv.log("Created {}".format(self.__class__.__name__), level=hookenv.INFO)
        super().__init__()
        self.config = config

    def create_line(self):
        """Create and return the command line for this route object.

        "default_route" and "net" are mutually exclusive. One of them is required
        "default_route" requires "table"
        "gateway" is mandatory

        Optional keywords: device, table, metric, mtu, mtu_lock

        """
        opts = collections.OrderedDict(
            {
                "device": "dev",
                "table": "table",
                "metric": "metric",
                "mtu": "mtu",
                "mtu_lock": "mtu lock",
            }
        )
        cmd = ["ip", "route", "replace"]

        gateway = self.config.get("gateway")
        # default route in table
        if "default_route" in self.config.keys():
            cmd.extend(
                [
                    "default",
                    "via",
                    gateway,  # Validated to be non-nil in validator
                    "table",
                    self.config["table"],
                ]
            )
            # already enforced
            del opts["table"]
        else:
            if gateway:
                # route in any given table or none
                cmd.extend([self.config["net"], "via", self.config["gateway"]])
            else:
                # directly connected route
                cmd.extend([self.config["net"]])

        # The "default_route" flow forces "table", so it is later removed
        for opt, keyword in opts.items():
            try:
                cmd.extend(keyword.split() + [str(self.config[opt])])
            except KeyError:
                pass
        return cmd

    def apply(self):
        """Apply this rule object to the system."""
        super().exec_cmd(self.create_line())

    @property
    def addline(self):
        """Return the add line for the ifup script."""
        return " ".join(self.create_line()) + "\n"

    @property
    def removeline(self):
        """Return the remove line for the ifdown script."""
        return " ".join(self.create_line()).replace(" replace ", " del ") + "\n"


class RoutingEntryRule(RoutingEntryType):
    """RoutingEntryType used for rules."""

    MARK_PATTERN_TXT = (
        # 13 digit int | 8 digit hex value [optional 8 digit hex mask]
        r"^(\d{1,13}|0x[0-9a-f]{1,8})(?:\/(0x[0-9a-f]{1,8}))?$"
    )
    MARK_PATTERN = re.compile(MARK_PATTERN_TXT, re.IGNORECASE)

    @staticmethod
    def fwmark_user(fwmark):
        """Convert user fwmark to match the output from ip rules list.

        @param str fwmark: marking from the user config
        @returns str in hex/hex format
        """
        match = RoutingEntryRule.MARK_PATTERN.search(fwmark)
        if not match:
            return None
        hex_vals = match.groups()
        as_ints = [int(val, 16 if val.lower().startswith("0x") else 10) for val in hex_vals if val]
        return "/".join(map(hex, as_ints))

    def __init__(self, config):
        """Object init function."""
        hookenv.log("Created {}".format(self.__class__.__name__), level=hookenv.INFO)
        super().__init__()
        self.config = config

    def create_line(self):
        """Create and return the command line for this rule object.

        Variations:
        # any dst, table main, default prio
        ip rule add from X.X.X.X/XX
        # table main, default prio
        ip rule add from X.X.X.X/XX to Y.Y.Y.Y/YY
        # default prio
        ip rule add from X.X.X.X/XX to Y.Y.Y.Y/YY table mytable
        # table main
        ip rule add from X.X.X.X/XX to Y.Y.Y.Y/YY priority NNN
        # all is specified
        ip rule add from X.X.X.X/XX to Y.Y.Y.Y/YY table mytable priority NNN
        # any dst, default prio
        ip rule add from X.X.X.X/XX table mytable
        # any dst
        ip rule add from X.X.X.X/XX table mytable priority NNN
        # any dst, table main
        ip rule add from X.X.X.X/XX priority NNN
        # any src, fwmark 0x1/0xF, iif bond0, table mytable
        ip rule add from any fwmark 1/0xF iif bond0 table mytable priority NNN
        """
        cmd = ["ip", "rule", "add", "from", self.config["from-net"]]
        opts = [
            ("fwmark", "fwmark"),
            ("iif", "iif"),
            ("to-net", "to"),
            ("table", "table"),
            ("priority", "priority"),
        ]
        for opt, keyword in opts:
            try:
                cmd.extend([keyword, str(self.config[opt])])
            except KeyError:
                pass
        return cmd

    def apply(self):
        """Apply this rule object to the system."""
        if self.is_duplicate() is False:
            # ip rule replace not supported, check for duplicates
            super().exec_cmd(self.create_line())

    @property
    def addline(self):
        """Return the add line for the ifup script."""
        return " ".join(self.create_line()) + "\n"

    @property
    def removeline(self):
        """Return the remove line for the ifdown script."""
        return " ".join(self.create_line()).replace(" add ", " del ") + "\n"

    def is_duplicate(self):
        """Ip rule add does not prevent duplicates in older kernel versions."""
        # https://patchwork.ozlabs.org/patch/624553/
        matchparams = ["from", self.config["from-net"]]

        to = self.config.get("to-net")
        if to and to != "all":  # ip rule omits to=all as it's implied
            matchparams.extend(("to", to))

        fwmark = self.config.get("fwmark")
        if fwmark:
            matchparams.extend(("fwmark", fwmark))

        iif = self.config.get("iif")
        if iif:
            matchparams.extend(("iif", iif))

        matchparams.extend(("lookup", self.config.get("table", "main")))
        matchline = " ".join(matchparams)
        prio = str(self.config.get("priority", ""))
        existing_rules = subprocess.check_output(["ip", "rule"]).decode("utf8").splitlines()
        for rule in existing_rules:
            rule = rule.strip()
            if rule.startswith(prio) and rule.endswith(matchline):
                hookenv.log("Found dup rule: {}".format(matchline), level=hookenv.DEBUG)
                return True
        return False
