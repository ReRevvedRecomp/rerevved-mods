#!/usr/bin/env python3
"""Assemble and package title-owned asset override packs."""

import argparse
import os
import re
import shutil
import stat
import sys
import tomllib
import zipfile
from pathlib import Path, PurePosixPath


PACKAGE_ID_RE = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
PACKAGE_VERSION_RE = re.compile(r"^[0-9]+\.[0-9]+$")
MANIFEST_TOP_LEVEL_KEYS = {"manifest_version", "asset_pack"}
MANIFEST_KEYS = {
    "id",
    "name",
    "version",
    "author",
    "description",
}
OPTIONAL_PACKAGE_FILES = {"icon.png", "README.md"}
ASSET_DIRECTORY = "assets"
RUNTIME_ROOT = "asset-overrides"


def _warn_unknown(path, scope, keys, allowed):
    for key in sorted(set(keys) - allowed):
        print(f"warning: {path}: unknown {scope} field {key!r}", file=sys.stderr)


def _require_string(value, field, path, *, nonempty=False):
    if not isinstance(value, str) or (nonempty and not value.strip()):
        state = "nonempty " if nonempty else ""
        raise RuntimeError(f"{path}: {field} must be a {state}string")
    return value


def _validate_version(value, field, path, version_re, syntax):
    _require_string(value, field, path)
    if not version_re.fullmatch(value):
        raise RuntimeError(f"{path}: {field} must use {syntax} syntax")


def parse_asset_pack_data(value, source, expected_id=None):
    """Validate and return an asset pack's [asset_pack] table."""
    if not isinstance(value, dict):
        raise RuntimeError(f"{source}: asset-pack manifest must be a TOML table")
    _warn_unknown(source, "top-level", value.keys(), MANIFEST_TOP_LEVEL_KEYS)
    if type(value.get("manifest_version")) is not int or value["manifest_version"] != 1:
        raise RuntimeError(f"{source}: manifest_version must be integer 1")
    pack = value.get("asset_pack")
    if not isinstance(pack, dict):
        raise RuntimeError(f"{source}: [asset_pack] table is required")
    _warn_unknown(source, "[asset_pack]", pack.keys(), MANIFEST_KEYS)
    required = {"id", "name", "version"}
    missing = sorted(required - pack.keys())
    if missing:
        raise RuntimeError(f"{source}: missing [asset_pack] field(s): {', '.join(missing)}")

    package_id = _require_string(pack["id"], "[asset_pack].id", source, nonempty=True)
    if not PACKAGE_ID_RE.fullmatch(package_id) or len(package_id) > 63:
        raise RuntimeError(f"{source}: [asset_pack].id is not a valid package ID")
    if expected_id is not None and package_id != expected_id:
        raise RuntimeError(
            f"{source}: [asset_pack].id {package_id!r} does not match {expected_id!r}"
        )
    _require_string(pack["name"], "[asset_pack].name", source, nonempty=True)
    _validate_version(
        pack["version"],
        "[asset_pack].version",
        source,
        PACKAGE_VERSION_RE,
        "numeric major.minor",
    )
    for field in ("author", "description"):
        if field in pack:
            _require_string(pack[field], f"[asset_pack].{field}", source)
    return pack


def load_asset_pack_manifest(path, expected_id=None):
    try:
        value = tomllib.loads(path.read_text(encoding="ascii"))
    except (OSError, UnicodeError, tomllib.TOMLDecodeError) as error:
        raise RuntimeError(f"{path}: invalid TOML: {error}") from error
    return parse_asset_pack_data(value, path, expected_id)


def _is_reparse_point(path):
    if path.is_symlink():
        return True
    is_junction = getattr(path, "is_junction", None)
    if is_junction is not None and is_junction():
        return True
    try:
        attributes = path.stat(follow_symlinks=False).st_file_attributes
    except (FileNotFoundError, AttributeError):
        return False
    return bool(attributes & 0x400)


def _validate_asset_relative(path):
    if (
        path.is_absolute()
        or "\\" in path.as_posix()
        or not path.parts
        or ".." in path.parts
    ):
        raise RuntimeError(f"invalid asset path: {path}")


def _asset_files(source_dir, owner, *, required):
    if not source_dir.exists():
        if required:
            raise RuntimeError(f"{owner}: asset pack requires a nonempty assets/ tree")
        return []
    if not source_dir.is_dir() or _is_reparse_point(source_dir):
        raise RuntimeError(f"{owner}: assets must be a regular directory")
    files = []
    for source in sorted(source_dir.rglob("*")):
        if _is_reparse_point(source):
            raise RuntimeError(f"reparse point in assets: {source}")
        relative = PurePosixPath(source.relative_to(source_dir).as_posix())
        _validate_asset_relative(relative)
        if source.is_dir():
            continue
        if not source.is_file():
            raise RuntimeError(f"asset must be a regular file: {source}")
        files.append((relative, source))
    if required and not files:
        raise RuntimeError(f"{owner}: asset pack requires a nonempty assets/ tree")
    return files


def discover_asset_packs(source_root):
    """Return asset pack IDs discovered under the source root."""
    packs = []
    for entry in sorted(source_root.iterdir()):
        if not entry.is_dir():
            continue
        if _is_reparse_point(entry):
            raise RuntimeError(f"asset pack source directory is a reparse point: {entry.name}")
        if not PACKAGE_ID_RE.fullmatch(entry.name) or len(entry.name) > 63:
            raise RuntimeError(f"invalid asset pack source directory: {entry.name}")
        manifest = entry / "asset-pack.toml"
        if not manifest.is_file() or _is_reparse_point(manifest):
            raise RuntimeError(f"asset pack has no manifest: {entry.name}")
        load_asset_pack_manifest(manifest, entry.name)
        _asset_files(entry / ASSET_DIRECTORY, entry.name, required=True)
        packs.append(entry.name)
    return packs


def _remove_generated_directory(path, generated_root):
    generated_root = Path(generated_root)
    if _is_reparse_point(generated_root):
        raise RuntimeError(f"generated asset root is a reparse point: {generated_root}")
    resolved_root = generated_root.resolve(strict=False)
    if not PACKAGE_ID_RE.fullmatch(path.name) or len(path.name) > 63:
        raise RuntimeError(f"invalid generated asset pack directory: {path}")
    if path.parent.resolve(strict=False) != resolved_root:
        raise RuntimeError(f"generated asset pack path is outside {generated_root}: {path}")
    if _is_reparse_point(path):
        raise RuntimeError(f"refusing to remove reparse point: {path}")
    resolved_path = path.resolve(strict=False)
    if resolved_path.parent != resolved_root or not resolved_path.is_relative_to(resolved_root):
        raise RuntimeError(f"generated asset pack path is outside {generated_root}: {path}")
    if path.exists():
        if not path.is_dir():
            raise RuntimeError(f"generated asset pack path is not a directory: {path}")
        reparse_points = [candidate for candidate in _reparse_points(path)]
        if reparse_points:
            raise RuntimeError(
                f"refusing to remove asset pack tree containing reparse point: {reparse_points[0]}"
            )
        shutil.rmtree(path)
    path.mkdir(parents=True, exist_ok=True)


def _reparse_points(root):
    pending = [root]
    while pending:
        current = pending.pop()
        try:
            entries = list(os.scandir(current))
        except FileNotFoundError:
            continue
        for entry in entries:
            child = Path(entry.path)
            if _is_reparse_point(child):
                yield child
                continue
            if entry.is_dir(follow_symlinks=False):
                pending.append(child)


def _copy_runtime_file(source, destination):
    if _is_reparse_point(source):
        raise RuntimeError(f"asset pack metadata must be a regular file: {source}")
    if not source.exists():
        return
    if not source.is_file():
        raise RuntimeError(f"asset pack metadata must be a regular file: {source}")
    shutil.copy2(source, destination)


def _copy_assets(source_dir, destination_dir, owner):
    for relative, source in _asset_files(source_dir, owner, required=True):
        destination = destination_dir / relative
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, destination)


def assemble_asset_pack(root, package_id):
    source_dir = root / "asset-packs" / package_id
    manifest = source_dir / "asset-pack.toml"
    pack = load_asset_pack_manifest(manifest, package_id)
    destination = root / RUNTIME_ROOT / package_id
    _remove_generated_directory(destination, root / RUNTIME_ROOT)
    _copy_runtime_file(manifest, destination / "asset-pack.toml")
    for filename in OPTIONAL_PACKAGE_FILES:
        _copy_runtime_file(source_dir / filename, destination / filename)
    for path in source_dir.iterdir():
        if path.name.startswith("LICENSE"):
            _copy_runtime_file(path, destination / path.name)
    _copy_assets(source_dir / ASSET_DIRECTORY, destination / ASSET_DIRECTORY, package_id)
    validate_runtime_tree(destination, pack)


def _validate_runtime_relative(path):
    if path.is_absolute() or "\\" in path.as_posix() or ".." in path.parts:
        raise RuntimeError(f"invalid asset pack runtime path: {path}")
    parts = path.parts
    if len(parts) == 1:
        if parts[0] == "asset-pack.toml" or parts[0] in OPTIONAL_PACKAGE_FILES:
            return
        if parts[0].startswith("LICENSE"):
            return
        raise RuntimeError(f"source or unsupported asset pack file: {path}")
    if len(parts) >= 2 and parts[0] == ASSET_DIRECTORY:
        _validate_asset_relative(path.relative_to(ASSET_DIRECTORY))
        return
    raise RuntimeError(f"unsupported asset pack runtime path: {path}")


def validate_runtime_tree(pack_dir, pack):
    if not pack_dir.is_dir() or _is_reparse_point(pack_dir):
        raise RuntimeError(f"asset pack runtime directory is missing: {pack_dir}")
    files = []
    asset_files = []
    for path in sorted(pack_dir.rglob("*")):
        relative = PurePosixPath(path.relative_to(pack_dir).as_posix())
        if _is_reparse_point(path):
            raise RuntimeError(f"reparse point in asset pack runtime: {relative}")
        if path.is_dir():
            continue
        if not path.is_file():
            raise RuntimeError(f"non-regular asset pack runtime entry: {relative}")
        _validate_runtime_relative(relative)
        if relative.parts and relative.parts[0] == ASSET_DIRECTORY:
            asset_files.append(relative)
        files.append((relative, path))
    if not any(relative == PurePosixPath("asset-pack.toml") for relative, _ in files):
        raise RuntimeError(f"asset pack runtime has no asset-pack.toml: {pack_dir}")
    if not asset_files:
        raise RuntimeError(f"asset pack runtime has no assets: {pack_dir}")
    return files


def package_asset_pack(root, package_id):
    package_dir = root / "pkg"
    package_dir.mkdir(parents=True, exist_ok=True)
    pack_dir = root / RUNTIME_ROOT / package_id
    pack = load_asset_pack_manifest(pack_dir / "asset-pack.toml", package_id)
    files = validate_runtime_tree(pack_dir, pack)
    archive = package_dir / f"{package_id}.zip"
    with zipfile.ZipFile(archive, "w", zipfile.ZIP_DEFLATED) as output:
        for relative, path in files:
            archive_path = PurePosixPath(RUNTIME_ROOT) / package_id / relative
            output.write(path, archive_path.as_posix())
    print(f"Packaged {archive}")


def _zip_entry_path(archive, name):
    if not name or name.endswith("/") or "\\" in name or "//" in name:
        raise RuntimeError(f"malformed archive entry in {archive.name}: {name}")
    if any(part in {".", ".."} for part in name.split("/")):
        raise RuntimeError(f"archive entry escapes its root in {archive.name}: {name}")
    path = PurePosixPath(name)
    if path.is_absolute():
        raise RuntimeError(f"archive entry escapes its root in {archive.name}: {name}")
    return path


def verify_asset_pack_archive(archive, package_id, source_pack):
    with zipfile.ZipFile(archive) as package:
        entries = package.infolist()
        seen = set()
        manifest_entry = PurePosixPath(RUNTIME_ROOT) / package_id / "asset-pack.toml"
        for info in entries:
            if info.filename in seen:
                raise RuntimeError(f"duplicate asset pack entry: {info.filename}")
            seen.add(info.filename)
            if info.is_dir() or stat.S_ISLNK(info.external_attr >> 16):
                raise RuntimeError(f"non-regular asset pack entry: {info.filename}")
            path = _zip_entry_path(archive, info.filename)
            if path.parts[:2] != (RUNTIME_ROOT, package_id):
                raise RuntimeError(
                    f"asset pack entry is not rooted at {RUNTIME_ROOT}/{package_id}/: {info.filename}"
                )
        if manifest_entry.as_posix() not in seen:
            raise RuntimeError(f"asset pack has no manifest: {archive.name}")
        try:
            manifest = tomllib.loads(package.read(manifest_entry.as_posix()).decode("ascii"))
        except (UnicodeError, tomllib.TOMLDecodeError) as error:
            raise RuntimeError(f"invalid asset pack manifest in {archive.name}: {error}") from error
        pack = parse_asset_pack_data(manifest, f"{archive.name}:{manifest_entry}", package_id)
        if pack != source_pack:
            raise RuntimeError(f"asset pack manifest differs from source: {archive.name}")

        root = PurePosixPath(RUNTIME_ROOT) / package_id
        asset_files = []
        for info in entries:
            path = _zip_entry_path(archive, info.filename)
            relative = PurePosixPath(*path.parts[len(root.parts):])
            _validate_runtime_relative(relative)
            if relative.parts and relative.parts[0] == ASSET_DIRECTORY:
                asset_files.append(relative)
        if not asset_files:
            raise RuntimeError(f"asset pack has no assets: {archive.name}")
        return sorted(path.as_posix() for path in asset_files)


def verify_asset_pack_sources(root):
    return discover_asset_packs(root / "asset-packs")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--pack", action="append", dest="packs", metavar="ID")
    parser.add_argument("--package", action="store_true")
    parser.add_argument("--list", action="store_true", help="List discovered asset packs and exit")
    args = parser.parse_args()

    root = Path(__file__).resolve().parent.parent
    available = verify_asset_pack_sources(root)
    if args.list:
        for name in available:
            print(name)
        return

    selected = args.packs or available
    unknown = sorted(set(selected) - set(available))
    if unknown:
        raise RuntimeError(f"unknown asset pack(s): {', '.join(unknown)}")
    for name in selected:
        assemble_asset_pack(root, name)
    if args.package:
        for name in selected:
            package_asset_pack(root, name)
    suffix = f": {', '.join(selected)}" if selected else "."
    print(f"Built {len(selected)} asset pack(s){suffix}")


if __name__ == "__main__":
    try:
        main()
    except (OSError, RuntimeError, UnicodeError, zipfile.BadZipFile) as error:
        print(f"error: {error}", file=sys.stderr)
        sys.exit(1)
