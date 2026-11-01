import ctypes
import unittest
from unittest.mock import Mock, call, patch

from edge_threat_response.jetson_memory import prepare_jetson_memory


class JetsonMemoryTests(unittest.TestCase):
    def test_other_platforms_and_missing_or_non_orin_devices_are_untouched(self):
        for system, model in [("Windows", "Orin"), ("Linux", "Jetson Nano"), ("Linux", OSError())]:
            with self.subTest(system=system, model=model), patch("platform.system", return_value=system), \
                 patch("pathlib.Path.read_text", side_effect=model if isinstance(model, Exception) else None, return_value=model), \
                 patch("ctypes.CDLL") as load:
                self.assertIsNone(prepare_jetson_memory())
                load.assert_not_called()

    def test_disable_is_process_scoped_and_confirmed(self):
        libc = Mock()
        libc.prctl.side_effect = [0, 0, 1]
        with patch("platform.system", return_value="Linux"), patch("pathlib.Path.read_text", return_value="Orin Nano"), \
             patch("ctypes.CDLL", return_value=libc):
            result = prepare_jetson_memory()
        self.assertEqual([call(42, 0, 0, 0, 0), call(41, 1, 0, 0, 0), call(42, 0, 0, 0, 0)], libc.prctl.call_args_list)
        self.assertEqual({"scope":"current_process","requested":"disable_thp","before":0,"after":1,"changed":True}, result)

    def test_already_disabled_and_explicit_inheritance_do_not_set_policy(self):
        for before, inherit in [(1, False), (0, True), (1, True)]:
            with self.subTest(before=before, inherit=inherit):
                libc = Mock()
                libc.prctl.return_value = before
                with patch("platform.system", return_value="Linux"), patch("pathlib.Path.read_text", return_value="Orin"), \
                     patch("ctypes.CDLL", return_value=libc):
                    result = prepare_jetson_memory(inherit_thp=inherit)
                self.assertEqual([call(42, 0, 0, 0, 0)] * 2, libc.prctl.call_args_list)
                self.assertFalse(result["changed"])

    def test_syscall_errors_and_unconfirmed_policy_are_not_silent_success(self):
        for returns in [[-1], [0, -1], [0, 0, 0]]:
            with self.subTest(returns=returns):
                libc = Mock()
                libc.prctl.side_effect = returns
                with patch("platform.system", return_value="Linux"), patch("pathlib.Path.read_text", return_value="Orin"), \
                     patch("ctypes.CDLL", return_value=libc), patch("ctypes.get_errno", return_value=1):
                    with self.assertRaises(RuntimeError):
                        prepare_jetson_memory()
