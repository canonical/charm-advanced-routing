# Overview

This subordinate charm allows for the configuration of policy routing rules on the deployed host,
as well as routes to configured services. A list of hash maps, in JSON format, is expected.

Charm supports IPv4 addressing.

**Warning:** if configured incorrectly, this has the potential to disrupt your units networking setup. Be sure to test your configuration before rolling it out to production. Note the charm provides an apply-changes action, which allows you to apply routing changes per unit as a way to mitigate risk

# Usage

Add to an existing application using juju-info relation.

Example:

```
juju deploy advanced-routing
juju add-relation ubuntu advanced-routing
```

# Configuration

The user can configure the following parameters:

* `enable-advanced-routing`: Enable routing. This requires for the charm to have routing information configured in JSON format: ```juju config advanced-routing --file path/to/your/config```
* `advanced-routing-config` parameter contains 3 types of entities: 'table', 'route', 'rule'. The 'type' parameter is always required.

table: routing table to put the rules in (used in rules)

route: defines a static route with the following params:

* default_route: should this be a default route or not (boolean: true|false) (optional, requires gateway and table)
* net:           IPv4 CIDR for a destination network (string) (mutually exclusive with default_route, and requires gateway or device)
* gateway:       IPv4 gateway address (string) (either device or gateway is required)
* table:         routing table name (string) (optional, except if default_route is used)
* metric:        metric for the route (int) (optional)
* device:        device (interface) (string) (either device or gateway is required)

rule:

* from-net: IPv4 CIDR source network or "all" (string) (required)
* to-net: IPv4 CIDR destination network or "all" (string) (optional)
* table: routing table name (string) (optional, default is main)
* priority: priority (int) (optional)

An example yaml config file below:

```yaml
settings:
  advanced-routing-config:
    value: |-
      [ {
          "type": "table",
          "table": "SF1"
      }, {
          "type": "route",
          "default_route": true,
          "gateway": "10.191.86.2",
          "table": "SF1",
          "metric": 101,
          "device": "eth0"
      }, {
          "type": "route",
          "net": "6.6.6.0/24",
          "gateway": "10.191.86.2"
      }, {
          "type": "rule",
          "from-net": "192.170.2.0/24",
          "to-net": "192.170.2.0/24",
          "table": "SF1",
          "priority": 101
      } ]
  enable-advanced-routing:
    value: true
```

The `example_config.yaml` file is also provided with the codebase.

**Note:** the `from-net` parameter refers not to the tcp conversation, but to
the individual packet path.  I.e., if a reply from our host to a remote host is
from the interface with address 192.170.2.4, regardless of destination, that
would trigger the rule when we state `"from-net": "192.170.2.0/24"`.

# Understanding the configuration options

The charm builds a routing configuration on units based on the configuration
options provided to it.  The configuration uses the policy routing rules
specified to build multiple route tables, and select which one to use based on
rule matching.

Let's use an example to illustrate; a unit with two network interfaces, one for
'internal' traffic, and one that listens on a public facing IP address for
traffic to it's specific application.  The default gateway is found via eth0
which is for 'internal' traffic, but doesn't allow traffic to the entire
Internet.  On the network with the 'public' interface is a gateway/firewall that
has routes to the clients wanting to connect to our host.

On the Juju unit we're looking at, the /etc/netplan/50-cloud-init.yaml
contains a 'gateway' setting only for eth0 (the default gateway) and does not
add a gateway for eth1.

Our network config looks like this:

* eth0: IP address 192.168.0.20/24, gateway 192.168.0.1 (default gateway)
* eth1: IP address 10.0.0.50/24, gateway 10.0.0.1 (not configured)
* Default gateway set up by the host network config: 192.168.0.1

The route table at the start looks like this:

```bash
# ip route
default via 192.168.0.1 dev eth0 proto static
192.168.0.0/24 dev eth0 proto kernel scope link src 192.168.0.20
10.0.0.0/24 dev eth1 proto kernel scope link src 10.0.0.50
```

Now, consider that a client connects to 192.168.0.20.  The traffic arrives on
eth0, and the reply goes out via eth0 and 192.168.0.1.  No problem.

Next a packet arrives from, e.g., 1.2.3.4, addressed to 10.0.0.50, on eth1.  The
reply needs to go via a router that has a route to that address, but the route
table states that the default route is via eth0 192.168.0.1, which would
block that traffic.  We need to tell the kernel that the response must go via
eth1, and use 10.0.0.1 as the next hop, rather than use this asymmetric path.

We can fix this using [policy routing rules](https://man7.org/linux/man-pages/man8/ip-rule.8.html).
In this case, we want to define a new rule and a route table to match it (let's
call that 'public').

We want to define the rule such that replies to traffic addressed to our eth1 IP
address is sent via the gateway accessed via eth1.  We can specify this with a
'from' address rule, where the network we state 'from' is the network that has
the address on eth1 - i.e., the reply is 'from' our eth1 address, going
outwards.

In this case, we want to say:

```bash
# ip rule list
0:      from all lookup local
101:    from 10.0.0.0/24 lookup public
32766:  from all lookup main
32767:  from all lookup default

# ip route show table main
default via 192.168.0.1 dev eth0 proto static
192.168.0.0/24 dev eth0 proto kernel scope link src 192.168.0.20
10.0.0.0/24 dev eth1 proto kernel scope link src 10.0.0.50

# ip route show table public
default via 10.0.0.1 dev eth1 proto static
```

Reading this, we see that traffic 'from' 10.0.0.0/24, i.e. from our host address
10.0.0.50 heading anywhere outwards, will be selected to use the 'public' route
table, which uses 10.0.0.1 as the next hop.  Other traffic will use the 'main'
table which uses 192.168.0.1.

To translate this into a configuration for the charm:

```yaml
settings:
  advanced-routing-config:
    value: |-
      [ {
          "type": "table",
          "table": "public"
      }, {
          "type": "route",
          "default_route": true,
          "gateway": "10.0.0.1",
          "table": "public",
          "metric": 101,
          "device": "eth1"
      }, {
          "type": "rule",
          "from-net": "10.0.0.0/24",
          "table": "public",
          "priority": 101
      } ]
  enable-advanced-routing:
    value: true
```

# Migration steps from the policy-routing charm

## Initial deployment

The following steps assume that an ubuntu unit with a subordinate policy-routing charm
with the following config has been deployed:

```
application: policy-routing
application-config:
  trust:
    default: false
    description: Does this application have access to trusted credentials
    source: default
    type: bool
    value: false
charm: policy-routing
settings:
  cidr:
    description: |
      CIDR of the network interface to setup a policy routing.
      e.g. 192.168.0.0/24
    source: user
    type: string
    value: 10.10.51.0/24
  gateway:
    description: |
      The gateway to be used from the network interface specified with
      the CIDR. e.g. 192.168.0.254
    source: user
    type: string
    value: 10.10.51.1
```

juju status looks like:

```
$ juju status
Model        Controller  Cloud/Region         Version  SLA          Timestamp
model1  lxd         localhost/localhost  2.7.2    unsupported  11:52:19Z

App                       Version     Status   Scale  Charm                     Store       Rev  OS      Notes
policy-routing                        waiting      0  policy-routing            jujucharms    3  ubuntu
ubuntu                    18.04       active       1  ubuntu                    jujucharms   15  ubuntu


Unit                   Workload  Agent      Machine  Public address  Ports               Message
ubuntu/0*              active    idle       127      10.0.8.155                          ready
  policy-routing/0*    active    idle                10.0.8.155                          Unit ready

```

## Deploy advanced-routing charm

* `juju deploy advanced-routing`
* `juju add-relation ubuntu advanced-routing`

Advanced-routing is in status blocked with message: "Please disable charm-policy-routing"

Apply the following config:

```
$ cat ./advanced_routing_config
advanced-routing:
  enable-advanced-routing: true
  advanced-routing-config: |
      [ {
          "type": "table",
          "table": "SF1"
      }, {
          "type": "route",
          "default_route": true,
          "gateway": "10.10.51.1",
          "table": "SF1"
      }, {
          "type": "rule",
          "from-net": "10.10.51.0/24",
          "to-net": "10.10.51.0/24",
          "priority": 100
      }, {
          "type": "rule",
          "from-net": "10.10.51.0/24",
          "table": "SF1",
          "priority": 101
      } ]
```

with the command:

```
juju config advanced-routing --file ./advanced_routing_config
```

## Disable the old config

```
juju run -u ubuntu/0 "sudo systemctl stop charm-pre-install-policy-routing ; sudo systemctl disable charm-pre-install-policy-routing ; sudo rm -f /etc/systemd/system/charm-pre-install-policy-routing.service; "
```

## Apply the routing configuration with the new charm

Using the action apply-changes, add the routes using the advance-routing charm

```
juju run-action advanced-routing/0 apply-changes --wait
```

# Build and Testing

To build the charm locally:

```
make build
```

To run lint tests:

```bash
make lint
```

To run unit tests:

```bash
make unittests
```

Functional tests have been developed using python-libjuju, deploying a simple ubuntu charm and adding the charm as a subordinate.

To run tests using python-libjuju:

```bash
make functional
```

To run the complete test suite (lint tests, unit tests, functional test)

```bash
make test
```

# Contact Information

* LMA Charmers <llama-charmers@lists.launchpad.net>
