"""Focused native runtime package checks."""

import sys
import tempfile
import unittest
import zipfile
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

from build_mods import (
    _remove_generated_directory,
    discover_mods,
    load_manifest,
    validate_runtime_tree,
)
from verify import verify_package_archive


MANIFEST = """\
manifest_version = 1

[mod]
id = "example-test"
name = "Example Test"
version = "1.0"
code = "example_test"
plugin_abi = 1
"""


class PackagingTests(unittest.TestCase):
    def test_discovery_uses_package_ids(self):
        self.assertEqual(
            discover_mods(Path(__file__).resolve().parents[1] / "src"),
            [
                "mongol-horseback-riding",
                "roman-cataphracts-defense",
                "state-inspector",
            ],
        )

    def write_runtime(self, root, binary="example_test.dll"):
        package = root / "mods" / "example-test"
        (package / "code" / "windows-x64").mkdir(parents=True)
        (package / "mod.toml").write_text(MANIFEST, encoding="ascii")
        (package / "code" / "windows-x64" / binary).write_bytes(b"plugin")
        return package

    def test_runtime_tree_rejects_source_leakage(self):
        with tempfile.TemporaryDirectory() as directory:
            package = self.write_runtime(Path(directory))
            (package / "CMakeLists.txt").write_text("project(leak)", encoding="ascii")
            mod = load_manifest(package / "mod.toml", "example-test")
            with self.assertRaisesRegex(RuntimeError, "source or unsupported"):
                validate_runtime_tree(package, mod)

    def test_archive_requires_runtime_root_and_qualified_binary(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            package = self.write_runtime(root)
            source_mod = load_manifest(package / "mod.toml", "example-test")
            archive = root / "example-test.zip"
            with zipfile.ZipFile(archive, "w") as output:
                output.write(
                    package / "mod.toml",
                    "mods/example-test/mod.toml",
                )
                output.writestr(
                    "mods/example-test/code/windows-x64/example_test.dll",
                    b"plugin",
                )
            self.assertEqual(
                verify_package_archive(archive, "example-test", source_mod),
                ["windows-x64"],
            )

            malformed = root / "malformed.zip"
            with zipfile.ZipFile(malformed, "w") as output:
                output.writestr("example-test/mod.toml", MANIFEST)
                output.writestr("example-test/code/windows-x64/example_test.dll", b"plugin")
            with self.assertRaisesRegex(RuntimeError, "rooted at mods/example-test"):
                verify_package_archive(malformed, "example-test", source_mod)

    def test_debug_and_relwithdebinfo_stems_are_qualified(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            package = self.write_runtime(root)
            for binary in ("example_testd.dll", "example_testrd.dll"):
                (package / "code" / "windows-x64" / binary).write_bytes(b"plugin")
            mod = load_manifest(package / "mod.toml", "example-test")
            self.assertEqual(len(validate_runtime_tree(package, mod)), 4)
            archive = root / "example-test.zip"
            with zipfile.ZipFile(archive, "w") as output:
                output.write(package / "mod.toml", "mods/example-test/mod.toml")
                for binary in ("example_test.dll", "example_testd.dll", "example_testrd.dll"):
                    output.writestr(
                        f"mods/example-test/code/windows-x64/{binary}",
                        b"plugin",
                    )
            self.assertEqual(
                verify_package_archive(archive, "example-test", mod),
                ["windows-x64"],
            )

    def test_manifest_version_requires_an_integer(self):
        with self.assertRaisesRegex(RuntimeError, "manifest_version must be integer 1"):
            from build_mods import parse_manifest_data

            parse_manifest_data(
                {
                    "manifest_version": 1.0,
                    "mod": {
                        "id": "example-test",
                        "name": "Example Test",
                        "version": "1.0",
                        "code": "example_test",
                        "plugin_abi": 1,
                    },
                },
                "fixture",
            )

    def test_optional_minimum_game_version_is_supported(self):
        from build_mods import parse_manifest_data

        manifest = parse_manifest_data(
            {
                "manifest_version": 1,
                "mod": {
                    "id": "example-test",
                    "name": "Example Test",
                    "version": "1.0",
                    "min_game_version": "2.3.4",
                    "code": "example_test",
                    "plugin_abi": 1,
                },
            },
            "fixture",
        )
        self.assertEqual(manifest["min_game_version"], "2.3.4")

    def test_package_version_requires_exact_numeric_major_minor(self):
        from build_mods import parse_manifest_data

        for version in (
            "1",
            "1.0.0",
            "",
            "1..0",
            "-1.0",
            "+1.0",
            "1.0-alpha",
            chr(0x0661) + ".0",
        ):
            with self.subTest(version=version):
                with self.assertRaisesRegex(
                    RuntimeError, "version must use numeric major.minor syntax"
                ):
                    parse_manifest_data(
                        {
                            "manifest_version": 1,
                            "mod": {
                                "id": "example-test",
                                "name": "Example Test",
                                "version": version,
                                "code": "example_test",
                                "plugin_abi": 1,
                            },
                        },
                        "fixture",
                    )

    def test_minimum_game_version_keeps_strict_three_component_grammar(self):
        from build_mods import parse_manifest_data

        for version in (
            "2.3",
            "2.3.4.5",
            "",
            "2..4",
            "-2.3.4",
            "+2.3.4",
            "2.3.4-dev",
            chr(0x0662) + ".3.4",
        ):
            with self.subTest(version=version):
                with self.assertRaisesRegex(
                    RuntimeError,
                    "min_game_version must use numeric major.minor.patch syntax",
                ):
                    parse_manifest_data(
                        {
                            "manifest_version": 1,
                            "mod": {
                                "id": "example-test",
                                "name": "Example Test",
                                "version": "1.0",
                                "min_game_version": version,
                                "code": "example_test",
                                "plugin_abi": 1,
                            },
                        },
                        "fixture",
                    )

    def test_generated_cleanup_stays_bounded_and_refuses_reparse_points(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            generated = root / "mods"
            package = generated / "example-test"
            linked = package / "linked"
            linked.mkdir(parents=True)
            marker = linked / "keep.txt"
            marker.write_text("keep", encoding="ascii")

            with self.assertRaisesRegex(RuntimeError, "outside"):
                _remove_generated_directory(root / "outside" / "example-test", generated)

            def is_reparse_point(path):
                return path == linked

            with mock.patch("build_mods._is_reparse_point", side_effect=is_reparse_point):
                with self.assertRaisesRegex(RuntimeError, "reparse point"):
                    _remove_generated_directory(package, generated)
            self.assertTrue(marker.is_file())


if __name__ == "__main__":
    unittest.main()
