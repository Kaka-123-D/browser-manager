import tempfile
import unittest
from pathlib import Path
from unittest import mock

from bm import paths, store
from bm.manager import Manager


class RenameTest(unittest.TestCase):
    def setUp(self):
        tmp = Path(tempfile.mkdtemp())
        patches = {
            "DATA_DIR": tmp, "PROFILES_FILE": tmp / "profiles.json", "PROFILE_DATA_DIR": tmp / "profiles",
            "PROXY_CONF_DIR": tmp / "proxies", "LOG_DIR": tmp / "logs", "VPN_DIRS": {},
        }
        for attr, value in patches.items():
            patcher = mock.patch.object(paths, attr, value)
            patcher.start()
            self.addCleanup(patcher.stop)
        self.manager = Manager()
        self.manager.save_profile({"name": "old", "note": "n"})
        (paths.PROFILE_DATA_DIR / "old").mkdir()
        (paths.PROFILE_DATA_DIR / "old" / "Cookies").write_text("x")

    def names(self):
        return [p["name"] for p in self.manager.state()["profiles"]]

    def test_rename_moves_record_and_chrome_data(self):
        self.manager.save_profile({"name": "new", "rename_from": "old", "note": "n2"})
        self.assertEqual(self.names(), ["new"])
        self.assertTrue((paths.PROFILE_DATA_DIR / "new" / "Cookies").exists())
        self.assertFalse((paths.PROFILE_DATA_DIR / "old").exists())

    def test_rename_onto_existing_profile_is_refused(self):
        self.manager.save_profile({"name": "other"})
        with self.assertRaises(store.ValidationError):
            self.manager.save_profile({"name": "other", "rename_from": "old"})
        self.assertEqual(self.names(), ["old", "other"])

    def test_rename_from_unknown_profile_is_refused(self):
        with self.assertRaises(store.ValidationError):
            self.manager.save_profile({"name": "x", "rename_from": "ghost"})


if __name__ == "__main__":
    unittest.main()
