"""Focused map pack manifest and layout checks."""

import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))

from verify_map_packs import verify_map_packs

MANIFEST = """\
manifest_version = 1

[asset_pack]
id = "{id}"
name = "Example Map"
version = "1.0"
author = "Aeshur"
description = "Example map pack."

[map_pack]
slot = {slot}

[[map_pack.scenarios]]
id = {scenario}
name = "Example Map"
"""


class MapPackTests(unittest.TestCase):
    def write_pack(
        self, root, pack_id="example-map", slot=5, scenario=100, folder=None
    ):
        pack = root / "maps" / (folder or pack_id)
        (pack / "assets" / "map-pack").mkdir(parents=True)
        (pack / "asset-pack.toml").write_text(
            MANIFEST.format(id=pack_id, slot=slot, scenario=scenario), encoding="ascii"
        )
        (pack / "assets" / "map-pack" / "dlc.fpk").write_bytes(b"FPK payload")
        return pack

    def test_shipped_packs_pass(self):
        root = Path(__file__).resolve().parents[1]
        self.assertIn("west-vs-east-duel", verify_map_packs(root))

    def test_missing_or_empty_maps_folder_is_valid(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            self.assertEqual(verify_map_packs(root), [])
            (root / "maps").mkdir()
            self.assertEqual(verify_map_packs(root), [])

    def test_valid_packs_return_sorted_ids(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            self.write_pack(root, "b-map", slot=6, scenario=101)
            self.write_pack(root, "a-map", slot=5, scenario=100)
            self.assertEqual(verify_map_packs(root), ["a-map", "b-map"])

    def test_rejects_extra_file(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            pack = self.write_pack(root)
            (pack / "README.md").write_text("extra", encoding="ascii")
            with self.assertRaisesRegex(RuntimeError, "must hold exactly"):
                verify_map_packs(root)

    def test_rejects_empty_payload(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            pack = self.write_pack(root)
            (pack / "assets" / "map-pack" / "dlc.fpk").write_bytes(b"")
            with self.assertRaisesRegex(RuntimeError, "payload is empty"):
                verify_map_packs(root)

    def test_rejects_slot_below_five(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            self.write_pack(root, slot=4)
            with self.assertRaisesRegex(
                RuntimeError, r"slot must be an integer 5\.\.31"
            ):
                verify_map_packs(root)

    def test_rejects_scenario_id_below_100(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            self.write_pack(root, scenario=99)
            with self.assertRaisesRegex(RuntimeError, "scenario id must be"):
                verify_map_packs(root)

    def test_rejects_folder_id_mismatch(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            self.write_pack(root, pack_id="example-map", folder="other-map")
            with self.assertRaisesRegex(RuntimeError, "does not match folder"):
                verify_map_packs(root)

    def test_rejects_id_too_long_for_content_name(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            self.write_pack(root, pack_id="a" * 40)
            with self.assertRaisesRegex(RuntimeError, "not a valid package ID"):
                verify_map_packs(root)

    def test_rejects_non_numeric_version(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            pack = self.write_pack(root)
            manifest = pack / "asset-pack.toml"
            manifest.write_text(
                manifest.read_text(encoding="ascii").replace('"1.0"', '"bad"'),
                encoding="ascii",
            )
            with self.assertRaisesRegex(RuntimeError, "major.minor"):
                verify_map_packs(root)

    def test_rejects_shared_slot(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            self.write_pack(root, "a-map", slot=5, scenario=100)
            self.write_pack(root, "b-map", slot=5, scenario=101)
            with self.assertRaisesRegex(RuntimeError, "slot 5 is also used"):
                verify_map_packs(root)

    def test_rejects_repeated_scenario_id(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            self.write_pack(root, "a-map", slot=5, scenario=100)
            self.write_pack(root, "b-map", slot=6, scenario=100)
            with self.assertRaisesRegex(RuntimeError, "scenario id 100 is also used"):
                verify_map_packs(root)


if __name__ == "__main__":
    unittest.main()
