import socket
import unittest
from pathlib import Path

from bm import proxy, runner


class ProxyTest(unittest.TestCase):
    def test_wireproxy_config(self):
        text = proxy.wireproxy_config(Path("/x/wg.conf"), 4321)
        self.assertIn("WGConfig = /x/wg.conf", text)
        self.assertIn("BindAddress = 127.0.0.1:4321", text)

    def test_free_port_and_port_open(self):
        port = proxy.free_port()
        self.assertFalse(proxy.port_open(port))
        with socket.socket() as sock:
            sock.bind(("127.0.0.1", port))
            sock.listen()
            self.assertTrue(proxy.port_open(port))


class RunnerTest(unittest.TestCase):
    def test_launch_options_with_proxy(self):
        opts = runner.launch_options({
            "data_dir": "/d", "locale": "en-US", "timezone": "America/Los_Angeles",
            "proxy_url": "socks5://127.0.0.1:9",
        })
        self.assertEqual(opts["proxy"], {"server": "socks5://127.0.0.1:9"})
        self.assertEqual(opts["timezone_id"], "America/Los_Angeles")
        self.assertIn("--force-webrtc-ip-handling-policy=disable_non_proxied_udp", opts["args"])

    def test_launch_options_direct(self):
        opts = runner.launch_options({"data_dir": "/d", "locale": "vi-VN", "timezone": "", "proxy_url": ""})
        self.assertNotIn("proxy", opts)
        self.assertNotIn("timezone_id", opts)


if __name__ == "__main__":
    unittest.main()
