#!/usr/bin/env python3
"""Verify ReRevved Mods locks, public hygiene, formatting, and native build."""

import argparse
import json
import re
import shutil
import subprocess
import sys
import tomllib
import zipfile
from pathlib import Path


TEXT_SUFFIXES = {".cmake", ".cpp", ".h", ".json", ".md", ".py", ".toml", ".yaml", ".yml"}
FORBIDDEN_RETAIL_SUFFIXES = {".bin", ".iso", ".xex", ".xexp"}
FORBIDDEN_TRACKED_SUFFIXES = FORBIDDEN_RETAIL_SUFFIXES | {
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
REQUIRED_MANIFEST_KEYS = {"name", "version", "author", "description"}
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
    return [root / item for item in output.split("\0") if item]


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
        "https://github.com/ReRevvedRecomp/rerevved-rexglue-sdk",
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
        manifest_path = directory / "mod.toml"
        if not manifest_path.is_file():
            raise RuntimeError(f"mod has no manifest: {directory.name}")
        manifest = tomllib.loads(manifest_path.read_text(encoding="ascii"))
        missing = REQUIRED_MANIFEST_KEYS - manifest.keys()
        if missing:
            raise RuntimeError(f"{directory.name} manifest is missing: {', '.join(sorted(missing))}")
        if (directory / "CMakeLists.txt").is_file() and manifest.get("code") != directory.name:
            raise RuntimeError(f"{directory.name} code key must match its directory")
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
            f"clang-format {CLANG_FORMAT_MAJOR}.x is required; "
            f"found {reported_version} at {formatter}"
        )
    mirrored_api = root / "src" / "common" / "api"
    sources = sorted(
        path for path in (root / "src").rglob("*")
        if path.is_file()
        and path.suffix.lower() in {".cpp", ".h"}
        and not path.is_relative_to(mirrored_api)
    )
    run([formatter, "--dry-run", "--Werror", *sources], root)


def verify_packages(root, mods):
    for name in mods:
        archive = root / "pkg" / f"{name}.zip"
        if not archive.is_file():
            raise RuntimeError(f"missing package: {archive}")
        with zipfile.ZipFile(archive) as package:
            for entry in package.namelist():
                path = Path(entry)
                if not path.parts or path.parts[0] != name:
                    raise RuntimeError(f"package entry escapes {name}/: {entry}")
                if path.suffix.lower() in FORBIDDEN_RETAIL_SUFFIXES:
                    raise RuntimeError(f"retail file in package: {entry}")


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
        verify_packages(root, mods)

    print(f"Verified {len(mods)} mod(s) against SDK {sdk_lock['version']}.")


if __name__ == "__main__":
    try:
        main()
    except (OSError, RuntimeError, subprocess.CalledProcessError, UnicodeError) as error:
        print(f"error: {error}", file=sys.stderr)
        sys.exit(1)
