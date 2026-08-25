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
import zipfile
from pathlib import Path


PLATFORMS = {
    "windows-x64": {"sdk": "win-amd64", "prefix": "", "extension": ".dll"},
    "windows-arm64": {"sdk": "win-arm64", "prefix": "", "extension": ".dll"},
    "linux-x64": {"sdk": "linux-amd64", "prefix": "lib", "extension": ".so"},
    "linux-arm64": {"sdk": "linux-arm64", "prefix": "lib", "extension": ".so"},
    "macos-x64": {"sdk": "mac-amd64", "prefix": "lib", "extension": ".dylib"},
    "macos-arm64": {"sdk": "mac-arm64", "prefix": "lib", "extension": ".dylib"},
}
POSTFIXES = {"Release": "", "RelWithDebInfo": "rd", "Debug": "d"}


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


def discover_mods(source_root):
    code_mods = []
    asset_mods = []
    for entry in sorted(source_root.iterdir()):
        if not entry.is_dir() or entry.name == "common":
            continue
        if (entry / "CMakeLists.txt").is_file():
            code_mods.append(entry.name)
        elif (entry / "mod.toml").is_file():
            asset_mods.append(entry.name)
    return code_mods, asset_mods


def find_compiler():
    names = ("clang++-22",) if platform.system() == "Linux" else ("clang++",)
    for name in names:
        path = shutil.which(name)
        if path:
            return path
    raise RuntimeError("Clang was not found in PATH")


def find_binary(build_dir, name, target, config):
    info = PLATFORMS[target]
    filename = f"{info['prefix']}{name}{POSTFIXES[config]}{info['extension']}"
    candidate = build_dir / filename
    if candidate.is_file():
        return candidate
    raise RuntimeError(f"built plugin not found under {build_dir}: {filename}")


def build_code_mod(root, name, target, sdk_dir, config):
    source_dir = root / "src" / name
    build_dir = root / "out" / "build" / target / name
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
        f"-DCMAKE_CXX_COMPILER={find_compiler()}",
    ]
    if target.startswith("macos-"):
        configure.append("-DCMAKE_OSX_DEPLOYMENT_TARGET=13.3")
    run(configure)
    run(["cmake", "--build", build_dir, "--parallel", str(os.cpu_count() or 1)])
    return find_binary(build_dir, name, target, config)


def assemble_code_mod(root, name, target, binary):
    source_dir = root / "src" / name
    destination = root / "mods" / name
    shutil.copytree(source_dir, destination, dirs_exist_ok=True)
    code_dir = destination / "code" / target
    code_dir.mkdir(parents=True, exist_ok=True)
    shutil.copy2(binary, code_dir / binary.name)

    manifest = destination / "mod.toml"
    if manifest.is_file():
        lines = manifest.read_text(encoding="ascii").splitlines()
        platforms = sorted(path.name for path in (destination / "code").iterdir() if path.is_dir())
        replacement = f'platform = "{",".join(platforms)}"'
        for index, line in enumerate(lines):
            if re.match(r"^\s*platform\s*=", line):
                lines[index] = replacement
                break
        else:
            lines.append(replacement)
        manifest.write_text("\n".join(lines) + "\n", encoding="ascii")


def assemble_asset_mod(root, name):
    shutil.copytree(root / "src" / name, root / "mods" / name, dirs_exist_ok=True)


def package_mod(root, name):
    package_dir = root / "pkg"
    package_dir.mkdir(parents=True, exist_ok=True)
    archive = package_dir / f"{name}.zip"
    mod_dir = root / "mods" / name
    with zipfile.ZipFile(archive, "w", zipfile.ZIP_DEFLATED) as output:
        for path in mod_dir.rglob("*"):
            if path.is_file():
                output.write(path, Path(name) / path.relative_to(mod_dir))
    print(f"Packaged {archive}")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--sdk-dir", type=Path, default=Path("sdk"))
    parser.add_argument("--mod", action="append", dest="mods", metavar="NAME")
    parser.add_argument("--target", choices=PLATFORMS, default=host_platform())
    parser.add_argument("--config", choices=POSTFIXES, default="Release")
    parser.add_argument("--package", action="store_true")
    parser.add_argument("--list", action="store_true", help="List discovered mods and exit")
    args = parser.parse_args()

    root = Path(__file__).resolve().parent.parent
    code_mods, asset_mods = discover_mods(root / "src")
    available = code_mods + asset_mods
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

    for name in selected:
        if name in asset_mods:
            assemble_asset_mod(root, name)

    selected_code = [name for name in selected if name in code_mods]
    if selected_code:
        if not args.target:
            raise RuntimeError("the native host platform could not be detected")
        if args.target != host_platform():
            raise RuntimeError(
                f"cross-building {args.target} is not configured; run on that native host"
            )
        sdk_dir = installed_sdk(args.sdk_dir.resolve(), args.target)
        validate_sdk_version(root, sdk_dir)
        for name in selected_code:
            binary = build_code_mod(root, name, args.target, sdk_dir, args.config)
            assemble_code_mod(root, name, args.target, binary)

    if args.package:
        for name in selected:
            package_mod(root, name)
    print(f"Built {len(selected)} mod(s): {', '.join(selected)}")


if __name__ == "__main__":
    try:
        main()
    except (OSError, RuntimeError, subprocess.CalledProcessError) as error:
        print(f"error: {error}", file=sys.stderr)
        sys.exit(1)
