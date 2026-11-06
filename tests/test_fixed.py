import stat
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from bm import fixed, paths, runner, store
from bm.manager import Manager


class FixedRecordTest(unittest.TestCase):
    def test_new_record_takes_next_free_pair(self):
        first = fixed.new_record("vpn:protonvpn/a.conf", [])
        second = fixed.new_record("vpn:protonvpn/b.conf", [first])
        self.assertEqual(second.http_port, first.http_port + 2)
        self.assertEqual(second.socks_port, second.http_port + 1)
        self.assertNotEqual(first.password, second.password)

    def test_urls_and_config(self):
        record = fixed.FixedProxy("vpn:protonvpn/a.conf", 18001, 18002, "bmuser", "secret")
        self.assertEqual(record.http_url(), "http://bmuser:secret@127.0.0.1:18001")
        self.assertEqual(record.socks_url(), "socks5://bmuser:secret@127.0.0.1:18002")
        self.assertEqual(record.plain(), "127.0.0.1:18001:bmuser:secret")
        text = fixed.wireproxy_config(Path("/x/wg.conf"), record)
        self.assertIn("[http]\nBindAddress = 127.0.0.1:18001\nUsername = bmuser\nPassword = secret", text)
        self.assertIn("[Socks5]\nBindAddress = 127.0.0.1:18002\nUsername = bmuser\nPassword = secret", text)
        self.assertNotIn("0.0.0.0", text)
        self.assertIn("ResolveStrategy = ipv4", text)

    def test_with_enabled_returns_new_list(self):
        records = [fixed.FixedProxy("k", 1, 2, "u", "p")]
        updated = fixed.with_enabled(records, "k", True)
        self.assertFalse(records[0].enabled)
        self.assertTrue(updated[0].enabled)


class RunnerLoginTest(unittest.TestCase):
    def test_login_is_split_out_for_playwright(self):
        opt = runner.proxy_option("http://bmuser:secret@127.0.0.1:18001")
        self.assertEqual(opt, {"server": "http://127.0.0.1:18001", "username": "bmuser", "password": "secret"})

    def test_plain_proxy_unchanged(self):
        self.assertEqual(runner.proxy_option("socks5://127.0.0.1:9"), {"server": "socks5://127.0.0.1:9"})


class ManagerFixedTest(unittest.TestCase):
    def setUp(self):
        tmp = Path(tempfile.mkdtemp())
        vpn = tmp / "vpn"
        vpn.mkdir()
        (vpn / "us-1.conf").write_text("[Interface]\n")
        patches = {
            "DATA_DIR": tmp, "PROFILES_FILE": tmp / "profiles.json", "PROFILE_DATA_DIR": tmp / "profiles",
            "PROXY_CONF_DIR": tmp / "proxies", "LOG_DIR": tmp / "logs", "VPN_DIRS": {"protonvpn": vpn},
        }
        for attr, value in patches.items():
            patcher = mock.patch.object(paths, attr, value)
            patcher.start()
            self.addCleanup(patcher.stop)
        self.manager = Manager()
        self.key = "vpn:protonvpn/us-1.conf"

    def test_add_saves_private_file(self):
        self.manager.add_fixed(self.key)
        view = self.manager.state()["fixed"]
        self.assertEqual([f["key"] for f in view], [self.key])
        self.assertFalse(view[0]["running"])
        mode = stat.S_IMODE(fixed.file_path().stat().st_mode)
        self.assertEqual(mode, 0o600)

    def test_add_twice_or_unknown_is_refused(self):
        self.manager.add_fixed(self.key)
        with self.assertRaises(store.ValidationError):
            self.manager.add_fixed(self.key)
        with self.assertRaises(store.ValidationError):
            self.manager.add_fixed("vpn:protonvpn/missing.conf")

    def test_start_refused_while_profile_tunnel_runs(self):
        self.manager.add_fixed(self.key)
        self.manager.save_profile({"name": "p", "proxy": self.key})
        self.manager._browsers = {"p": mock.Mock(poll=lambda: None)}
        self.manager._proxies = {self.key: mock.Mock(alive=lambda: True)}
        with mock.patch("bm.proxy.launch") as launch:
            with self.assertRaises(store.ValidationError):
                self.manager.start_fixed(self.key)
            launch.assert_not_called()

    def test_profile_reuses_running_fixed_proxy(self):
        self.manager.add_fixed(self.key)
        self.manager._fixed_running = {self.key: mock.Mock(alive=lambda: True)}
        profile = store.Profile("p", proxy=self.key)
        url = self.manager._proxy_url(profile)
        self.assertTrue(url.startswith("http://bm"))
        self.assertTrue(url.endswith(f"@127.0.0.1:{self.manager.state()['fixed'][0]['http_port']}"))

    def test_delete_refused_while_running(self):
        self.manager.add_fixed(self.key)
        self.manager._fixed_running = {self.key: mock.Mock(alive=lambda: True)}
        with self.assertRaises(store.ValidationError):
            self.manager.delete_fixed(self.key)


if __name__ == "__main__":
    unittest.main()
