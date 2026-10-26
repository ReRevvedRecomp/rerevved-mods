"""Focused Lua runtime package checks."""

import contextlib
import copy
import io
import json
import stat
import sys
import tempfile
import tomllib
import unittest
import warnings
import zipfile
from pathlib import Path, PurePosixPath
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))

from build_mods import (
    _remove_generated_directory,
    _validate_lua_relative,
    assemble_lua_mod,
    discover_mods,
    load_manifest,
    package_mod,
    parse_manifest_data,
    validate_lua_binary_header,
    validate_lua_source,
    validate_runtime_tree,
)
from build_mods import (
    main as build_main,
)
from verify import (
    _zip_entry_path,
    load_lock,
    verify_locks,
    verify_manifests,
    verify_package_archive,
    verify_packages,
    verify_public_tree,
    verify_title_checkout,
)

LUA_MANIFEST = """\
manifest_version = 2

[mod]
id = "example-test"
name = "Example Test"
version = "1.0"

[payload]
kind = "lua"
entry = "main.lua"
api = "rerevved.rules"
api_version = 1
requires = ["terrain_yield"]
"""
LUA_SOURCE = b'return { provider_id = "example.test", rules = {} }\n'
LUA_PACKAGES = {
    "founding-militia": ["city_founding_unit"],
    "hills-production": ["terrain_yield"],
    "jaguar-woodsman": ["unit_combat", "nation_select_text"],
    "cataphracts-defense": ["unique_unit_scalar", "nation_select_text"],
    "keshik-movement": ["unit_movement", "nation_select_text"],
    "hoplite-loyalty": ["unit_effect", "unit_production_cost", "nation_select_text"],
    "mongol-horseback": ["era_technology_ability", "nation_select_text"],
    "stonehenge-religion": ["wonder_completion_technology"],
    "chinese-library-gold": ["building_yield"],
}


def write_runtime(destination, package_id, name="Example Test", source=LUA_SOURCE):
    destination.mkdir(parents=True)
    manifest = LUA_MANIFEST.replace(
        'id = "example-test"', f'id = "{package_id}"'
    ).replace('name = "Example Test"', f'name = "{name}"')
    (destination / "mod.toml").write_text(manifest, encoding="ascii", newline="\n")
    (destination / "main.lua").write_bytes(source)
    return destination


class LuaPackagingTests(unittest.TestCase):
    def test_repository_manifest_catalog(self):
        repository = Path(__file__).resolve().parents[1]
        discovered = discover_mods(repository / "mods")
        self.assertEqual(
            discovered,
            [
                "cataphracts-defense",
                "chinese-library-gold",
                "founding-militia",
                "hills-production",
                "hoplite-loyalty",
                "jaguar-woodsman",
                "keshik-movement",
                "mongol-horseback",
                "stonehenge-religion",
            ],
        )
        self.assertEqual(discovered, sorted(LUA_PACKAGES))
        for package_id, requires in LUA_PACKAGES.items():
            with self.subTest(package_id=package_id):
                source = repository / "mods" / package_id
                manifest = tomllib.loads((source / "mod.toml").read_text("ascii"))
                parse_manifest_data(manifest, source / "mod.toml", package_id)
                self.assertEqual(manifest["manifest_version"], 2)
                self.assertEqual(
                    manifest["payload"],
                    {
                        "kind": "lua",
                        "entry": "main.lua",
                        "api": "rerevved.rules",
                        "api_version": 1,
                        "requires": requires,
                    },
                )

    def write_source(self, root):
        return write_runtime(root / "mods" / "example-test", "example-test")

    def test_lua_manifest_valid_contract(self):
        value = tomllib.loads(LUA_MANIFEST)
        value["mod"].update(author="", description="", min_game_version="1.0.0")
        value["payload"].update(
            api="another.api",
            api_version=0xFFFFFFFF,
            requires=["terrain_yield", "domain-2", "a" * 63],
        )
        for version in ("1.0.0", "2.3.4"):
            with self.subTest(min_game_version=version):
                value["mod"]["min_game_version"] = version
                parsed = parse_manifest_data(value, "fixture", "example-test")
                self.assertEqual(parsed, {**value["mod"], "payload": value["payload"]})
                self.assertEqual(parsed["min_game_version"], version)

    def test_lua_manifest_requires_tables(self):
        for value in (None, [], "manifest", 1):
            with self.subTest(manifest=value):
                with self.assertRaisesRegex(
                    RuntimeError, "manifest must be a TOML table"
                ):
                    parse_manifest_data(value, "fixture")
        base = tomllib.loads(LUA_MANIFEST)
        del base["mod"]
        with self.assertRaisesRegex(RuntimeError, r"\[mod\] table is required"):
            parse_manifest_data(base, "fixture")
        for mod in (None, [], "mod", 1):
            with self.subTest(mod=mod):
                base["mod"] = mod
                with self.assertRaisesRegex(RuntimeError, r"\[mod\] table is required"):
                    parse_manifest_data(base, "fixture")

    def test_lua_manifest_invalid_payload_values(self):
        cases = {
            "kind": ["native", "Lua", "", 1, True, {}],
            "entry": ["", 1, True, [], "main.txt", ".lua"],
            "api": ["", "  ", 1, True, []],
            "api_version": [0, -1, 0x100000000, True, 1.0, "1", []],
            "requires": [
                [],
                "terrain_yield",
                [""],
                [" "],
                [1],
                [True],
                [{}],
                ["Terrain"],
                ["a" * 64],
                ["terrain.yield"],
                ["terrain/yield"],
                ["terrain_yield", "terrain_yield"],
            ],
        }
        for field, invalid_values in cases.items():
            for invalid in invalid_values:
                with self.subTest(field=field, invalid=invalid):
                    value = tomllib.loads(LUA_MANIFEST)
                    value["payload"][field] = invalid
                    with self.assertRaisesRegex(RuntimeError, field):
                        parse_manifest_data(value, "fixture")

    def test_lua_manifest_missing_unknown_and_native_fields(self):
        base = tomllib.loads(LUA_MANIFEST)
        for scope in ("top-level", "mod", "payload"):
            for field in ("code", "plugin_abi"):
                with self.subTest(scope=scope, field=field):
                    value = copy.deepcopy(base)
                    table = value if scope == "top-level" else value[scope]
                    table[field] = "native"
                    with self.assertRaisesRegex(RuntimeError, "native field"):
                        parse_manifest_data(value, "fixture")
        for scope in ("top-level", "mod"):
            with self.subTest(scope=scope, field="unknown"):
                value = copy.deepcopy(base)
                table = value if scope == "top-level" else value[scope]
                table["unknown"] = "metadata"
                warnings = io.StringIO()
                with contextlib.redirect_stderr(warnings):
                    parse_manifest_data(value, "fixture")
                self.assertIn("unknown", warnings.getvalue())
        nested = copy.deepcopy(base)
        nested["extra"] = {"items": [{"code": "x"}]}
        with self.assertRaisesRegex(RuntimeError, "native field"):
            parse_manifest_data(nested, "fixture")
        unknown_payload = copy.deepcopy(base)
        unknown_payload["payload"]["unknown"] = "x"
        with self.assertRaisesRegex(RuntimeError, "unknown"):
            parse_manifest_data(unknown_payload, "fixture")
        for field in base["payload"]:
            with self.subTest(missing=field):
                value = copy.deepcopy(base)
                del value["payload"][field]
                with self.assertRaisesRegex(RuntimeError, "missing"):
                    parse_manifest_data(value, "fixture")
        for payload in (None, [], [base["payload"]], "lua", 1):
            with self.subTest(payload=payload):
                value = copy.deepcopy(base)
                value["payload"] = payload
                with self.assertRaisesRegex(RuntimeError, "one .*payload.* table"):
                    parse_manifest_data(value, "fixture")
        del base["payload"]
        with self.assertRaisesRegex(RuntimeError, "payload"):
            parse_manifest_data(base, "fixture")

    def test_lua_manifest_rejects_duplicate_payload_tables(self):
        with tempfile.TemporaryDirectory() as directory:
            package = Path(directory)
            for extra in ("\n[payload]\n", "\n[[payload]]\n"):
                with self.subTest(extra=extra):
                    (package / "mod.toml").write_text(
                        LUA_MANIFEST + extra, encoding="ascii"
                    )
                    with self.assertRaisesRegex(RuntimeError, "invalid TOML"):
                        load_manifest(package / "mod.toml")

    def test_lua_manifest_preserves_metadata_rules(self):
        cases = {
            "id": ["Bad_ID", "a" * 64, "a--b", ""],
            "name": ["", " ", 1],
            "author": [1],
            "description": [False],
        }
        for field, invalid_values in cases.items():
            for invalid in invalid_values:
                with self.subTest(field=field, invalid=invalid):
                    value = tomllib.loads(LUA_MANIFEST)
                    value["mod"][field] = invalid
                    with self.assertRaises(RuntimeError):
                        parse_manifest_data(value, "fixture")
        for field in ("id", "name", "version"):
            value = tomllib.loads(LUA_MANIFEST)
            del value["mod"][field]
            with self.assertRaisesRegex(RuntimeError, "missing"):
                parse_manifest_data(value, "fixture")
        with self.assertRaisesRegex(RuntimeError, "does not match"):
            parse_manifest_data(tomllib.loads(LUA_MANIFEST), "fixture", "other-mod")

    def test_lua_manifest_version_requires_integer_two(self):
        for version in (True, False, 2.0, "2", 0, 3):
            with self.subTest(version=version):
                value = tomllib.loads(LUA_MANIFEST)
                value["manifest_version"] = version
                with mock.patch("sys.stderr", new_callable=io.StringIO):
                    with self.assertRaisesRegex(
                        RuntimeError, "manifest_version must be integer 2"
                    ):
                        parse_manifest_data(value, "fixture")

    def test_first_party_manifest_rejects_version_one(self):
        value = tomllib.loads(LUA_MANIFEST)
        value["manifest_version"] = 1
        with self.assertRaisesRegex(RuntimeError, "first-party packages are Lua"):
            parse_manifest_data(value, "fixture")

    def test_lua_manifest_rejects_unsafe_entries(self):
        for entry in (
            "../main.lua",
            "./main.lua",
            "sub/main.lua",
            "sub\\main.lua",
            "/main.lua",
            "C:main.lua",
            "C:/main.lua",
            "\\\\server\\main.lua",
            "\\\\?\\C:\\main.lua",
            "CON.lua",
            "aux.lua",
            "LPT1.lua",
            "main:stream.lua",
            "main?.lua",
            "main\x00.lua",
            ".",
            "..",
        ):
            with self.subTest(entry=entry):
                value = tomllib.loads(LUA_MANIFEST)
                value["payload"]["entry"] = entry
                with self.assertRaisesRegex(RuntimeError, "entry"):
                    parse_manifest_data(value, "fixture")

    def test_lua_source_style_and_size(self):
        for data, error in (
            (b"return {}\r\n", "LF"),
            (b"return {}", "final newline"),
            (b"\treturn {}\n", "tabs"),
            (b"return {} \n", "trailing whitespace"),
            (b"\xef\xbb\xbfreturn {}\n", "BOM"),
            (b"-- \xff\n", "ASCII"),
            (b"\x1bLua\x54\n", "bytecode"),
            (b"\x1bLua\n", "bytecode"),
            (b"x" * 262144 + b"\n", "256 KiB"),
        ):
            with self.subTest(error=error):
                with self.assertRaisesRegex(RuntimeError, error):
                    validate_lua_source(data, "fixture")
        validate_lua_source(b"-" * 262143 + b"\n", "fixture")

    def test_lua_source_disk_style_and_size(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            package = self.write_source(root)
            (package / "main.lua").write_bytes(b"-" * 262143 + b"\n")
            self.assertEqual(verify_manifests(root), ["example-test"])
            for data, error in (
                (b"return {}\r\n", "LF"),
                (b"x" * 262144 + b"\n", "256 KiB"),
            ):
                with self.subTest(error=error):
                    (package / "main.lua").write_bytes(data)
                    with self.assertRaisesRegex(RuntimeError, error):
                        verify_manifests(root)

    def test_lua_relative_paths_reject_native_files(self):
        for name in (
            "CMakeLists.txt",
            "mod_main.cpp",
            "source.c",
            "source.cc",
            "source.cxx",
            "header.hpp",
            "code",
            "assets/code",
            "assets/helper.cpp",
            "assets/helper.cmake",
            "assets/cmakelists.txt",
            "assets/plugin.dll",
            "assets/plugin.exe",
            "assets/lib.so.1",
        ):
            with self.subTest(name=name):
                with self.assertRaisesRegex(RuntimeError, "native|code/"):
                    _validate_lua_relative(PurePosixPath(name), "main.lua")

    def test_lua_source_rejects_native_files_and_code_directory(self):
        for name, message in (
            ("CMakeLists.txt", "native source"),
            ("code", "code/"),
            ("assets/code", "code/"),
        ):
            with self.subTest(name=name), tempfile.TemporaryDirectory() as directory:
                root = Path(directory)
                package = self.write_source(root)
                extra = package / name
                extra.parent.mkdir(parents=True, exist_ok=True)
                if extra.name == "code":
                    extra.mkdir()
                else:
                    extra.write_text("project(leak)", encoding="ascii")
                with self.assertRaisesRegex(RuntimeError, message):
                    discover_mods(root / "mods")

    def test_lua_entry_must_exist_and_be_regular(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            package = self.write_source(root)
            entry = package / "main.lua"
            entry.unlink()
            with self.assertRaisesRegex(RuntimeError, "regular file"):
                discover_mods(root / "mods")
            entry.mkdir()
            with self.assertRaisesRegex(RuntimeError, "unsupported directory"):
                discover_mods(root / "mods")

    def test_lua_reparse_points_rejected_before_assembly(self):
        for linked_name in (".", "mod.toml", "main.lua", "assets", "assets/item"):
            with (
                self.subTest(linked=linked_name),
                tempfile.TemporaryDirectory() as directory,
            ):
                root = Path(directory)
                package = self.write_source(root)
                (package / "assets").mkdir()
                (package / "assets/item").write_bytes(b"asset")
                linked = package / linked_name
                with mock.patch(
                    "build_mods._is_reparse_point",
                    side_effect=lambda path: path == linked,
                ):
                    with self.assertRaisesRegex(RuntimeError, "reparse point"):
                        discover_mods(root / "mods")
                    with self.assertRaisesRegex(RuntimeError, "reparse point"):
                        assemble_lua_mod(root, "example-test")
                self.assertFalse((root / "out" / "mods").exists())

    def test_lua_only_build_packages_without_sdk_or_compiler(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            self.write_source(root)
            with (
                mock.patch("build_mods.__file__", str(root / "tools/build_mods.py")),
                mock.patch.object(
                    sys, "argv", ["build_mods.py", "--mod", "example-test"]
                ),
                mock.patch.dict("os.environ", {"PATH": ""}),
                mock.patch("sys.stdout", new_callable=io.StringIO),
            ):
                build_main()
            archive = root / "out/pkg/mods/example-test.zip"
            with zipfile.ZipFile(archive) as package:
                self.assertEqual(
                    sorted(package.namelist()),
                    ["mods/example-test/main.lua", "mods/example-test/mod.toml"],
                )
                for name in ("main.lua", "mod.toml"):
                    self.assertEqual(
                        package.read(f"mods/example-test/{name}"),
                        (root / "mods/example-test" / name).read_bytes(),
                    )
                self.assertEqual(package.read("mods/example-test/main.lua"), LUA_SOURCE)
            mod = load_manifest(root / "mods/example-test/mod.toml")
            self.assertEqual(
                verify_package_archive(archive, "example-test", mod), ["lua"]
            )
            self.assertEqual(
                verify_packages(root, ["example-test"]), {"example-test": ["lua"]}
            )

    def test_lua_assembly_preserves_optional_files_and_assets(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = self.write_source(root)
            for name in (
                "README.md",
                "LICENSE.txt",
                "icon.png",
                "assets/nested/image.dds",
            ):
                path = source / name
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_bytes(b"asset")
            asset = source / "assets/nested/logo.dds"
            asset.write_bytes(b"DDS payload")
            assemble_lua_mod(root, "example-test")
            mod = load_manifest(source / "mod.toml")
            self.assertIn(
                "assets/nested/logo.dds",
                [
                    relative.as_posix()
                    for relative, _ in validate_runtime_tree(
                        root / "out/mods/example-test", mod
                    )
                ],
            )
            self.assertEqual(
                (root / "out/mods/example-test/assets/nested/logo.dds").read_bytes(),
                b"DDS payload",
            )
            with mock.patch("sys.stdout", new_callable=io.StringIO):
                package_mod(root, "example-test")
            with zipfile.ZipFile(root / "out/pkg/mods/example-test.zip") as archive:
                for path in source.rglob("*"):
                    if path.is_file():
                        self.assertEqual(
                            archive.read(
                                "mods/example-test/"
                                + path.relative_to(source).as_posix()
                            ),
                            path.read_bytes(),
                        )

    def test_lua_binary_headers_reject_native_signatures(self):
        for name, data in (
            ("assets/image.dat", b"\x7fELFbinary"),
            ("LICENSE", b"\xcf\xfa\xed\xfebinary"),
            ("assets/image.dat", b"MZbinary"),
        ):
            with self.subTest(name=name, data=data):
                with self.assertRaisesRegex(RuntimeError, "native binary"):
                    validate_lua_binary_header(data, name)

    def test_lua_runtime_rejects_binary_in_optional_asset(self):
        with tempfile.TemporaryDirectory() as directory:
            source = self.write_source(Path(directory))
            path = source / "assets/image.dat"
            path.parent.mkdir()
            path.write_bytes(b"\x7fELFbinary")
            mod = load_manifest(source / "mod.toml")
            with self.assertRaisesRegex(RuntimeError, "native binary"):
                validate_runtime_tree(source, mod)

    def test_lua_archive_rejects_missing_entry_native_payload_and_bad_source(self):
        mod = parse_manifest_data(tomllib.loads(LUA_MANIFEST), "fixture")
        for extra, data, entry_data, message in (
            (None, b"", None, "no Lua entry"),
            ("code/windows-x64/example_test.dll", b"plugin", LUA_SOURCE, "code/"),
            ("assets/plugin.dll", b"plugin", LUA_SOURCE, "native binary"),
            ("assets/image.dat", b"MZbinary", LUA_SOURCE, "native binary"),
            (None, b"", b"return {}\r\n", "LF"),
            (None, b"", b"x" * 262144 + b"\n", "256 KiB"),
        ):
            with (
                self.subTest(message=message),
                tempfile.TemporaryDirectory() as directory,
            ):
                archive = Path(directory) / "example-test.zip"
                with zipfile.ZipFile(archive, "w") as package:
                    package.writestr("mods/example-test/mod.toml", LUA_MANIFEST)
                    if entry_data is not None:
                        package.writestr("mods/example-test/main.lua", entry_data)
                    if extra:
                        package.writestr("mods/example-test/" + extra, data)
                with self.assertRaisesRegex(RuntimeError, message):
                    verify_package_archive(archive, "example-test", mod)

    def test_lua_archive_accepts_source_at_size_limit(self):
        mod = parse_manifest_data(tomllib.loads(LUA_MANIFEST), "fixture")
        with tempfile.TemporaryDirectory() as directory:
            archive = Path(directory) / "example-test.zip"
            with zipfile.ZipFile(archive, "w") as package:
                package.writestr("mods/example-test/mod.toml", LUA_MANIFEST)
                package.writestr("mods/example-test/main.lua", b"-" * 262143 + b"\n")
            self.assertEqual(
                verify_package_archive(archive, "example-test", mod), ["lua"]
            )

    def test_lua_archive_payload_must_match_source(self):
        with tempfile.TemporaryDirectory() as directory:
            archive = Path(directory) / "example-test.zip"
            with zipfile.ZipFile(archive, "w") as package:
                package.writestr("mods/example-test/mod.toml", LUA_MANIFEST)
                package.writestr("mods/example-test/main.lua", LUA_SOURCE)
            mod = parse_manifest_data(tomllib.loads(LUA_MANIFEST), "fixture")
            mod["payload"]["requires"] = ["unit_combat"]
            with self.assertRaisesRegex(RuntimeError, "manifest differs"):
                verify_package_archive(archive, "example-test", mod)

    def test_lua_overlay_on_native_runtime_tree_is_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            self.write_source(root)
            assemble_lua_mod(root, "example-test")
            with mock.patch("sys.stdout", new_callable=io.StringIO):
                package_mod(root, "example-test")
            installed = root / "installed"
            package = write_runtime(installed / "mods/example-test", "example-test")
            binary = package / "code/windows-x64/example_test.dll"
            binary.parent.mkdir(parents=True)
            binary.write_bytes(b"plugin")
            with zipfile.ZipFile(root / "out/pkg/mods/example-test.zip") as archive:
                archive.extractall(installed)
            mod = load_manifest(package / "mod.toml")
            with self.assertRaisesRegex(RuntimeError, "code/"):
                validate_runtime_tree(package, mod)
            self.assertEqual(
                (package / "code/windows-x64/example_test.dll").read_bytes(), b"plugin"
            )


class PackagingTests(unittest.TestCase):
    def test_verifier_requires_at_least_one_mod(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / "mods"
            source.mkdir()
            self.assertEqual(discover_mods(source), [])
            with self.assertRaisesRegex(RuntimeError, r"^no mods found under mods/$"):
                verify_manifests(root)

    def test_discovery_reports_source_errors(self):
        cases = (
            ("Bad_ID", "invalid package source directory: Bad_ID", False),
            ("valid-mod", "mod has no manifest: valid-mod", False),
            (
                "valid-mod",
                "first-party packages are Lua",
                True,
            ),
        )
        for package_id, message, write_manifest in cases:
            with self.subTest(package_id=package_id, message=message):
                with tempfile.TemporaryDirectory() as directory:
                    root = Path(directory)
                    source = root / "mods"
                    package = source / package_id
                    package.mkdir(parents=True)
                    if write_manifest:
                        manifest = LUA_MANIFEST.replace(
                            'id = "example-test"', 'id = "valid-mod"'
                        ).replace("manifest_version = 2", "manifest_version = 1")
                        (package / "mod.toml").write_text(manifest, encoding="ascii")
                    with self.assertRaisesRegex(RuntimeError, message):
                        discover_mods(source)

    def test_verifier_propagates_discovery_error(self):
        with mock.patch(
            "verify.discover_mods",
            side_effect=RuntimeError("mod has no manifest: valid-mod"),
        ) as discover:
            with self.assertRaisesRegex(RuntimeError, "mod has no manifest: valid-mod"):
                verify_manifests(Path("fixture"))
        discover.assert_called_once_with(Path("fixture/mods"))

    def test_discovery_preserves_sorted_sources(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / "mods"
            source.mkdir()
            (source / "ordinary.txt").write_text("ignored", encoding="ascii")
            for package_id in ("z-mod", "a-mod"):
                write_runtime(source / package_id, package_id)
            expected = ["a-mod", "z-mod"]
            self.assertEqual(discover_mods(source), expected)

    def test_archive_requires_runtime_root_and_lua_entry(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source_mod = parse_manifest_data(tomllib.loads(LUA_MANIFEST), "fixture")
            archive = root / "example-test.zip"
            with zipfile.ZipFile(archive, "w") as output:
                output.writestr("mods/example-test/mod.toml", LUA_MANIFEST)
                output.writestr(
                    "mods/example-test/main.lua",
                    LUA_SOURCE,
                )
            self.assertEqual(
                verify_package_archive(archive, "example-test", source_mod),
                ["lua"],
            )

            malformed = root / "malformed.zip"
            with zipfile.ZipFile(malformed, "w") as output:
                output.writestr("example-test/mod.toml", LUA_MANIFEST)
                output.writestr("example-test/main.lua", LUA_SOURCE)
            with self.assertRaisesRegex(RuntimeError, "rooted at mods/example-test"):
                verify_package_archive(malformed, "example-test", source_mod)

    def test_archive_rejects_raw_dot_components(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source_mod = parse_manifest_data(tomllib.loads(LUA_MANIFEST), "fixture")
            for component in (".", ".."):
                with self.subTest(component=component):
                    archive = root / f"dot-{component.replace('.', 'dot')}.zip"
                    with zipfile.ZipFile(archive, "w") as output:
                        output.writestr("mods/example-test/mod.toml", LUA_MANIFEST)
                        output.writestr(
                            f"mods/example-test/{component}/main.lua",
                            LUA_SOURCE,
                        )
                    with self.assertRaisesRegex(
                        RuntimeError, "archive entry escapes its root"
                    ):
                        verify_package_archive(archive, "example-test", source_mod)

    def test_archive_rejects_explicit_special_entry_types(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source_mod = parse_manifest_data(tomllib.loads(LUA_MANIFEST), "fixture")
            archive = root / "fifo.zip"
            info = zipfile.ZipInfo("mods/example-test/main.lua")
            info.external_attr = (stat.S_IFIFO | 0o644) << 16
            with zipfile.ZipFile(archive, "w") as output:
                output.writestr("mods/example-test/mod.toml", LUA_MANIFEST)
                output.writestr(info, LUA_SOURCE)
            with self.assertRaisesRegex(RuntimeError, "non-regular package entry"):
                verify_package_archive(archive, "example-test", source_mod)

    def test_package_version_requires_exact_numeric_major_minor(self):
        for version in (
            "1",
            "1.0.0",
            "",
            "1..0",
            "-1.0",
            "+1.0",
            "1.0-alpha",
            "1.0-dev",
            chr(0x0661) + ".0",
        ):
            with self.subTest(version=version):
                with self.assertRaisesRegex(
                    RuntimeError, "version must use numeric major.minor syntax"
                ):
                    value = tomllib.loads(LUA_MANIFEST)
                    value["mod"]["version"] = version
                    parse_manifest_data(value, "fixture")
        with self.assertRaisesRegex(RuntimeError, r"\[mod\].version must be a string"):
            value = tomllib.loads(LUA_MANIFEST)
            value["mod"]["version"] = 1
            parse_manifest_data(value, "fixture")

    def test_minimum_game_version_keeps_strict_three_component_grammar(self):
        for version in (
            "2.3",
            "2.3.4.5",
            "1.0",
            "1.0.0.0",
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
                    value = tomllib.loads(LUA_MANIFEST)
                    value["mod"]["min_game_version"] = version
                    parse_manifest_data(value, "fixture")
        with self.assertRaisesRegex(RuntimeError, "min_game_version must be a string"):
            value = tomllib.loads(LUA_MANIFEST)
            value["mod"]["min_game_version"] = 1
            parse_manifest_data(value, "fixture")

    def test_archive_rejects_duplicate_missing_and_malformed_manifests(self):
        manifest_name = "mods/example-test/mod.toml"
        entry = ("mods/example-test/main.lua", LUA_SOURCE)
        cases = (
            (
                "duplicate",
                [(manifest_name, LUA_MANIFEST), entry, entry],
                "duplicate package entry",
            ),
            ("missing", [entry], "package has no manifest"),
            ("toml", [(manifest_name, b"[")], "invalid package manifest"),
            ("ascii", [(manifest_name, b"\xff")], "invalid package manifest"),
        )
        mod = parse_manifest_data(tomllib.loads(LUA_MANIFEST), "fixture")
        with tempfile.TemporaryDirectory() as directory:
            archive = Path(directory) / "example-test.zip"
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
                        verify_package_archive(archive, "example-test", mod)

    def test_zip_entry_paths_validate_raw_names(self):
        for name, message in (
            ("", "malformed archive entry"),
            ("mods/example-test/", "malformed archive entry"),
            ("mods\\example-test\\main.lua", "malformed archive entry"),
            ("mods//example-test/main.lua", "malformed archive entry"),
            ("/mods/example-test/main.lua", "escapes its root"),
            ("mods/example-test/./main.lua", "escapes its root"),
            ("mods/example-test/../main.lua", "escapes its root"),
        ):
            with self.subTest(name=name):
                with self.assertRaisesRegex(RuntimeError, message):
                    _zip_entry_path(Path("fixture.zip"), name)

    def test_verifier_requires_mod_archive(self):
        with tempfile.TemporaryDirectory() as directory:
            with self.assertRaisesRegex(RuntimeError, "missing package"):
                verify_packages(Path(directory), ["example-test"])

    def test_build_cli_selection_listing_and_errors(self):
        cases = (
            ("default", [], ["a-mod", "z-mod"], ["a-mod", "z-mod"], None),
            ("selected", ["--mod", "z-mod"], ["a-mod", "z-mod"], ["z-mod"], None),
            ("list", ["--list"], ["a-mod", "z-mod"], [], "a-mod\nz-mod\n"),
            ("unknown", ["--mod", "missing"], ["a-mod", "z-mod"], [], None),
            ("empty", [], [], [], "No mods found under mods/.\n"),
        )
        for label, arguments, available, selected, output in cases:
            with (
                self.subTest(case=label),
                mock.patch.object(sys, "argv", ["build_mods.py", *arguments]),
                mock.patch("build_mods.discover_mods", return_value=available),
                mock.patch("build_mods.assemble_lua_mod") as assemble,
                mock.patch("build_mods.package_mod") as package,
                contextlib.redirect_stdout(io.StringIO()) as stdout,
            ):
                if label == "unknown":
                    with self.assertRaisesRegex(
                        RuntimeError, r"unknown mod\(s\): missing"
                    ):
                        build_main()
                else:
                    build_main()
                root = Path(__file__).resolve().parents[1]
                expected_calls = [mock.call(root, name) for name in selected]
                self.assertEqual(assemble.call_args_list, expected_calls)
                self.assertEqual(package.call_args_list, expected_calls)
                if output is not None:
                    self.assertEqual(stdout.getvalue(), output)

    def test_title_checkout_must_match_locked_commit(self):
        title_dir = Path("title")
        lock = {"commit": "a" * 40}
        with mock.patch("verify.run", return_value=lock["commit"] + "\n") as run:
            verify_title_checkout(title_dir, lock)
        run.assert_called_once_with(
            ["git", "rev-parse", "HEAD"], title_dir, capture=True
        )
        with mock.patch("verify.run", return_value="b" * 40 + "\n"):
            with self.assertRaisesRegex(RuntimeError, "title checkout mismatch"):
                verify_title_checkout(title_dir, lock)

    def test_lock_rejects_repository_and_commit_syntax(self):
        repository = "https://github.com/ReRevvedRecomp/rerevved"
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "fixture.lock.json"
            for field, invalid, message in (
                ("repository", "https://example.com/other", "unexpected repository"),
                ("commit", "", "invalid commit"),
                ("commit", "a" * 39, "invalid commit"),
                ("commit", "a" * 41, "invalid commit"),
                ("commit", "A" * 40, "invalid commit"),
                ("commit", "g" * 40, "invalid commit"),
            ):
                with self.subTest(field=field, invalid=invalid):
                    value = {"repository": repository, "commit": "a" * 40}
                    value[field] = invalid
                    path.write_text(json.dumps(value), encoding="ascii")
                    with self.assertRaisesRegex(RuntimeError, message):
                        load_lock(path, repository)

    def test_lock_versions_and_abi_mismatches(self):
        sdk = {
            "repository": "https://github.com/ReRevvedRecomp/rerevved-sdk",
            "commit": "a" * 40,
            "version": "0.5.0.gaaaaaaa",
        }
        title = {
            "repository": "https://github.com/ReRevvedRecomp/rerevved",
            "commit": "b" * 40,
            "gameplay_abi": 2,
            "unit_catalog_abi": 2,
            "unique_unit_rules_abi": 2,
            "unique_era_abilities_abi": 3,
            "terrain_yield_rules_abi": 2,
            "unit_movement_rules_abi": 2,
            "unit_production_cost_rules_abi": 2,
            "unit_effect_rules_abi": 3,
            "unit_combat_rules_abi": 2,
            "nation_select_text_abi": 2,
            "building_effect_rules_abi": 1,
            "wonder_effect_rules_abi": 1,
        }
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            sdk_path = root / "rexglue-sdk.lock.json"
            title_path = root / "rerevved-api.lock.json"
            title_path.write_text(json.dumps(title), encoding="ascii")
            for version in ("0.5.0.gaaaaaaa", "0.5.0", "0.5.0.1"):
                with self.subTest(version=version):
                    sdk["version"] = version
                    sdk_path.write_text(json.dumps(sdk), encoding="ascii")
                    self.assertEqual(verify_locks(root), (sdk, title))
            for version in ("", "0.5", "0.5.0.1.2", "0.5.0.gbbbbbbb"):
                with self.subTest(version=version):
                    sdk["version"] = version
                    sdk_path.write_text(json.dumps(sdk), encoding="ascii")
                    with self.assertRaisesRegex(
                        RuntimeError, "SDK version does not match"
                    ):
                        verify_locks(root)
            sdk["version"] = "0.5.0.gaaaaaaa"
            sdk_path.write_text(json.dumps(sdk), encoding="ascii")
            for field, message in (
                ("gameplay_abi", "gameplay ABI 2"),
                ("unit_catalog_abi", "Unit Catalog ABI 2"),
                ("unique_unit_rules_abi", "Unique Unit Rules ABI 2"),
                ("unique_era_abilities_abi", "Unique Era Abilities ABI 3"),
                ("terrain_yield_rules_abi", "Terrain Yield Rules ABI 2"),
                ("unit_movement_rules_abi", "Unit Movement Rules ABI 2"),
                ("unit_production_cost_rules_abi", "Unit Production Cost Rules ABI 2"),
                ("unit_effect_rules_abi", "Unit Effect Rules ABI 3"),
                ("unit_combat_rules_abi", "Unit Combat Rules ABI 2"),
                ("nation_select_text_abi", "Nation Select Text ABI 2"),
                ("building_effect_rules_abi", "Building Effect Rules ABI 1"),
                ("wonder_effect_rules_abi", "Wonder Effect Rules ABI 1"),
            ):
                with self.subTest(field=field):
                    invalid = {**title, field: 0}
                    title_path.write_text(json.dumps(invalid), encoding="ascii")
                    with self.assertRaisesRegex(RuntimeError, message):
                        verify_locks(root)

    def test_public_tree_rejects_forbidden_files_and_text(self):
        cases = (
            ("retail.xex", b"retail", RuntimeError, "forbidden tracked retail file"),
            ("plugin.DLL", b"plugin", RuntimeError, "forbidden tracked retail file"),
            ("package.zip", b"package", RuntimeError, "forbidden tracked retail file"),
            ("note.md", b"agent-" + b"islands", RuntimeError, "private path marker"),
            (
                "note.md",
                b"docs/ai_agents/" + b"local",
                RuntimeError,
                "private path marker",
            ),
            ("note.md", b"Documents/" + b"Repos", RuntimeError, "private path marker"),
            ("note.md", b"Documents" + b"\\Repos", RuntimeError, "private path marker"),
            ("note.md", b"\xff", UnicodeDecodeError, "ascii"),
        )
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            for name, data, error, message in cases:
                with self.subTest(name=name, data=data):
                    path = root / name
                    path.write_bytes(data)
                    with self.assertRaisesRegex(error, message):
                        verify_public_tree(root, [path])

    def test_generated_cleanup_stays_bounded_and_refuses_reparse_points(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            generated = root / "out" / "mods"
            package = generated / "example-test"
            linked = package / "linked"
            linked.mkdir(parents=True)
            marker = linked / "keep.txt"
            marker.write_text("keep", encoding="ascii")

            with self.assertRaisesRegex(RuntimeError, "outside"):
                _remove_generated_directory(
                    root / "outside" / "example-test", generated
                )
            with self.assertRaisesRegex(RuntimeError, "outside"):
                _remove_generated_directory(
                    root / "x" / "example-test", root / "x", base=root / "out"
                )

            for reparse in (root / "out", generated, package, linked):
                with (
                    self.subTest(reparse=reparse),
                    mock.patch(
                        "build_mods._is_reparse_point",
                        side_effect=lambda path: path == reparse,
                    ),
                ):
                    with self.assertRaisesRegex(RuntimeError, "reparse point"):
                        _remove_generated_directory(package, generated, base=root)
                    self.assertTrue(marker.is_file())
                    self.assertEqual(marker.read_text(encoding="ascii"), "keep")

    def test_generated_cleanup_replaces_only_selected_output(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            generated = root / "out" / "mods"
            package = generated / "example-test"
            stale = package / "nested/stale.txt"
            stale.parent.mkdir(parents=True)
            stale.write_bytes(b"stale")
            sibling = generated / "other-mod/keep.txt"
            sibling.parent.mkdir()
            sibling.write_bytes(b"keep")
            _remove_generated_directory(package, generated)
            self.assertTrue(package.is_dir())
            self.assertEqual(list(package.iterdir()), [])
            self.assertEqual(sibling.read_bytes(), b"keep")


if __name__ == "__main__":
    unittest.main()
