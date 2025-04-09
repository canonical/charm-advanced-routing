"""routing validator unit testing module."""

import pytest
import routing_validator


@pytest.mark.parametrize(
    "fwmark",
    [
        "abc",  # not valid hex -- 0xabc is right
        "1 0x0f",  # space isn't a valid delimiter
        "99999999999999",  # too many digits
        "0x1000000000",  # too many hex digits
        "2/0x1000000000",  # too many hex digits
        "1/1",  # mask must be hex
    ],
    ids=[
        "not valid hex -- 0xabc is right",
        "space isn't a valid delimiter",
        "too many digits",
        "too many hex digits",
        "too many hex digits in mask",
        "mask must be hex",
    ],
)
def test_routing_validate_rule_fwmark_failure(fwmark):
    """Test different versions of user input on fwmark."""
    validator = routing_validator.RoutingConfigValidator()
    with pytest.raises(routing_validator.RoutingConfigValidatorError) as ie:
        validator.verify_rule({"fwmark": fwmark})
    ie.match("fwmark {} is in the wrong format".format(fwmark))
