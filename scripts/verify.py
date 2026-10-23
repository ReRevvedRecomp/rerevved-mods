#!/usr/bin/env python3
"""Check locks, public-file safety and formatting, then build and verify mod packages."""

import argparse
import json
import re
import stat
import subprocess
import sys
import tomllib
import zipfile
from pathlib import Path, PurePosixPath

from build_mods import (
    LUA_SOURCE_LIMIT,
    _validate_lua_relative,
    discover_mods,
    load_manifest,
    parse_manifest_data,
    validate_lua_binary_header,
    validate_lua_source,
)
from format_lua import main as format_lua_main
from verify_asset_packs import verify_asset_packs

TEXT_SUFFIXES = {
    ".json",
    ".lua",
    ".md",
    ".py",
    ".toml",
    ".yaml",
    ".yml",
}
FORBIDDEN_TRACKED_SUFFIXES = {
    ".bin",
    ".iso",
    ".xex",
    ".xexp",
    ".dll",
    ".dylib",
    ".exe",
    ".pdb",
    ".so",
    ".zip",
}
FORBIDDEN_TEXT = (
    "agent-" + "islands",
    "docs/ai_agents/" + "local",
    "Documents/" + "Repos",
    "Documents" + "\\Repos",
)


def run(command, cwd, capture=False):
    result = subprocess.run(
        command,
        cwd=cwd,
        check=True,
        text=True,
        capture_output=capture,
    )
    return result.stdout if capture else ""


def tracked_files(root):
    output = run(
        ["git", "ls-files", "--cached", "--others", "--exclude-standard", "-z"],
        root,
        capture=True,
    )
    return [
        root / item for item in output.split("\0") if item and (root / item).is_file()
    ]


def load_lock(path, repository):
    value = json.loads(path.read_text(encoding="ascii"))
    if value.get("repository") != repository:
        raise RuntimeError(
            f"unexpected repository in {path.name}: {value.get('repository')}"
        )
    commit = value.get("commit", "")
    if not re.fullmatch(r"[0-9a-f]{40}", commit):
        raise RuntimeError(f"invalid commit in {path.name}: {commit}")
    return value


def verify_locks(root):
    sdk = load_lock(
        root / "rexglue-sdk.lock.json",
        "https://github.com/ReRevvedRecomp/rerevved-sdk",
    )
    title = load_lock(
        root / "rerevved-api.lock.json", "https://github.com/ReRevvedRecomp/rerevved"
    )
    expected_suffix = f".g{sdk['commit'][:7]}"
    version = sdk.get("version", "")
    # Untagged builds carry the commit suffix; a tagged release is a plain version.
    if not (
        version.endswith(expected_suffix)
        or re.fullmatch(r"\d+\.\d+\.\d+(\.\d+)?", version)
    ):
        raise RuntimeError(
            f"SDK version does not match its commit: {sdk.get('version')}"
        )
    if title.get("gameplay_abi") != 2:
        raise RuntimeError("rerevved-api.lock.json must pin gameplay ABI 2")
    if title.get("unit_catalog_abi") != 2:
        raise RuntimeError("rerevved-api.lock.json must pin Unit Catalog ABI 2")
    if title.get("unique_unit_rules_abi") != 2:
        raise RuntimeError("rerevved-api.lock.json must pin Unique Unit Rules ABI 2")
    if title.get("unique_era_abilities_abi") != 3:
        raise RuntimeError("rerevved-api.lock.json must pin Unique Era Abilities ABI 3")
    if title.get("terrain_yield_rules_abi") != 2:
        raise RuntimeError("rerevved-api.lock.json must pin Terrain Yield Rules ABI 2")
    if title.get("unit_movement_rules_abi") != 2:
        raise RuntimeError("rerevved-api.lock.json must pin Unit Movement Rules ABI 2")
    if title.get("unit_production_cost_rules_abi") != 2:
        raise RuntimeError(
            "rerevved-api.lock.json must pin Unit Production Cost Rules ABI 2"
        )
    if title.get("unit_effect_rules_abi") != 3:
        raise RuntimeError("rerevved-api.lock.json must pin Unit Effect Rules ABI 3")
    if title.get("unit_combat_rules_abi") != 2:
        raise RuntimeError("rerevved-api.lock.json must pin Unit Combat Rules ABI 2")
    if title.get("nation_select_text_abi") != 2:
        raise RuntimeError("rerevved-api.lock.json must pin Nation Select Text ABI 2")
    if title.get("building_effect_rules_abi") != 1:
        raise RuntimeError(
            "rerevved-api.lock.json must pin Building Effect Rules ABI 1"
        )
    if title.get("wonder_effect_rules_abi") != 1:
        raise RuntimeError("rerevved-api.lock.json must pin Wonder Effect Rules ABI 1")
    return sdk, title


def verify_public_tree(root, files):
    for path in files:
        relative = path.relative_to(root).as_posix()
        if path.suffix.lower() in FORBIDDEN_TRACKED_SUFFIXES:
            raise RuntimeError(f"forbidden tracked retail file: {relative}")
        if path.suffix.lower() not in TEXT_SUFFIXES:
            continue
        text = path.read_text(encoding="ascii")
        for marker in FORBIDDEN_TEXT:
            if marker in text:
                raise RuntimeError(f"private path marker in {relative}: {marker}")


def verify_manifests(root):
    mods = discover_mods(root / "src")
    if not mods:
        raise RuntimeError("no mods found under src/")
    return mods


def verify_title_checkout(title_dir, title_lock):
    actual = run(["git", "rev-parse", "HEAD"], title_dir, capture=True).strip()
    if actual != title_lock["commit"]:
        raise RuntimeError(
            f"title checkout mismatch: expected {title_lock['commit']}, found {actual}"
        )


def verify_python(root):
    run([sys.executable, "-m", "ruff", "check", "scripts", "tests"], root)
    run(
        [sys.executable, "-m", "ruff", "format", "--check", "scripts", "tests"],
        root,
    )


def verify_focused_tests(root):
    run(
        [
            sys.executable,
            "-m",
            "unittest",
            "discover",
            "-s",
            "tests",
            "-p",
            "test_*.py",
        ],
        root,
    )


def _zip_entry_path(archive, name):
    if not name or name.endswith("/") or "\\" in name or "//" in name:
        raise RuntimeError(f"malformed archive entry in {archive.name}: {name}")
    if any(part in {".", ".."} for part in name.split("/")):
        raise RuntimeError(f"archive entry escapes its root in {archive.name}: {name}")
    path = PurePosixPath(name)
    if path.is_absolute():
        raise RuntimeError(f"archive entry escapes its root in {archive.name}: {name}")
    return path


def verify_package_archive(archive, package_id, source_mod):
    with zipfile.ZipFile(archive) as package:
        entries = package.infolist()
        seen = set()
        manifest_entry = PurePosixPath("mods") / package_id / "mod.toml"
        for info in entries:
            if info.filename in seen:
                raise RuntimeError(f"duplicate package entry: {info.filename}")
            seen.add(info.filename)
            mode = info.external_attr >> 16
            if info.is_dir() or stat.S_IFMT(mode) not in (0, stat.S_IFREG):
                raise RuntimeError(f"non-regular package entry: {info.filename}")
            path = _zip_entry_path(archive, info.filename)
            if path.parts[:2] != ("mods", package_id):
                raise RuntimeError(
                    f"package entry is not rooted at mods/{package_id}/: {info.filename}"
                )
        if manifest_entry.as_posix() not in seen:
            raise RuntimeError(f"package has no manifest: {archive.name}")
        try:
            manifest = tomllib.loads(
                package.read(manifest_entry.as_posix()).decode("ascii")
            )
        except (UnicodeError, tomllib.TOMLDecodeError) as error:
            raise RuntimeError(
                f"invalid package manifest in {archive.name}: {error}"
            ) from error
        mod = parse_manifest_data(
            manifest, f"{archive.name}:{manifest_entry}", package_id
        )
        if mod != source_mod:
            raise RuntimeError(
                f"package manifest differs from source manifest: {archive.name}"
            )

        root = PurePosixPath("mods") / package_id
        for info in entries:
            path = _zip_entry_path(archive, info.filename)
            relative = PurePosixPath(*path.parts[len(root.parts) :])
            _validate_lua_relative(relative, mod["payload"]["entry"])
            with package.open(info) as runtime_file:
                validate_lua_binary_header(runtime_file.read(8), info.filename)
        entry = (root / mod["payload"]["entry"]).as_posix()
        if entry not in seen:
            raise RuntimeError(f"package has no Lua entry: {entry}")
        with package.open(entry) as script:
            validate_lua_source(script.read(LUA_SOURCE_LIMIT + 1), entry)
        return ["lua"]


def verify_packages(root, mods):
    inventory = {}
    for name in mods:
        archive = root / "pkg" / "mods" / f"{name}.zip"
        if not archive.is_file():
            raise RuntimeError(f"missing package: {archive}")
        source_mod = load_manifest(root / "src" / name / "mod.toml", name)
        inventory[name] = verify_package_archive(archive, name, source_mod)
    return inventory


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--title-dir", type=Path)
    parser.add_argument(
        "--skip-lua-format",
        action="store_true",
        help="skip CodeFormat on hosts without a pinned asset; retain Lua source checks",
    )
    args = parser.parse_args()

    root = Path(__file__).resolve().parent.parent
    files = tracked_files(root)
    sdk_lock, title_lock = verify_locks(root)
    verify_public_tree(root, files)
    mods = verify_manifests(root)
    asset_packs = verify_asset_packs(root)
    if args.skip_lua_format:
        print("Lua formatter check explicitly skipped; Lua source checks retained.")
    elif format_lua_main(["check"]):
        raise RuntimeError("Lua formatter check failed; see the diagnostic above")
    run(["git", "diff", "--check"], root)
    verify_python(root)
    verify_focused_tests(root)

    if args.title_dir:
        verify_title_checkout(args.title_dir.resolve(), title_lock)
    run([sys.executable, str(root / "scripts" / "build_mods.py")], root)
    inventory = verify_packages(root, mods)
    run(
        [
            sys.executable,
            str(root / "scripts" / "build_asset_packs.py"),
            "--package",
        ],
        root,
    )
    verify_asset_packs(root, check_packages=True)
    print(
        "Package inventory: "
        + ", ".join(f"{name} ({'/'.join(kinds)})" for name, kinds in inventory.items())
    )

    print(
        f"Verified {len(mods)} mod(s) and {len(asset_packs)} asset pack(s) "
        f"with recorded SDK {sdk_lock['version']}."
    )


if __name__ == "__main__":
    try:
        main()
    except (
        OSError,
        RuntimeError,
        subprocess.CalledProcessError,
        UnicodeError,
    ) as error:
        print(f"error: {error}", file=sys.stderr)
        sys.exit(1)
