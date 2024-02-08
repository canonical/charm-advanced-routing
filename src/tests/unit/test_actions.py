"""Test suite for actions."""

import pathlib
from unittest import mock

import routing_validator


class TestActions:
    """Test suite for actions."""

    test_dir = pathlib.Path("/tmp/test/charm-advanced-routing")
    test_networkd_conf_path = test_dir / "networkd.conf.d" / "juju-networkd.conf"
    test_script = "test-script"

    def test_action_apply_changes_apply_config(self, advanced_routing_helper):
        """Test action apply changes."""
        import actions.apply_changes

        def noop():
            pass

        test_obj = advanced_routing_helper
        test_obj.common_location = self.test_dir
        test_obj.routing_script_name = self.test_script
        test_obj.common_ifup_path = self.test_dir / "if-up" / self.test_script
        test_obj.common_cleanup_path = self.test_dir / "cleanup" / self.test_script
        test_obj.networkd_conf_path = self.test_networkd_conf_path

        test_obj.post_setup = noop
        routing_validator.RoutingConfigValidator.__init__ = mock.Mock(return_value=None)
        test_obj.setup()

        assert actions.apply_changes.apply_config()
