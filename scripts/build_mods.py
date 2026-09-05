#!/usr/bin/env python3
"""Build and assemble ReRevved mod packages."""

import argparse
import json
import os
import platform
import re
import shutil
import subprocess
import sys
import tomllib
import zipfile
from pathlib import Path, PurePosixPath


PLATFORMS = {
    "windows-x64": {"sdk": "win-amd64", "prefix": "", "extension": ".dll"},
    "windows-arm64": {"sdk": "win-arm64", "prefix": "", "extension": ".dll"},
    "linux-x64": {"sdk": "linux-amd64", "prefix": "lib", "extension": ".so"},
    "linux-arm64": {"sdk": "linux-arm64", "prefix": "lib", "extension": ".so"},
    "macos-x64": {"sdk": "mac-amd64", "prefix": "lib", "extension": ".dylib"},
    "macos-arm64": {"sdk": "mac-arm64", "prefix": "lib", "extension": ".dylib"},
}
POSTFIXES = {"Release": "", "RelWithDebInfo": "rd", "Debug": "d"}
PACKAGE_ID_RE = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
VERSION_RE = re.compile(r"^[0-9]+\.[0-9]+\.[0-9]+$")
MANIFEST_TOP_LEVEL_KEYS = {"manifest_version", "mod"}
MANIFEST_KEYS = {
    "id",
    "name",
    "version",
    "author",
    "description",
    "min_game_version",
    "code",
    "plugin_abi",
}
OPTIONAL_PACKAGE_FILES = {"icon.png", "README.md"}


def host_platform():
    system = platform.system()
    machine = platform.machine().lower()
    if system == "Windows" and machine in ("amd64", "x86_64"):
        return "windows-x64"
    if system == "Windows" and machine in ("arm64", "aarch64"):
        return "windows-arm64"
    if system == "Linux" and machine in ("amd64", "x86_64"):
        return "linux-x64"
    if system == "Linux" and machine in ("arm64", "aarch64"):
        return "linux-arm64"
    if system == "Darwin" and machine in ("amd64", "x86_64"):
        return "macos-x64"
    if system == "Darwin" and machine in ("arm64", "aarch64"):
        return "macos-arm64"
    return None


def run(command):
    print("+", " ".join(str(part) for part in command))
    subprocess.run(command, check=True)


def installed_sdk(requested, target):
    candidates = [requested, requested / PLATFORMS[target]["sdk"]]
    for candidate in candidates:
        if (candidate / "lib" / "cmake" / "rexglue").is_dir():
            return candidate.resolve()
    raise RuntimeError(
        f"ReXGlue SDK for {target} not found under {requested}; "
        "install the version in rexglue-sdk.lock.json"
    )


def validate_sdk_version(root, sdk_dir):
    lock = json.loads((root / "rexglue-sdk.lock.json").read_text(encoding="ascii"))
    version_header = sdk_dir / "include" / "rex" / "version.h"
    if not version_header.is_file():
        raise RuntimeError(f"SDK version header not found: {version_header}")
    match = re.search(
        r'^#define REXGLUE_VERSION_STRING "([^"]+)"$',
        version_header.read_text(encoding="ascii"),
        re.MULTILINE,
    )
    if not match:
        raise RuntimeError(f"SDK version is unreadable: {version_header}")
    if match.group(1) != lock["version"]:
        raise RuntimeError(
            f"SDK version mismatch: expected {lock['version']}, found {match.group(1)}"
        )


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


def _validate_version(value, field, path):
    _require_string(value, field, path)
    if not VERSION_RE.fullmatch(value):
        raise RuntimeError(
            f"{path}: {field} must use numeric major.minor.patch syntax"
        )


def parse_manifest_data(value, source, expected_id=None):
    """Validate and return the version-1 [mod] table from TOML data."""
    if not isinstance(value, dict):
        raise RuntimeError(f"{source}: manifest must be a TOML table")
    _warn_unknown(source, "top-level", value.keys(), MANIFEST_TOP_LEVEL_KEYS)
    if type(value.get("manifest_version")) is not int or value["manifest_version"] != 1:
        raise RuntimeError(f"{source}: manifest_version must be integer 1")
    mod = value.get("mod")
    if not isinstance(mod, dict):
        raise RuntimeError(f"{source}: [mod] table is required")
    _warn_unknown(source, "[mod]", mod.keys(), MANIFEST_KEYS)

    required = {"id", "name", "version", "code", "plugin_abi"}
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
    _validate_version(mod["version"], "[mod].version", source)
    code = _require_string(mod["code"], "[mod].code", source, nonempty=True)
    if (
        code in {".", ".."}
        or "/" in code
        or "\\" in code
        or Path(code).name != code
        or Path(code).suffix
    ):
        raise RuntimeError(f"{source}: [mod].code must be one filename stem")
    plugin_abi = mod["plugin_abi"]
    if isinstance(plugin_abi, bool) or not isinstance(plugin_abi, int) or plugin_abi != 1:
        raise RuntimeError(f"{source}: [mod].plugin_abi must be integer 1")
    for field in ("author", "description"):
        if field in mod:
            _require_string(mod[field], f"[mod].{field}", source)
    if "min_game_version" in mod:
        _validate_version(mod["min_game_version"], "[mod].min_game_version", source)
    return mod


def load_manifest(path, expected_id=None):
    try:
        value = tomllib.loads(path.read_text(encoding="ascii"))
    except (OSError, UnicodeError, tomllib.TOMLDecodeError) as error:
        raise RuntimeError(f"{path}: invalid TOML: {error}") from error
    return parse_manifest_data(value, path, expected_id)


def discover_mods(source_root):
    """Return native package IDs discovered under the source root."""
    code_mods = []
    for entry in sorted(source_root.iterdir()):
        if not entry.is_dir() or entry.name == "common":
            continue
        if not PACKAGE_ID_RE.fullmatch(entry.name) or len(entry.name) > 63:
            raise RuntimeError(f"invalid package source directory: {entry.name}")
        manifest = entry / "mod.toml"
        if not manifest.is_file():
            raise RuntimeError(f"mod has no manifest: {entry.name}")
        load_manifest(manifest, entry.name)
        if not (entry / "CMakeLists.txt").is_file():
            raise RuntimeError(
                f"{entry.name}: native packages require a CMakeLists.txt payload"
            )
        code_mods.append(entry.name)
    return code_mods


def find_compiler():
    names = ("clang++-22",) if platform.system() == "Linux" else ("clang++",)
    for name in names:
        path = shutil.which(name)
        if path:
            return path
    raise RuntimeError("Clang was not found in PATH")


def find_binary(build_dir, code, target, config):
    info = PLATFORMS[target]
    filename = f"{info['prefix']}{code}{POSTFIXES[config]}{info['extension']}"
    candidate = build_dir / filename
    if candidate.is_file():
        return candidate
    raise RuntimeError(f"built plugin not found under {build_dir}: {filename}")


def build_code_mod(root, package_id, target, sdk_dir, config):
    source_dir = root / "src" / package_id
    manifest = load_manifest(source_dir / "mod.toml", package_id)
    code = manifest["code"]
    build_dir = root / "out" / "build" / target / package_id
    rexglue_dir = sdk_dir / "lib" / "cmake" / "rexglue"
    configure = [
        "cmake",
        "-S",
        source_dir,
        "-B",
        build_dir,
        "-G",
        "Ninja",
        f"-DCMAKE_BUILD_TYPE={config}",
        f"-DCMAKE_PREFIX_PATH={sdk_dir}",
        f"-Drexglue_DIR={rexglue_dir}",
        f"-DCMAKE_CXX_COMPILER={find_compiler()}",
    ]
    if target.startswith("macos-"):
        configure.append("-DCMAKE_OSX_DEPLOYMENT_TARGET=13.3")
    run(configure)
    run(["cmake", "--build", build_dir, "--parallel", str(os.cpu_count() or 1)])
    return find_binary(build_dir, code, target, config)


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


def _remove_generated_directory(path, generated_root):
    generated_root = Path(generated_root)
    if _is_reparse_point(generated_root):
        raise RuntimeError(f"generated package root is a reparse point: {generated_root}")
    resolved_root = generated_root.resolve(strict=False)
    if not PACKAGE_ID_RE.fullmatch(path.name) or len(path.name) > 63:
        raise RuntimeError(f"invalid generated package directory: {path}")
    if path.parent.resolve(strict=False) != resolved_root:
        raise RuntimeError(f"generated package path is outside {generated_root}: {path}")
    if _is_reparse_point(path):
        raise RuntimeError(f"refusing to remove reparse point: {path}")
    resolved_path = path.resolve(strict=False)
    if resolved_path.parent != resolved_root or not resolved_path.is_relative_to(resolved_root):
        raise RuntimeError(f"generated package path is outside {generated_root}: {path}")
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


def _copy_runtime_file(source, destination):
    if source.is_symlink():
        raise RuntimeError(f"runtime metadata must be a regular file: {source}")
    if not source.exists():
        return
    if not source.is_file():
        raise RuntimeError(f"runtime metadata must be a regular file: {source}")
    shutil.copy2(source, destination)


def assemble_code_mod(root, package_id, target, binary):
    source_dir = root / "src" / package_id
    manifest = source_dir / "mod.toml"
    mod = load_manifest(manifest, package_id)
    destination = root / "mods" / package_id
    _remove_generated_directory(destination, root / "mods")
    _copy_runtime_file(manifest, destination / "mod.toml")
    for filename in OPTIONAL_PACKAGE_FILES:
        _copy_runtime_file(source_dir / filename, destination / filename)
    for path in source_dir.iterdir():
        if path.name.startswith("LICENSE"):
            _copy_runtime_file(path, destination / path.name)
    info = PLATFORMS[target]
    expected = {
        f"{info['prefix']}{mod['code']}{postfix}{info['extension']}"
        for postfix in POSTFIXES.values()
    }
    if binary.name not in expected:
        raise RuntimeError(f"built plugin does not match declared code stem: {binary.name}")
    code_dir = destination / "code" / target
    code_dir.mkdir(parents=True, exist_ok=True)
    shutil.copy2(binary, code_dir / binary.name)


def _validate_runtime_relative(path, code):
    """Validate a runtime tree entry and return its platform, if binary."""
    if path.is_absolute() or "\\" in path.as_posix() or ".." in path.parts:
        raise RuntimeError(f"invalid runtime path: {path}")
    parts = path.parts
    if len(parts) == 1:
        if parts[0] == "mod.toml" or parts[0] in OPTIONAL_PACKAGE_FILES:
            return None
        if parts[0].startswith("LICENSE"):
            return None
        raise RuntimeError(f"source or unsupported file in runtime package: {path}")
    if len(parts) == 3 and parts[0] == "code" and parts[1] in PLATFORMS:
        info = PLATFORMS[parts[1]]
        expected = {
            f"{info['prefix']}{code}{postfix}{info['extension']}"
            for postfix in POSTFIXES.values()
        }
        if parts[2] not in expected:
            raise RuntimeError(f"binary does not match declared code stem: {path}")
        return parts[1]
    raise RuntimeError(f"unsupported runtime package path: {path}")


def validate_runtime_tree(mod_dir, mod):
    if not mod_dir.is_dir() or mod_dir.is_symlink():
        raise RuntimeError(f"runtime package directory is missing: {mod_dir}")
    files = []
    platforms = set()
    for path in sorted(mod_dir.rglob("*")):
        relative = PurePosixPath(path.relative_to(mod_dir).as_posix())
        if path.is_symlink():
            raise RuntimeError(f"symlink in runtime package: {relative}")
        if path.is_dir():
            continue
        if not path.is_file():
            raise RuntimeError(f"non-regular runtime package entry: {relative}")
        platform_name = _validate_runtime_relative(relative, mod["code"])
        if platform_name:
            platforms.add(platform_name)
        files.append((relative, path))
    if not any(relative == PurePosixPath("mod.toml") for relative, _ in files):
        raise RuntimeError(f"runtime package has no mod.toml: {mod_dir}")
    if not platforms:
        raise RuntimeError(f"runtime package has no qualified native binary: {mod_dir}")
    return files


def package_mod(root, package_id):
    package_dir = root / "pkg"
    package_dir.mkdir(parents=True, exist_ok=True)
    mod_dir = root / "mods" / package_id
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
    parser.add_argument("--sdk-dir", type=Path, default=Path("sdk"))
    parser.add_argument("--mod", action="append", dest="mods", metavar="ID")
    parser.add_argument("--target", choices=PLATFORMS, default=host_platform())
    parser.add_argument("--config", choices=POSTFIXES, default="Release")
    parser.add_argument("--package", action="store_true")
    parser.add_argument("--list", action="store_true", help="List discovered mods and exit")
    args = parser.parse_args()

    root = Path(__file__).resolve().parent.parent
    available = discover_mods(root / "src")
    if args.list:
        for name in available:
            print(name)
        return

    selected = args.mods or available
    unknown = sorted(set(selected) - set(available))
    if unknown:
        raise RuntimeError(f"unknown mod(s): {', '.join(unknown)}")
    if not selected:
        print("No mods found under src/.")
        return

    if not args.target:
        raise RuntimeError("the native host platform could not be detected")
    if args.target != host_platform():
        raise RuntimeError(
            f"cross-building {args.target} is not configured; run on that native host"
        )
    sdk_dir = installed_sdk(args.sdk_dir.resolve(), args.target)
    validate_sdk_version(root, sdk_dir)
    for name in selected:
        binary = build_code_mod(root, name, args.target, sdk_dir, args.config)
        assemble_code_mod(root, name, args.target, binary)

    if args.package:
        for name in selected:
            package_mod(root, name)
    print(f"Built {len(selected)} mod(s): {', '.join(selected)}")


if __name__ == "__main__":
    try:
        main()
    except (OSError, RuntimeError, subprocess.CalledProcessError, UnicodeError) as error:
        print(f"error: {error}", file=sys.stderr)
        sys.exit(1)
