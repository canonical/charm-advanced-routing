"""Config options used in test_routing.py.

Listing of advanced-routing-config options to be tested in test_juju_routing
"""

JSON_CONFIGS = [
    {
        "input": [
            {"type": "table", "table": "SF1"},
            {
                "type": "route",
                "default_route": True,
                "net": "192.170.1.0/24",
                "gateway": "10.191.86.2",
                "table": "SF1",
                "metric": 101,
                "device": "eth0",
            },
            {"type": "route", "net": "6.6.6.0/24", "gateway": "10.191.86.2"},
            {
                "type": "rule",
                "from-net": "192.170.2.0/24",
                "to-net": "192.170.2.0/24",
                "table": "SF1",
                "priority": 101,
            },
        ],
        "expected_ifup": (
            "#!/bin/sh\n"
            "# This file is managed by Juju.\n"
            "ip route flush cache\n"
            "# Table: name SF1\n"
            "ip route replace default via 10.191.86.2 table SF1 dev eth0 metric 101\n"
            "ip route replace 6.6.6.0/24 via 10.191.86.2\n"
            "ip rule add from 192.170.2.0/24 to 192.170.2.0/24 table SF1 priority 101\n"
        ),
        "expected_ifdown": (
            "#!/bin/sh\n"
            "# This file is managed by Juju.\n"
            "ip rule del from 192.170.2.0/24 to 192.170.2.0/24 table SF1 priority 101\n"
            "ip route del 6.6.6.0/24 via 10.191.86.2\n"
            "ip route del default via 10.191.86.2 table SF1 dev eth0 metric 101\n"
            "ip route flush table SF1\n"
            "ip rule del table SF1\n"
            "ip route flush cache\n"
        ),
    },
    {
        "input": [
            {"type": "table", "table": "mytable"},
            {
                "type": "route",
                "default_route": True,
                "gateway": "10.205.6.1",
                "table": "mytable",
            },
            {
                "type": "rule",
                "from-net": "10.205.6.0/24",
                "to-net": "1.1.1.1/32",
                "priority": 100,
            },
            {
                "type": "rule",
                "from-net": "10.205.6.0/24",
                "table": "mytable",
                "priority": 101,
            },
        ],
        "expected_ifup": (
            "#!/bin/sh\n"
            "# This file is managed by Juju.\n"
            "ip route flush cache\n"
            "# Table: name mytable\n"
            "ip route replace default via 10.205.6.1 table mytable\n"
            "ip rule add from 10.205.6.0/24 to 1.1.1.1/32 priority 100\n"
            "ip rule add from 10.205.6.0/24 table mytable priority 101\n"
        ),
        "expected_ifdown": (
            "#!/bin/sh\n"
            "# This file is managed by Juju.\n"
            "ip rule del from 10.205.6.0/24 table mytable priority 101\n"
            "ip rule del from 10.205.6.0/24 to 1.1.1.1/32 priority 100\n"
            "ip route del default via 10.205.6.1 table mytable\n"
            "ip route flush table mytable\n"
            "ip rule del table mytable\n"
            "ip route flush cache\n"
        ),
    },
    {  # Test "all" in rules, and test a directly connected route
        "input": [
            {"type": "table", "table": "mytable"},
            {
                "type": "route",
                "net": "1.1.2.0/24",
                "device": "eth0",
                "table": "mytable",
            },
            {
                "type": "rule",
                "from-net": "all",
                "to-net": "1.1.2.1/32",
                "priority": 100,
            },
            {
                "type": "rule",
                "from-net": "10.205.7.0/24",
                "to-net": "all",
                "table": "mytable",
                "priority": 101,
            },
        ],
        "expected_ifup": (
            "#!/bin/sh\n"
            "# This file is managed by Juju.\n"
            "ip route flush cache\n"
            "# Table: name mytable\n"
            "ip route replace 1.1.2.0/24 dev eth0 table mytable\n"
            "ip rule add from all to 1.1.2.1/32 priority 100\n"
            "ip rule add from 10.205.7.0/24 to all table mytable priority 101\n"
        ),
        "expected_ifdown": (
            "#!/bin/sh\n"
            "# This file is managed by Juju.\n"
            "ip rule del from 10.205.7.0/24 to all table mytable priority 101\n"
            "ip rule del from all to 1.1.2.1/32 priority 100\n"
            "ip route del 1.1.2.0/24 dev eth0 table mytable\n"
            "ip route flush table mytable\n"
            "ip rule del table mytable\n"
            "ip route flush cache\n"
        ),
    },
    {  # Test a rule for a builtin table ("main")
        "input": [
            {"type": "table", "table": "main"},
            {
                "type": "rule",
                "from-net": "10.205.7.0/24",
                "to-net": "all",
                "table": "main",
            },
        ],
        "expected_ifup": (
            "#!/bin/sh\n"
            "# This file is managed by Juju.\n"
            "ip route flush cache\n"
            "# Table: name main\n"
            "ip rule add from 10.205.7.0/24 to all table main\n"
        ),
        "expected_ifdown": (
            "#!/bin/sh\n"
            "# This file is managed by Juju.\n"
            "ip rule del from 10.205.7.0/24 to all table main\n"
            "# Skip removing builtin table main\n"
            "ip route flush cache\n"
        ),
    },
    {
        "input": [
            {"type": "table", "table": "mytable"},
            {"type": "route", "net": "1.1.2.0/24", "device": "eth0"},
            {
                "type": "rule",
                "from-net": "all",
                "to-net": "1.1.2.1/32",
                "priority": 100,
            },
            {
                "type": "rule",
                "from-net": "10.205.7.0/24",
                "to-net": "all",
                "table": "mytable",
                "priority": 101,
            },
        ],
        "expected_ifup": (
            "#!/bin/sh\n"
            "# This file is managed by Juju.\n"
            "ip route flush cache\n"
            "# Table: name mytable\n"
            "ip route replace 1.1.2.0/24 dev eth0\n"
            "ip rule add from all to 1.1.2.1/32 priority 100\n"
            "ip rule add from 10.205.7.0/24 to all table mytable priority 101\n"
        ),
        "expected_ifdown": (
            "#!/bin/sh\n"
            "# This file is managed by Juju.\n"
            "ip rule del from 10.205.7.0/24 to all table mytable priority 101\n"
            "ip rule del from all to 1.1.2.1/32 priority 100\n"
            "ip route del 1.1.2.0/24 dev eth0\n"
            "ip route flush table mytable\n"
            "ip rule del table mytable\n"
            "ip route flush cache\n"
        ),
    },
]
