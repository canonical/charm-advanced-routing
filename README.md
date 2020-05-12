# Overview

This subordinate charm allows for the configuration of policy routing rules on the deployed host,
as well as routes to configured services. A list of hash maps, in JSON format, is expected.

Charm supports IPv4 addressing.

**Warning:** if configured incorrectly, this has the potential to disrupt your units networking setup. Be sure to test your configuration before rolling it out to production. Note the charm provides an apply-changes action, which allows you to apply routing changes per unit as a way to mitigate risk


# Build
```
cd charm-advanced-routing
make build
```

# Usage
Add to an existing application using juju-info relation.

Example:
```
juju deploy cs:advanced-routing
juju add-relation ubuntu advanced-routing
```

# Configuration                                                                 
The user can configure the following parameters:
 * `enable-advanced-routing`: Enable routing. This requires for the charm to have routing information configured in JSON format: ```juju config advanced-routing --file path/to/your/config```

 * `advanced-routing-config` parameter contains 3 types of entities: 'table', 'route', 'rule'. The 'type' parameter is always required.

table: routing table to put the rules in (used in rules)

route: defines a static route with the following params:
 - default_route: should this be a default route or not (boolean: true|false) (optional, requires gateway and table)
 - net:           IPv4 CIDR for a destination network (string) (mutually exclusive with default_route, and requires gateway or device)
 - gateway:       IPv4 gateway address (string) (either device or gateway is required)
 - table:         routing table name (string) (optional, except if default_route is used)
 - metric:        metric for the route (int) (optional)
 - device:        device (interface) (string) (either device or gateway is required)

rule:
 - from-net: IPv4 CIDR source network or "all" (string) (required)
 - to-net: IPv4 CIDR destination network or "all" (string) (optional)
 - table: routing table name (string) (optional, default is main)
 - priority: priority (int) (optional)

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


# Migration steps from the policy-routing charm

### Initial deployment:

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

### Deploy advanced-routing charm :

- ``` juju deploy cs:advanced-routing ```
- ``` juju add-relation ubuntu advanced-routing ```

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
          "table": "SF1",
      }, {
          "type": "rule",
          "from-net": "10.10.51.0/24",
          "to-net": "10.10.51.0/24",
          "priority": 100,     
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

### Disable the old config

```
juju run -u ubuntu/0 "sudo systemctl stop charm-pre-install-policy-routing ; sudo systemctl disable charm-pre-install-policy-routing ; sudo rm -f /etc/systemd/system/charm-pre-install-policy-routing.service; "
```

### Apply the routing configuration with the new charm

Using the action apply-changes, add the routes using the advance-routing charm

```
juju run-action advanced-routing/0 apply-changes --wait
```

# Testing                                                                       
To run lint tests:
```bash
tox -e lint

```
To run unit tests:
```bash
tox -e unit
```
Functional tests have been developed using python-libjuju, deploying a simple ubuntu charm and adding the charm as a subordinate.

To run tests using python-libjuju:
```bash
tox -e functional
```

# Contact Information

 * LMA Charmers <llama-charmers@lists.launchpad.net>
