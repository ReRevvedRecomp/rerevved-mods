"""Focused asset pack manifest, assembly, and archive checks."""

import sys
import tempfile
import unittest
import zipfile
from pathlib import Path, PurePosixPath
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

from build_asset_packs import (
    _validate_asset_relative,
    _validate_runtime_relative,
    assemble_asset_pack,
    discover_asset_packs,
    load_asset_pack_manifest,
    package_asset_pack,
    parse_asset_pack_data,
    validate_runtime_tree,
    verify_asset_pack_archive,
    verify_asset_pack_sources,
)


MANIFEST = """\
manifest_version = 1

[asset_pack]
id = "example-pack"
name = "Example Pack"
version = "1.0"
author = "Aeshur"
description = "Example title asset pack."
"""


class AssetPackTests(unittest.TestCase):
    def write_source(self, root, manifest=MANIFEST, asset=True):
        source = root / "asset-packs" / "example-pack"
        (source / "assets" / "file-data").mkdir(parents=True)
        (source / "asset-pack.toml").write_text(manifest, encoding="ascii")
        if asset:
            (source / "assets" / "file-data" / "logo.dds").write_bytes(b"DDS payload")
        return source

    def test_empty_source_catalog_is_valid(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "asset-packs").mkdir()
            self.assertEqual(verify_asset_pack_sources(root), [])

    def test_manifest_requires_asset_pack_identity_and_version(self):
        pack = parse_asset_pack_data(
            {
                "manifest_version": 1,
                "asset_pack": {
                    "id": "example-pack",
                    "name": "Example Pack",
                    "version": "1.0",
                },
            },
            "fixture",
        )
        self.assertEqual(pack["id"], "example-pack")
        with self.assertRaisesRegex(RuntimeError, "missing .*version"):
            parse_asset_pack_data(
                {
                    "manifest_version": 1,
                    "asset_pack": {"id": "example-pack", "name": "Example Pack"},
                },
                "fixture",
            )

    def test_discovery_rejects_empty_asset_tree(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            self.write_source(root, asset=False)
            with self.assertRaisesRegex(RuntimeError, "nonempty assets"):
                discover_asset_packs(root / "asset-packs")

    def test_asset_pack_assembles_and_packages_under_asset_overrides(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = self.write_source(root)
            self.assertEqual(discover_asset_packs(root / "asset-packs"), ["example-pack"])

            assemble_asset_pack(root, "example-pack")
            runtime = root / "asset-overrides" / "example-pack"
            self.assertEqual(
                (runtime / "assets" / "file-data" / "logo.dds").read_bytes(),
                b"DDS payload",
            )
            package_asset_pack(root, "example-pack")
            archive = root / "pkg" / "example-pack.zip"
            source_pack = load_asset_pack_manifest(source / "asset-pack.toml", "example-pack")
            self.assertEqual(
                verify_asset_pack_archive(archive, "example-pack", source_pack),
                ["assets/file-data/logo.dds"],
            )
            with zipfile.ZipFile(archive) as package:
                self.assertEqual(
                    package.namelist(),
                    [
                        "asset-overrides/example-pack/asset-pack.toml",
                        "asset-overrides/example-pack/assets/file-data/logo.dds",
                    ],
                )

    def test_asset_pack_runtime_requires_nonempty_assets(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = self.write_source(root, asset=False)
            runtime = root / "asset-overrides" / "example-pack"
            runtime.mkdir(parents=True)
            (runtime / "asset-pack.toml").write_text(
                (source / "asset-pack.toml").read_text(encoding="ascii"),
                encoding="ascii",
            )
            pack = load_asset_pack_manifest(runtime / "asset-pack.toml", "example-pack")
            with self.assertRaisesRegex(RuntimeError, "has no assets"):
                validate_runtime_tree(runtime, pack)

    def test_asset_pack_paths_reject_parent_components(self):
        with self.assertRaisesRegex(RuntimeError, "invalid asset path"):
            _validate_asset_relative(PurePosixPath("../outside"))
        with self.assertRaisesRegex(RuntimeError, "invalid asset pack runtime path"):
            _validate_runtime_relative(PurePosixPath("assets/../outside"))

    def test_asset_pack_runtime_rejects_reparse_points(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = self.write_source(root)
            assemble_asset_pack(root, "example-pack")
            runtime = root / "asset-overrides" / "example-pack"
            pack = load_asset_pack_manifest(source / "asset-pack.toml", "example-pack")
            linked = runtime / "assets" / "file-data" / "logo.dds"
            with mock.patch("build_asset_packs._is_reparse_point", side_effect=lambda path: path == linked):
                with self.assertRaisesRegex(RuntimeError, "reparse point"):
                    validate_runtime_tree(runtime, pack)


if __name__ == "__main__":
    unittest.main()
