"""Main unit testing module."""

import pathlib
import shutil
import unittest.mock as mock


import routing_validator


class TestAdvancedRoutingHelper:
    """Main test class."""

    test_dir = pathlib.Path("/tmp/test/charm-advanced-routing")
    test_networkd_conf_path = test_dir / "networkd.conf.d" / "juju-networkd.conf"
    test_netplanup_path = test_dir / "symlink_test" / "netplanup"
    test_cleanup_path = test_dir / "symlink_test" / "netplandown"
    test_ifup_path = test_dir / "symlink_test" / "ifup"
    test_script = "test-script"

    @classmethod
    def setUp(cls):
        """Make dirs for setup."""
        cls.test_dir.mkdir(parents=True)
        cls.test_ifup_path.mkdir(parents=True)
        cls.test_netplanup_path.mkdir(parents=True)

    @classmethod
    def tearDown(cls):
        """Teardown method."""
        try:
            shutil.rmtree(cls.test_dir)
        except OSError:
            pass

    def test_pre_setup(self, advanced_routing_helper):
        """Test pre_setup."""
        test_obj = advanced_routing_helper

        test_obj.common_location = self.test_dir
        test_obj.routing_script_name = self.test_script
        test_obj.policy_routing_service_dir_path = self.test_dir

        try:
            (
                test_obj.policy_routing_service_dir_path
                / "charm-pre-install-policy-routing.service"
            ).unlink()
        except FileNotFoundError:
            pass

        test_obj.pre_setup()

        uppath = test_obj.common_location / "if-up"

        assert uppath.exists()

    def test_setup(self, advanced_routing_helper):
        """Test setup."""

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

        assert test_obj.common_ifup_path.exists()
        assert test_obj.common_cleanup_path.exists()

    def test_remove_routes(self, advanced_routing_helper, mock_check_call):
        """Test post_setup."""
        test_obj = advanced_routing_helper

        with mock.patch("charmhelpers.core.host.lsb_release") as lsbrelbionic:
            test_obj.netplan_up_dir_path = self.test_netplanup_path
            test_obj.common_cleanup_path = self.test_cleanup_path
            lsbrelbionic.return_value = "bionic"
            test_obj.remove_routes()

        with mock.patch("charmhelpers.core.host.lsb_release") as lsbrelxenial:
            test_obj.net_tools_up_dir_path = self.test_ifup_path
            test_obj.common_cleanup_path = self.test_cleanup_path
            lsbrelxenial.return_value = "xenial"
            test_obj.remove_routes()

        assert not test_obj.common_ifup_path.exists()
        assert not test_obj.common_cleanup_path.exists()

    def test_symlink_force(self, advanced_routing_helper):
        """Test symlink_force."""
        test_obj = advanced_routing_helper

        target = self.test_dir / "testfile"
        link = self.test_dir / "testlink"

        try:
            target.unlink()
        except FileNotFoundError:
            pass  # dont care

        # touch target file to link to
        try:
            with open(target, "w+") as f:
                f.write("dont care\n")
        except IOError:
            pass  # dont care

        assert target.exists()

        # link it
        test_obj.symlink_force(target, link)
        assert link.exists()

        # link it again
        test_obj.symlink_force(target, link)
        assert link.exists()

    def test_setup_persistent_rules(self, advanced_routing_helper):
        """Test setup_persistent_rules."""
        test_obj = advanced_routing_helper
        test_obj.networkd_conf_path = self.test_networkd_conf_path

        test_obj.setup_persistent_rules()

        assert test_obj.networkd_conf_path.exists()
