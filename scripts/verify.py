#!/usr/bin/env python3
"""Verify ReRevved Mods locks, public hygiene, formatting, and native build."""

import argparse
import json
import re
import shutil
import stat
import subprocess
import sys
import tomllib
import zipfile
from pathlib import Path, PurePosixPath

from build_mods import (
    PACKAGE_ID_RE,
    _validate_runtime_relative,
    load_manifest,
    parse_manifest_data,
)


TEXT_SUFFIXES = {".cmake", ".cpp", ".h", ".json", ".md", ".py", ".toml", ".yaml", ".yml"}
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
CLANG_FORMAT_MAJOR = 22


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
    return [root / item for item in output.split("\0") if item and (root / item).is_file()]


def load_lock(path, repository):
    value = json.loads(path.read_text(encoding="ascii"))
    if value.get("repository") != repository:
        raise RuntimeError(f"unexpected repository in {path.name}: {value.get('repository')}")
    commit = value.get("commit", "")
    if not re.fullmatch(r"[0-9a-f]{40}", commit):
        raise RuntimeError(f"invalid commit in {path.name}: {commit}")
    return value


def verify_locks(root):
    sdk = load_lock(
        root / "rexglue-sdk.lock.json",
        "https://github.com/ReRevvedRecomp/rerevved-sdk",
    )
    title = load_lock(root / "rerevved-api.lock.json", "https://github.com/ReRevvedRecomp/rerevved")
    expected_suffix = f".g{sdk['commit'][:7]}"
    if not sdk.get("version", "").endswith(expected_suffix):
        raise RuntimeError(f"SDK version does not match its commit: {sdk.get('version')}")
    if title.get("gameplay_abi") != 1:
        raise RuntimeError("rerevved-api.lock.json must pin gameplay ABI 1")
    if title.get("unit_catalog_abi") != 1:
        raise RuntimeError("rerevved-api.lock.json must pin Unit Catalog ABI 1")
    if title.get("unique_unit_rules_abi") != 1:
        raise RuntimeError("rerevved-api.lock.json must pin Unique Unit Rules ABI 1")
    if title.get("unique_era_abilities_abi") != 2:
        raise RuntimeError("rerevved-api.lock.json must pin Unique Era Abilities ABI 2")
    return sdk, title


def verify_public_tree(root, files):
    for path in files:
        relative = path.relative_to(root).as_posix()
        if path.suffix.lower() in FORBIDDEN_TRACKED_SUFFIXES:
            raise RuntimeError(f"forbidden tracked retail file: {relative}")
        if path.suffix.lower() not in TEXT_SUFFIXES and path.name != "CMakeLists.txt":
            continue
        text = path.read_text(encoding="ascii")
        for marker in FORBIDDEN_TEXT:
            if marker in text:
                raise RuntimeError(f"private path marker in {relative}: {marker}")


def verify_manifests(root):
    mods = []
    for directory in sorted((root / "src").iterdir()):
        if not directory.is_dir() or directory.name == "common":
            continue
        if not PACKAGE_ID_RE.fullmatch(directory.name) or len(directory.name) > 63:
            raise RuntimeError(f"invalid package source directory: {directory.name}")
        manifest_path = directory / "mod.toml"
        if not manifest_path.is_file():
            raise RuntimeError(f"mod has no manifest: {directory.name}")
        load_manifest(manifest_path, directory.name)
        if not (directory / "CMakeLists.txt").is_file():
            raise RuntimeError(
                f"{directory.name}: native packages require a CMakeLists.txt payload"
            )
        mods.append(directory.name)
    if not mods:
        raise RuntimeError("no mods found under src/")
    return mods


def verify_title_mirror(root, title_dir, title_lock):
    actual = run(["git", "rev-parse", "HEAD"], title_dir, capture=True).strip()
    if actual != title_lock["commit"]:
        raise RuntimeError(f"title checkout mismatch: expected {title_lock['commit']}, found {actual}")
    for name in (
        "game_ids.h",
        "gameplay_state.h",
        "unique_era_abilities.h",
        "unique_unit_rules.h",
        "unit_catalog.h",
    ):
        source = title_dir / "api" / name
        mirror = root / "src" / "common" / "api" / name
        if source.read_bytes() != mirror.read_bytes():
            raise RuntimeError(f"src/common/api/{name} differs from the pinned title header")


def verify_format(root):
    formatter = shutil.which("clang-format")
    if not formatter:
        raise RuntimeError(f"clang-format {CLANG_FORMAT_MAJOR}.x was not found in PATH")
    version_result = subprocess.run(
        [formatter, "--version"],
        cwd=root,
        check=False,
        text=True,
        capture_output=True,
    )
    version_output = " ".join(
        part.strip() for part in (version_result.stdout, version_result.stderr) if part.strip()
    )
    version_match = re.search(
        r"\bclang-format version (?P<version>\d+\.\d+\.\d+)(?=\s|$|\()",
        version_output,
        re.IGNORECASE,
    )
    if version_result.returncode != 0:
        raise RuntimeError(
            f"clang-format {CLANG_FORMAT_MAJOR}.x version query failed at {formatter}: "
            f"{version_output}"
        )
    if not version_match or int(version_match.group("version").split(".", 1)[0]) != CLANG_FORMAT_MAJOR:
        reported_version = version_match.group("version") if version_match else "unknown"
        raise RuntimeError(
            f"clang-format {CLANG_FORMAT_MAJOR}.x is required; found {reported_version} at {formatter}"
        )
    mirrored_api = root / "src" / "common" / "api"
    sources = sorted(
        path
        for path in (root / "src").rglob("*")
        if path.is_file()
        and path.suffix.lower() in {".cpp", ".h"}
        and not path.is_relative_to(mirrored_api)
    )
    run([formatter, "--dry-run", "--Werror", *sources], root)


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
    path = PurePosixPath(name)
    if path.is_absolute() or ".." in path.parts:
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
            if info.is_dir() or stat.S_ISLNK(info.external_attr >> 16):
                raise RuntimeError(f"non-regular package entry: {info.filename}")
            path = _zip_entry_path(archive, info.filename)
            if path.parts[:2] != ("mods", package_id):
                raise RuntimeError(f"package entry is not rooted at mods/{package_id}/: {info.filename}")
        if manifest_entry.as_posix() not in seen:
            raise RuntimeError(f"package has no manifest: {archive.name}")
        try:
            manifest = tomllib.loads(package.read(manifest_entry.as_posix()).decode("ascii"))
        except (UnicodeError, tomllib.TOMLDecodeError) as error:
            raise RuntimeError(f"invalid package manifest in {archive.name}: {error}") from error
        mod = parse_manifest_data(manifest, f"{archive.name}:{manifest_entry}", package_id)
        if mod != source_mod:
            raise RuntimeError(f"package manifest differs from source manifest: {archive.name}")

        platforms = set()
        root = PurePosixPath("mods") / package_id
        for info in entries:
            path = _zip_entry_path(archive, info.filename)
            relative = PurePosixPath(*path.parts[len(root.parts):])
            platform_name = _validate_runtime_relative(relative, mod["code"])
            if platform_name:
                platforms.add(platform_name)
        if not platforms:
            raise RuntimeError(f"package has no qualified native binary: {archive.name}")
        return sorted(platforms)


def verify_packages(root, mods):
    inventory = {}
    for name in mods:
        archive = root / "pkg" / f"{name}.zip"
        if not archive.is_file():
            raise RuntimeError(f"missing package: {archive}")
        source_mod = load_manifest(root / "src" / name / "mod.toml", name)
        inventory[name] = verify_package_archive(archive, name, source_mod)
    return inventory


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--title-dir", type=Path)
    parser.add_argument("--sdk-dir", type=Path)
    args = parser.parse_args()

    root = Path(__file__).resolve().parent.parent
    files = tracked_files(root)
    sdk_lock, title_lock = verify_locks(root)
    verify_public_tree(root, files)
    mods = verify_manifests(root)
    run(["git", "diff", "--check"], root)
    verify_format(root)
    verify_focused_tests(root)

    if args.title_dir:
        verify_title_mirror(root, args.title_dir.resolve(), title_lock)
    if args.sdk_dir:
        run(
            [
                sys.executable,
                str(root / "scripts" / "build_mods.py"),
                "--sdk-dir",
                str(args.sdk_dir.resolve()),
                "--package",
            ],
            root,
        )
        inventory = verify_packages(root, mods)
        print(
            "Package inventory: "
            + ", ".join(f"{name} ({'/'.join(platforms)})" for name, platforms in inventory.items())
        )

    print(f"Verified {len(mods)} mod(s) against SDK {sdk_lock['version']}.")


if __name__ == "__main__":
    try:
        main()
    except (OSError, RuntimeError, subprocess.CalledProcessError, UnicodeError) as error:
        print(f"error: {error}", file=sys.stderr)
        sys.exit(1)
