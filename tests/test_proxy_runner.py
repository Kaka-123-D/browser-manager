import socket
import unittest
from pathlib import Path

from bm import proxy, runner


class ProxyTest(unittest.TestCase):
    def test_wireproxy_config(self):
        text = proxy.wireproxy_config(Path("/x/wg.conf"), 4321)
        self.assertIn("WGConfig = /x/wg.conf", text)
        self.assertIn("BindAddress = 127.0.0.1:4321", text)
        self.assertIn("ResolveStrategy = ipv4", text)

    def test_ipv4_only_drops_ipv6_entries(self):
        text = ("[Interface]\nPrivateKey = abc=\nAddress = 10.2.0.2/32, 2a07:b944::2:2/128\n"
                "DNS = 10.2.0.1, 2a07:b944::2:1\n\n[Peer]\nAllowedIPs = 0.0.0.0/0, ::/0\nEndpoint = 1.2.3.4:51820\n")
        out = proxy.ipv4_only(text)
        self.assertIn("Address = 10.2.0.2/32\n", out)
        self.assertIn("DNS = 10.2.0.1\n", out)
        self.assertIn("PrivateKey = abc=\n", out)
        self.assertIn("AllowedIPs = 0.0.0.0/0, ::/0\n", out)
        self.assertIn("Endpoint = 1.2.3.4:51820\n", out)

    def test_ipv4_only_drops_line_left_empty(self):
        out = proxy.ipv4_only("[Interface]\nDNS = 2a07:b944::2:1\nAddress = 10.2.0.2/32\n")
        self.assertNotIn("DNS", out)
        self.assertIn("Address = 10.2.0.2/32", out)

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

    def test_plain_chrome_has_no_automation_and_strips_login(self):
        args = runner.plain_chrome_args({
            "data_dir": "/d", "locale": "en-US", "start_url": "https://accounts.google.com",
            "proxy_url": "http://u:p@127.0.0.1:18001",
        }, "/chrome")
        self.assertEqual(args[0], "/chrome")
        self.assertIn("--user-data-dir=/d", args)
        self.assertIn("--proxy-server=http://127.0.0.1:18001", args)
        self.assertEqual(args[-1], "https://accounts.google.com")
        self.assertFalse(any("remote-debugging" in a or "enable-automation" in a for a in args))
        self.assertFalse(any("u:p" in a for a in args))


if __name__ == "__main__":
    unittest.main()
