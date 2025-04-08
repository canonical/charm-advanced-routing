"""RoutingEntryRule unit testing module."""

import pytest
import routing_entry


@pytest.mark.parametrize(
    "config,check_output,expected_result",
    [
        pytest.param(
            {"from-net": "10.0.0.0/24", "priority": 100},
            (
                b"0:\tfrom all lookup local\n"
                b"32766:\tfrom all lookup main\n"
                b"32767:\tfrom all lookup default\n"
            ),
            False,
            id="From-Prio-NotFound=False",
        ),
        pytest.param(
            {
                "from-net": "10.0.0.0/24",
                "to-net": "all",
                "table": "SF1",
                "priority": 101,
            },
            (
                b"0:\tfrom all lookup local\n"
                b"101:\tfrom 10.0.0.0/24 lookup SF1\n"
                b"32766:\tfrom all lookup main\n"
                b"32767:\tfrom all lookup default\n"
            ),
            True,
            id="From-ToAll-Table-Prio-Found=True",
        ),
        pytest.param(
            {
                "from-net": "all",
                "fwmark": "0x10/0xff",
                "iif": "lo",
                "to-net": "10.0.0.0/24",
                "table": "SF1",
                "priority": 100,
            },
            (
                b"0:\tfrom all lookup local\n"
                b"100:\tfrom all to 10.0.0.0/24 fwmark 0x10/0xff iif lo lookup SF1\n"
                b"32766:\tfrom all lookup main\n"
                b"32767:\tfrom all lookup default\n"
            ),
            True,
            id="FromAll-ToNet-Fwmark-Iif-Table-Prio-Found=True",
        ),
    ],
)
def test_routing_entry_rule_is_duplicate(config, check_output, expected_result, monkeypatch):
    """Test that RoutingEntryRule.is_duplicate returns the expected boolean value."""
    monkeypatch.setattr("routing_entry.hookenv.log", lambda msg, level: None)
    monkeypatch.setattr("subprocess.check_output", lambda L: check_output)
    r_entry_rule = routing_entry.RoutingEntryRule(config)
    assert r_entry_rule.is_duplicate() is expected_result
