#!/usr/bin/env python3
"""Assemble and package ReRevved Lua mods."""

import argparse
import os
import re
import shutil
import sys
import tomllib
import zipfile
from pathlib import Path, PurePosixPath, PureWindowsPath

PACKAGE_ID_RE = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
VERSION_RE = re.compile(r"^[0-9]+\.[0-9]+\.[0-9]+$")
PACKAGE_VERSION_RE = re.compile(r"^[0-9]+\.[0-9]+$")
MANIFEST_TOP_LEVEL_KEYS = {"manifest_version", "mod", "payload"}
MANIFEST_KEYS = {
    "id",
    "name",
    "version",
    "author",
    "description",
    "min_game_version",
}
OPTIONAL_PACKAGE_FILES = {"icon.png", "README.md"}
ASSET_DIRECTORY = "assets"
LUA_PAYLOAD_KEYS = {"kind", "entry", "api", "api_version", "requires"}
LUA_SOURCE_LIMIT = 256 * 1024
NATIVE_SOURCE_SUFFIXES = {
    ".c",
    ".cc",
    ".cmake",
    ".cpp",
    ".cxx",
    ".c++",
    ".h",
    ".hh",
    ".hpp",
    ".hxx",
    ".h++",
}
NATIVE_BINARY_SUFFIXES = {
    ".dll",
    ".so",
    ".dylib",
    ".exe",
    ".o",
    ".obj",
    ".a",
    ".lib",
    ".bin",
    ".pdb",
}


def _warn_unknown(path, scope, keys, allowed):
    for key in sorted(set(keys) - allowed):
        print(
            f"warning: {path}: unknown {scope} field {key!r}",
            file=sys.stderr,
        )


def _require_string(value, field, path, *, nonempty=False):
    if not isinstance(value, str) or (nonempty and not value.strip()):
        state = "nonempty " if nonempty else ""
        raise RuntimeError(f"{path}: {field} must be a {state}string")
    return value


def _validate_version(
    value, field, path, version_re=VERSION_RE, syntax="numeric major.minor.patch"
):
    _require_string(value, field, path)
    if not version_re.fullmatch(value):
        raise RuntimeError(f"{path}: {field} must use {syntax} syntax")


def parse_manifest_data(value, source, expected_id=None):
    """Return validated first-party Lua metadata with its payload table."""
    if not isinstance(value, dict):
        raise RuntimeError(f"{source}: manifest must be a TOML table")
    version = value.get("manifest_version")
    if type(version) is int and version == 1:
        raise RuntimeError(
            f"{source}: first-party packages are Lua; use manifest_version = 2"
        )
    if type(version) is not int or version != 2:
        raise RuntimeError(f"{source}: manifest_version must be integer 2")
    _warn_unknown(source, "top-level", value.keys(), MANIFEST_TOP_LEVEL_KEYS)
    mod = value.get("mod")
    if not isinstance(mod, dict):
        raise RuntimeError(f"{source}: [mod] table is required")
    native = sorted(_native_fields(value))
    if native:
        raise RuntimeError(
            f"{source}: native field(s) not allowed in version 2: {', '.join(native)}"
        )
    _warn_unknown(source, "[mod]", mod.keys(), MANIFEST_KEYS)

    required = {"id", "name", "version"}
    missing = sorted(required - mod.keys())
    if missing:
        raise RuntimeError(f"{source}: missing [mod] field(s): {', '.join(missing)}")

    package_id = _require_string(mod["id"], "[mod].id", source, nonempty=True)
    if not PACKAGE_ID_RE.fullmatch(package_id) or len(package_id) > 63:
        raise RuntimeError(f"{source}: [mod].id is not a valid package ID")
    if expected_id is not None and package_id != expected_id:
        raise RuntimeError(
            f"{source}: [mod].id {package_id!r} does not match {expected_id!r}"
        )
    _require_string(mod["name"], "[mod].name", source, nonempty=True)
    _validate_version(
        mod["version"],
        "[mod].version",
        source,
        PACKAGE_VERSION_RE,
        "numeric major.minor",
    )
    for field in ("author", "description"):
        if field in mod:
            _require_string(mod[field], f"[mod].{field}", source)
    if "min_game_version" in mod:
        _validate_version(mod["min_game_version"], "[mod].min_game_version", source)
    payload = _validate_lua_payload(value.get("payload"), source)
    return {**mod, "payload": payload}


def _native_fields(value):
    """Return native field names anywhere in a TOML value, as the SDK rejects."""
    found = set()
    if isinstance(value, dict):
        for key, child in value.items():
            if key in {"code", "plugin_abi"}:
                found.add(key)
            found |= _native_fields(child)
    elif isinstance(value, list):
        for child in value:
            found |= _native_fields(child)
    return found


def _reject_unknown(source, scope, fields, allowed):
    unknown = sorted(set(fields) - allowed)
    if unknown:
        raise RuntimeError(f"{source}: unknown {scope} field(s): {', '.join(unknown)}")


def _validate_lua_payload(payload, source):
    if not isinstance(payload, dict):
        raise RuntimeError(f"{source}: exactly one [payload] table is required")
    _reject_unknown(source, "[payload]", payload, LUA_PAYLOAD_KEYS)
    missing = sorted(LUA_PAYLOAD_KEYS - payload.keys())
    if missing:
        raise RuntimeError(
            f"{source}: missing [payload] field(s): {', '.join(missing)}"
        )
    if payload["kind"] != "lua":
        raise RuntimeError(f"{source}: [payload].kind must be lua")
    entry = _require_string(payload["entry"], "[payload].entry", source, nonempty=True)
    if (
        len(entry) <= len(".lua")
        or not entry.endswith(".lua")
        or any(char in entry for char in '/\\:<>"|?*')
        or any(ord(char) < 32 for char in entry)
        or PureWindowsPath(entry).is_reserved()
        or PurePosixPath(entry).name != entry
    ):
        raise RuntimeError(
            f"{source}: [payload].entry must be one safe direct-child .lua filename"
        )
    _require_string(payload["api"], "[payload].api", source, nonempty=True)
    if (
        type(payload["api_version"]) is not int
        or not 0 < payload["api_version"] <= 0xFFFFFFFF
    ):
        raise RuntimeError(
            f"{source}: [payload].api_version must be a positive integer"
        )
    requires = payload["requires"]
    if (
        not isinstance(requires, list)
        or not requires
        or any(
            not isinstance(domain, str) or not re.fullmatch(r"[a-z0-9_-]{1,63}", domain)
            for domain in requires
        )
        or len(set(requires)) != len(requires)
    ):
        raise RuntimeError(
            f"{source}: [payload].requires must be distinct nonempty domain names "
            "of 1 to 63 lowercase letters, digits, underscores or hyphens"
        )
    return payload


def validate_lua_source(data, source):
    if len(data) > LUA_SOURCE_LIMIT:
        raise RuntimeError(f"{source}: Lua entry exceeds 256 KiB")
    if data.startswith(b"\x1bLua"):
        raise RuntimeError(f"{source}: Lua bytecode is not allowed")
    if data.startswith(b"\xef\xbb\xbf"):
        raise RuntimeError(f"{source}: UTF-8 BOM is not allowed")
    if not data.isascii():
        raise RuntimeError(f"{source}: Lua entry must be ASCII")
    if b"\r" in data or not data.endswith(b"\n"):
        raise RuntimeError(
            f"{source}: Lua entry requires LF line endings and a final newline"
        )
    if b"\t" in data or any(line.rstrip(b" \t") != line for line in data.split(b"\n")):
        raise RuntimeError(f"{source}: Lua entry forbids tabs and trailing whitespace")


def _read_lua_source(path):
    if _is_reparse_point(path) or not path.is_file():
        raise RuntimeError(f"Lua entry must be a regular file: {path}")
    with path.open("rb") as entry:
        data = entry.read(LUA_SOURCE_LIMIT + 1)
    validate_lua_source(data, path)


def _validate_lua_relative(path, entry):
    if (
        "code" in path.parts
        or path.name.lower() == "cmakelists.txt"
        or path.suffix.lower() in NATIVE_SOURCE_SUFFIXES
    ):
        raise RuntimeError(f"native source or code/ in Lua package: {path}")
    if path.suffix.lower() in NATIVE_BINARY_SUFFIXES or ".so." in path.name.lower():
        raise RuntimeError(f"native binary in Lua package: {path}")
    if path == PurePosixPath(entry):
        return
    _validate_runtime_relative(path)


def validate_lua_binary_header(data, source):
    # Check executable signatures as well as extensions, including renamed assets.
    if data.startswith(
        (
            b"MZ",
            b"\x7fELF",
            b"!<arch>\n",
            b"\xfe\xed\xfa\xce",
            b"\xce\xfa\xed\xfe",
            b"\xfe\xed\xfa\xcf",
            b"\xcf\xfa\xed\xfe",
            b"\xca\xfe\xba\xbe",
            b"\xbe\xba\xfe\xca",
            b"\xca\xfe\xba\xbf",
            b"\xbf\xba\xfe\xca",
        )
    ):
        raise RuntimeError(f"native binary in Lua package: {source}")


def load_manifest(path, expected_id=None):
    try:
        value = tomllib.loads(path.read_text(encoding="ascii"))
    except (OSError, UnicodeError, tomllib.TOMLDecodeError) as error:
        raise RuntimeError(f"{path}: invalid TOML: {error}") from error
    return parse_manifest_data(value, path, expected_id)


def discover_mods(source_root):
    """Return Lua package IDs discovered under the source root."""
    mods = []
    for entry in sorted(source_root.iterdir()):
        if not entry.is_dir():
            continue
        if _is_reparse_point(entry):
            raise RuntimeError(f"reparse point in Lua package: {entry}")
        if not PACKAGE_ID_RE.fullmatch(entry.name) or len(entry.name) > 63:
            raise RuntimeError(f"invalid package source directory: {entry.name}")
        manifest = entry / "mod.toml"
        if _is_reparse_point(manifest):
            raise RuntimeError(f"reparse point in Lua package: {manifest}")
        if not manifest.is_file():
            raise RuntimeError(f"mod has no manifest: {entry.name}")
        mod = load_manifest(manifest, entry.name)
        validate_runtime_tree(entry, mod)
        mods.append(entry.name)
    return mods


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


def _remove_generated_directory(path, generated_root, *, base=None):
    generated_root = Path(generated_root)
    if base is not None:
        base = Path(base)
        if not generated_root.is_relative_to(base):
            raise RuntimeError(
                f"generated package root is outside {base}: {generated_root}"
            )
        relative = generated_root.relative_to(base)
        for depth in range(1, len(relative.parts) + 1):
            link = base.joinpath(*relative.parts[:depth])
            if _is_reparse_point(link):
                raise RuntimeError(f"generated package root is a reparse point: {link}")
    if _is_reparse_point(generated_root):
        raise RuntimeError(
            f"generated package root is a reparse point: {generated_root}"
        )
    resolved_root = generated_root.resolve(strict=False)
    if not PACKAGE_ID_RE.fullmatch(path.name) or len(path.name) > 63:
        raise RuntimeError(f"invalid generated package directory: {path}")
    if path.parent.resolve(strict=False) != resolved_root:
        raise RuntimeError(
            f"generated package path is outside {generated_root}: {path}"
        )
    if _is_reparse_point(path):
        raise RuntimeError(f"refusing to remove reparse point: {path}")
    resolved_path = path.resolve(strict=False)
    if resolved_path.parent != resolved_root or not resolved_path.is_relative_to(
        resolved_root
    ):
        raise RuntimeError(
            f"generated package path is outside {generated_root}: {path}"
        )
    if path.exists():
        if not path.is_dir():
            raise RuntimeError(f"generated package path is not a directory: {path}")
        reparse_points = list(_reparse_points(path))
        if reparse_points:
            raise RuntimeError(
                f"refusing to remove package tree containing reparse point: {reparse_points[0]}"
            )
        shutil.rmtree(path)
    path.mkdir(parents=True, exist_ok=True)


def assemble_lua_mod(root, package_id):
    source_dir = root / "mods" / package_id
    if _is_reparse_point(source_dir):
        raise RuntimeError(f"reparse point in Lua package: {source_dir}")
    linked = next(_reparse_points(source_dir), None)
    if linked is not None:
        raise RuntimeError(f"reparse point in Lua package: {linked}")
    mod = load_manifest(source_dir / "mod.toml", package_id)
    files = validate_runtime_tree(source_dir, mod)
    destination = root / "out" / "mods" / package_id
    _remove_generated_directory(destination, root / "out" / "mods", base=root)
    for relative, source in files:
        target = destination / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, target)
    validate_runtime_tree(destination, mod)


def _validate_runtime_relative(path):
    """Validate the manifest and optional runtime file paths."""
    if path.is_absolute() or "\\" in path.as_posix() or ".." in path.parts:
        raise RuntimeError(f"invalid runtime path: {path}")
    parts = path.parts
    if len(parts) == 1:
        if parts[0] == "mod.toml" or parts[0] in OPTIONAL_PACKAGE_FILES:
            return None
        if parts[0].startswith("LICENSE"):
            return None
        raise RuntimeError(f"source or unsupported file in runtime package: {path}")
    if len(parts) >= 2 and parts[0] == ASSET_DIRECTORY:
        return None
    raise RuntimeError(f"unsupported runtime package path: {path}")


def validate_runtime_tree(mod_dir, mod):
    if not mod_dir.is_dir() or mod_dir.is_symlink():
        raise RuntimeError(f"runtime package directory is missing: {mod_dir}")
    files = []
    if _is_reparse_point(mod_dir):
        raise RuntimeError(f"reparse point in Lua package: {mod_dir}")
    linked = next(_reparse_points(mod_dir), None)
    if linked is not None:
        raise RuntimeError(f"reparse point in Lua package: {linked}")
    for path in sorted(mod_dir.rglob("*")):
        relative = PurePosixPath(path.relative_to(mod_dir).as_posix())
        if path.is_symlink():
            raise RuntimeError(f"symlink in runtime package: {relative}")
        if path.is_dir():
            if "code" in relative.parts or relative.parts[0] != ASSET_DIRECTORY:
                raise RuntimeError(
                    f"unsupported directory or code/ in Lua package: {relative}"
                )
            continue
        if not path.is_file():
            raise RuntimeError(f"non-regular runtime package entry: {relative}")
        _validate_lua_relative(relative, mod["payload"]["entry"])
        with path.open("rb") as runtime_file:
            validate_lua_binary_header(runtime_file.read(8), path)
        files.append((relative, path))
    if not any(relative == PurePosixPath("mod.toml") for relative, _ in files):
        raise RuntimeError(f"runtime package has no mod.toml: {mod_dir}")
    _read_lua_source(mod_dir / mod["payload"]["entry"])
    return files


def package_mod(root, package_id):
    package_dir = root / "out" / "pkg" / "mods"
    package_dir.mkdir(parents=True, exist_ok=True)
    mod_dir = root / "out" / "mods" / package_id
    mod = load_manifest(mod_dir / "mod.toml", package_id)
    files = validate_runtime_tree(mod_dir, mod)
    archive = package_dir / f"{package_id}.zip"
    with zipfile.ZipFile(archive, "w", zipfile.ZIP_DEFLATED) as output:
        for relative, path in files:
            archive_path = PurePosixPath("mods") / package_id / relative
            output.write(path, archive_path.as_posix())
    print(f"Packaged {archive}")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--mod", action="append", dest="mods", metavar="ID")
    parser.add_argument(
        "--package",
        action="store_true",
        help="compatibility option; Lua archives are always created",
    )
    parser.add_argument(
        "--list", action="store_true", help="List discovered mods and exit"
    )
    args = parser.parse_args()

    root = Path(__file__).resolve().parent.parent
    available = discover_mods(root / "mods")
    if args.list:
        for name in available:
            print(name)
        return

    selected = args.mods or available
    unknown = sorted(set(selected) - set(available))
    if unknown:
        raise RuntimeError(f"unknown mod(s): {', '.join(unknown)}")
    if not selected:
        print("No mods found under mods/.")
        return

    for name in selected:
        assemble_lua_mod(root, name)

    for name in selected:
        package_mod(root, name)
    print(f"Built {len(selected)} mod(s): {', '.join(selected)}")


if __name__ == "__main__":
    try:
        main()
    except (OSError, RuntimeError, UnicodeError) as error:
        print(f"error: {error}", file=sys.stderr)
        sys.exit(1)
