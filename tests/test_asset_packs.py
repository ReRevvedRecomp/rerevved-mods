"""Focused asset pack manifest, assembly, and archive checks."""

import contextlib
import copy
import io
import stat
import sys
import tempfile
import tomllib
import unittest
import warnings
import zipfile
from pathlib import Path, PurePosixPath
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

from build_asset_packs import (
    _copy_runtime_file,
    _remove_generated_directory,
    _validate_asset_relative,
    _validate_runtime_relative,
    _zip_entry_path,
    assemble_asset_pack,
    discover_asset_packs,
    load_asset_pack_manifest,
    package_asset_pack,
    parse_asset_pack_data,
    validate_runtime_tree,
    verify_asset_pack_archive,
)
from build_asset_packs import (
    main as build_main,
)
from build_mods import package_mod
from test_packaging import write_runtime
from verify import verify_packages
from verify_asset_packs import verify_asset_packs

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
    def write_source(self, root, asset=True):
        source = root / "asset-packs" / "example-pack"
        (source / "assets" / "file-data").mkdir(parents=True)
        (source / "asset-pack.toml").write_text(MANIFEST, encoding="ascii")
        if asset:
            (source / "assets" / "file-data" / "logo.dds").write_bytes(b"DDS payload")
        return source

    def test_empty_source_catalog_is_valid(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            self.assertEqual(discover_asset_packs(root / "asset-packs"), [])
            (root / "asset-packs").mkdir()
            self.assertEqual(discover_asset_packs(root / "asset-packs"), [])

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

    def test_manifest_rejects_invalid_tables_and_versions(self):
        for value in (None, [], "manifest", 1):
            with self.subTest(manifest=value):
                with self.assertRaisesRegex(
                    RuntimeError, "manifest must be a TOML table"
                ):
                    parse_asset_pack_data(value, "fixture")
        base = tomllib.loads(MANIFEST)
        for field, values, message in (
            (
                "manifest_version",
                (None, True, 1.0, "1", 0, 2),
                "manifest_version must be integer 1",
            ),
            ("asset_pack", (None, [], "pack", 1), r"\[asset_pack\] table is required"),
        ):
            value = copy.deepcopy(base)
            del value[field]
            with self.subTest(missing=field):
                with self.assertRaisesRegex(RuntimeError, message):
                    parse_asset_pack_data(value, "fixture")
            for invalid in values:
                with self.subTest(field=field, invalid=invalid):
                    value[field] = invalid
                    with self.assertRaisesRegex(RuntimeError, message):
                        parse_asset_pack_data(value, "fixture")

    def test_manifest_rejects_invalid_metadata(self):
        cases = {
            "id": ["Bad_ID", "a" * 64, "a--b", "", 1],
            "name": ["", " ", 1],
            "version": [
                "1",
                "1.0.0",
                "1.0-dev",
                "-1.0",
                "+1.0",
                chr(0x0661) + ".0",
                1,
            ],
            "author": [1],
            "description": [False],
        }
        for field, invalid_values in cases.items():
            for invalid in invalid_values:
                with self.subTest(field=field, invalid=invalid):
                    value = tomllib.loads(MANIFEST)
                    value["asset_pack"][field] = invalid
                    with self.assertRaisesRegex(RuntimeError, field):
                        parse_asset_pack_data(value, "fixture")
        for field in ("id", "name"):
            with self.subTest(missing=field):
                value = tomllib.loads(MANIFEST)
                del value["asset_pack"][field]
                with self.assertRaisesRegex(RuntimeError, "missing .*" + field):
                    parse_asset_pack_data(value, "fixture")
        with self.assertRaisesRegex(RuntimeError, "does not match"):
            parse_asset_pack_data(tomllib.loads(MANIFEST), "fixture", "other-pack")

    def test_manifest_warns_about_unknown_fields(self):
        for scope in ("top-level", "asset_pack"):
            with self.subTest(scope=scope):
                value = tomllib.loads(MANIFEST)
                table = value if scope == "top-level" else value[scope]
                table["unknown"] = "metadata"
                with contextlib.redirect_stderr(io.StringIO()) as warnings_output:
                    self.assertEqual(
                        parse_asset_pack_data(value, "fixture"), value["asset_pack"]
                    )
                self.assertIn("unknown", warnings_output.getvalue())

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
            self.assertEqual(
                discover_asset_packs(root / "asset-packs"), ["example-pack"]
            )

            assemble_asset_pack(root, "example-pack")
            runtime = root / "asset-overrides" / "example-pack"
            self.assertEqual(
                (runtime / "assets" / "file-data" / "logo.dds").read_bytes(),
                b"DDS payload",
            )
            package_asset_pack(root, "example-pack")
            archive = root / "pkg" / "asset-overrides" / "example-pack.zip"
            source_pack = load_asset_pack_manifest(
                source / "asset-pack.toml", "example-pack"
            )
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

    def test_same_id_mod_and_asset_archives_coexist(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            self.write_source(root)
            assemble_asset_pack(root, "example-pack")
            mod = write_runtime(
                root / "mods/example-pack",
                "example-pack",
                "Example Mod",
                b"return {}\n",
            )
            entry_path = "mods/example-pack/main.lua"
            source = root / "src" / "example-pack"
            source.mkdir(parents=True)
            (source / "mod.toml").write_bytes((mod / "mod.toml").read_bytes())

            package_mod(root, "example-pack")
            package_asset_pack(root, "example-pack")

            self.assertEqual(
                verify_packages(root, ["example-pack"]),
                {"example-pack": ["lua"]},
            )
            self.assertEqual(
                verify_asset_packs(root, check_packages=True), ["example-pack"]
            )
            with zipfile.ZipFile(root / "pkg" / "mods" / "example-pack.zip") as package:
                self.assertEqual(package.read(entry_path), b"return {}\n")
            with zipfile.ZipFile(
                root / "pkg" / "asset-overrides" / "example-pack.zip"
            ) as package:
                self.assertEqual(
                    package.read(
                        "asset-overrides/example-pack/assets/file-data/logo.dds"
                    ),
                    b"DDS payload",
                )

    def test_asset_pack_archive_rejects_explicit_special_entry_types(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source_pack = parse_asset_pack_data(tomllib.loads(MANIFEST), "fixture")
            archive = root / "fifo.zip"
            info = zipfile.ZipInfo(
                "asset-overrides/example-pack/assets/file-data/logo.dds"
            )
            info.external_attr = (stat.S_IFIFO | 0o644) << 16
            with zipfile.ZipFile(archive, "w") as output:
                output.writestr(
                    "asset-overrides/example-pack/asset-pack.toml", MANIFEST
                )
                output.writestr(info, b"DDS payload")
            with self.assertRaisesRegex(RuntimeError, "non-regular asset pack entry"):
                verify_asset_pack_archive(archive, "example-pack", source_pack)

    def test_asset_pack_runtime_requires_nonempty_assets(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            runtime = root / "asset-overrides" / "example-pack"
            runtime.mkdir(parents=True)
            (runtime / "asset-pack.toml").write_text(MANIFEST, encoding="ascii")
            with self.assertRaisesRegex(RuntimeError, "has no assets"):
                validate_runtime_tree(runtime)

    def test_asset_pack_paths_reject_parent_components(self):
        with self.assertRaisesRegex(RuntimeError, "invalid asset path"):
            _validate_asset_relative(PurePosixPath("../outside"))
        with self.assertRaisesRegex(RuntimeError, "invalid asset pack runtime path"):
            _validate_runtime_relative(PurePosixPath("assets/../outside"))

    def test_asset_pack_runtime_rejects_reparse_points(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            runtime = root / "asset-overrides" / "example-pack"
            linked = runtime / "assets" / "file-data" / "logo.dds"
            linked.parent.mkdir(parents=True)
            linked.write_bytes(b"DDS payload")
            (runtime / "asset-pack.toml").write_text(MANIFEST, encoding="ascii")
            with mock.patch(
                "build_asset_packs._is_reparse_point",
                side_effect=lambda path: path == linked,
            ):
                with self.assertRaisesRegex(RuntimeError, "reparse point"):
                    validate_runtime_tree(runtime)

    def test_archive_rejects_invalid_manifests_roots_and_empty_assets(self):
        manifest_name = "asset-overrides/example-pack/asset-pack.toml"
        asset = (
            "asset-overrides/example-pack/assets/file-data/logo.dds",
            b"DDS payload",
        )
        cases = (
            (
                "duplicate",
                [(manifest_name, MANIFEST), asset, asset],
                "duplicate asset pack entry",
            ),
            ("missing", [asset], "asset pack has no manifest"),
            ("toml", [(manifest_name, b"[")], "invalid asset pack manifest"),
            ("ascii", [(manifest_name, b"\xff")], "invalid asset pack manifest"),
            (
                "root",
                [("example-pack/asset-pack.toml", MANIFEST)],
                "not rooted at asset-overrides/example-pack",
            ),
            ("empty", [(manifest_name, MANIFEST)], "asset pack has no assets"),
            (
                "mismatch",
                [
                    (
                        manifest_name,
                        MANIFEST.replace('version = "1.0"', 'version = "2.0"'),
                    ),
                    asset,
                ],
                "manifest differs from source",
            ),
            (
                "raw path",
                [
                    (manifest_name, MANIFEST),
                    ("asset-overrides/example-pack/assets/./logo.dds", b"DDS payload"),
                ],
                "escapes its root",
            ),
        )
        pack = parse_asset_pack_data(tomllib.loads(MANIFEST), "fixture")
        with tempfile.TemporaryDirectory() as directory:
            archive = Path(directory) / "example-pack.zip"
            for label, entries, message in cases:
                with self.subTest(case=label):
                    with warnings.catch_warnings():
                        warnings.filterwarnings(
                            "ignore", message="Duplicate name:", category=UserWarning
                        )
                        with zipfile.ZipFile(archive, "w") as output:
                            for name, data in entries:
                                output.writestr(name, data)
                    with self.assertRaisesRegex(RuntimeError, message):
                        verify_asset_pack_archive(archive, "example-pack", pack)

    def test_zip_entry_paths_validate_raw_names(self):
        for name, message in (
            ("", "malformed archive entry"),
            ("asset-overrides/example-pack/", "malformed archive entry"),
            (
                "asset-overrides\\example-pack\\asset-pack.toml",
                "malformed archive entry",
            ),
            (
                "asset-overrides//example-pack/asset-pack.toml",
                "malformed archive entry",
            ),
            ("/asset-overrides/example-pack/asset-pack.toml", "escapes its root"),
            ("asset-overrides/example-pack/./asset-pack.toml", "escapes its root"),
            ("asset-overrides/example-pack/../asset-pack.toml", "escapes its root"),
        ):
            with self.subTest(name=name):
                with self.assertRaisesRegex(RuntimeError, message):
                    _zip_entry_path(Path("fixture.zip"), name)

    def test_assembly_preserves_optional_metadata_bytes(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = self.write_source(root)
            files = {
                "icon.png": b"icon",
                "README.md": b"readme\n",
                "LICENSE.txt": b"license\n",
            }
            for name, data in files.items():
                (source / name).write_bytes(data)
            assemble_asset_pack(root, "example-pack")
            runtime = root / "asset-overrides/example-pack"
            for name, data in files.items():
                with self.subTest(name=name):
                    self.assertEqual((runtime / name).read_bytes(), data)

    def test_source_discovery_rejects_reparse_points(self):
        for name, message in (
            (".", "source directory is a reparse point"),
            ("asset-pack.toml", "has no manifest"),
            ("assets", "assets must be a regular directory"),
            ("assets/file-data/logo.dds", "reparse point in assets"),
        ):
            with self.subTest(name=name), tempfile.TemporaryDirectory() as directory:
                root = Path(directory)
                source = self.write_source(root)
                linked = source / name
                with mock.patch(
                    "build_asset_packs._is_reparse_point",
                    side_effect=lambda path: path == linked,
                ):
                    with self.assertRaisesRegex(RuntimeError, message):
                        discover_asset_packs(root / "asset-packs")

    def test_metadata_copy_rejects_links_and_directories(self):
        for kind in ("link", "directory"):
            with self.subTest(kind=kind), tempfile.TemporaryDirectory() as directory:
                root = Path(directory)
                source = root / "README.md"
                destination = root / "copied.md"
                destination.write_bytes(b"keep")
                if kind == "directory":
                    source.mkdir()
                else:
                    source.write_bytes(b"readme\n")
                with mock.patch(
                    "build_asset_packs._is_reparse_point",
                    side_effect=lambda path: kind == "link" and path == source,
                ):
                    with self.assertRaisesRegex(
                        RuntimeError, "metadata must be a regular file"
                    ):
                        _copy_runtime_file(source, destination)
                self.assertEqual(destination.read_bytes(), b"keep")

    def test_generated_cleanup_stays_bounded_and_refuses_reparse_points(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            generated = root / "asset-overrides"
            package = generated / "example-pack"
            linked = package / "linked"
            linked.mkdir(parents=True)
            marker = linked / "keep.txt"
            marker.write_bytes(b"keep")
            with self.assertRaisesRegex(RuntimeError, "outside"):
                _remove_generated_directory(root / "outside/example-pack", generated)
            for reparse in (generated, package, linked):
                with (
                    self.subTest(reparse=reparse),
                    mock.patch(
                        "build_asset_packs._is_reparse_point",
                        side_effect=lambda path: path == reparse,
                    ),
                ):
                    with self.assertRaisesRegex(RuntimeError, "reparse point"):
                        _remove_generated_directory(package, generated)
                    self.assertEqual(marker.read_bytes(), b"keep")

    def test_generated_cleanup_replaces_only_selected_output(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            generated = root / "asset-overrides"
            package = generated / "example-pack"
            stale = package / "nested/stale.txt"
            stale.parent.mkdir(parents=True)
            stale.write_bytes(b"stale")
            sibling = generated / "other-pack/keep.txt"
            sibling.parent.mkdir()
            sibling.write_bytes(b"keep")
            _remove_generated_directory(package, generated)
            self.assertTrue(package.is_dir())
            self.assertEqual(list(package.iterdir()), [])
            self.assertEqual(sibling.read_bytes(), b"keep")

    def test_build_cli_selection_listing_and_package_flag(self):
        cases = (
            ("default", [], ["a-pack", "z-pack"], ["a-pack", "z-pack"], [], None),
            (
                "selected",
                ["--pack", "z-pack"],
                ["a-pack", "z-pack"],
                ["z-pack"],
                [],
                None,
            ),
            (
                "package",
                ["--pack", "z-pack", "--package"],
                ["a-pack", "z-pack"],
                ["z-pack"],
                ["z-pack"],
                None,
            ),
            (
                "list",
                ["--list", "--package"],
                ["a-pack", "z-pack"],
                [],
                [],
                "a-pack\nz-pack\n",
            ),
            ("unknown", ["--pack", "missing"], ["a-pack", "z-pack"], [], [], None),
        )
        for label, arguments, available, selected, packaged, output in cases:
            with (
                self.subTest(case=label),
                mock.patch.object(sys, "argv", ["build_asset_packs.py", *arguments]),
                mock.patch(
                    "build_asset_packs.discover_asset_packs", return_value=available
                ),
                mock.patch("build_asset_packs.assemble_asset_pack") as assemble,
                mock.patch("build_asset_packs.package_asset_pack") as package,
                contextlib.redirect_stdout(io.StringIO()) as stdout,
            ):
                if label == "unknown":
                    with self.assertRaisesRegex(
                        RuntimeError, r"unknown asset pack\(s\): missing"
                    ):
                        build_main()
                else:
                    build_main()
                root = Path(__file__).resolve().parents[1]
                self.assertEqual(
                    assemble.call_args_list,
                    [mock.call(root, name) for name in selected],
                )
                self.assertEqual(
                    package.call_args_list,
                    [mock.call(root, name) for name in packaged],
                )
                if output is not None:
                    self.assertEqual(stdout.getvalue(), output)

    def test_source_only_verification_and_missing_archive(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            self.write_source(root)
            self.assertEqual(
                verify_asset_packs(root, check_packages=False), ["example-pack"]
            )
            with self.assertRaisesRegex(RuntimeError, "missing asset pack package"):
                verify_asset_packs(root, check_packages=True)


if __name__ == "__main__":
    unittest.main()
