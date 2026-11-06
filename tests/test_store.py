import tempfile
import unittest
from pathlib import Path

from bm import store


class StoreTest(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.vpn_dirs = {"protonvpn": self.tmp / "protonvpn"}
        self.vpn_dirs["protonvpn"].mkdir()
        (self.vpn_dirs["protonvpn"] / "us-wa-270.conf").write_text("[Interface]\n")

    def test_valid_profile_with_vpn(self):
        profile = store.validate({"name": "test-us", "proxy": "vpn:protonvpn/us-wa-270.conf"}, self.vpn_dirs)
        self.assertEqual(profile.proxy, "vpn:protonvpn/us-wa-270.conf")
        self.assertEqual(profile.timezone, "auto")
        self.assertEqual(profile.locale, "en-US")

    def test_rejects_bad_names(self):
        for name in ["", "Abc", "../x", "a b", "-x", "x" * 41]:
            with self.subTest(name=name), self.assertRaises(store.ValidationError):
                store.validate({"name": name}, self.vpn_dirs)

    def test_rejects_missing_or_escaping_vpn_config(self):
        for proxy in ["vpn:protonvpn/missing.conf", "vpn:protonvpn/../x.conf", "vpn:other/x.conf", "ftp://h:21"]:
            with self.subTest(proxy=proxy), self.assertRaises(store.ValidationError):
                store.validate({"name": "a", "proxy": proxy}, self.vpn_dirs)

    def test_accepts_url_proxy(self):
        profile = store.validate({"name": "a", "proxy": "socks5://127.0.0.1:1080"}, self.vpn_dirs)
        self.assertEqual(profile.proxy, "socks5://127.0.0.1:1080")

    def test_rejects_bad_timezone_locale_and_url(self):
        bad = [{"timezone": "Mars/Base"}, {"locale": "english"}, {"start_url": "file:///etc/passwd"}]
        for extra in bad:
            with self.subTest(extra=extra), self.assertRaises(store.ValidationError):
                store.validate({"name": "a", **extra}, self.vpn_dirs)

    def test_list_vpn_configs(self):
        self.assertEqual(store.list_vpn_configs(self.vpn_dirs), ["vpn:protonvpn/us-wa-270.conf"])

    def test_save_load_roundtrip_and_upsert_remove(self):
        file = self.tmp / "profiles.json"
        a = store.validate({"name": "a"}, self.vpn_dirs)
        b = store.validate({"name": "b", "note": "x"}, self.vpn_dirs)
        profiles = store.upsert(store.upsert([], b), a)
        self.assertEqual([p.name for p in profiles], ["a", "b"])
        store.save(profiles, file)
        self.assertEqual(store.load(file), profiles)
        self.assertEqual(store.remove(profiles, "a"), [b])
        self.assertIsNone(store.find(profiles, "zzz"))

    def test_upsert_does_not_mutate_input(self):
        original = [store.validate({"name": "a"}, self.vpn_dirs)]
        store.upsert(original, store.validate({"name": "a", "note": "new"}, self.vpn_dirs))
        self.assertEqual(original[0].note, "")


if __name__ == "__main__":
    unittest.main()
