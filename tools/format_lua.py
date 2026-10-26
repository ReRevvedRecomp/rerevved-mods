"""Install and run the pinned formatter on tracked, authored Lua files."""

from __future__ import annotations

import argparse
import hashlib
import os
import platform
import re
import shutil
import stat
import subprocess
import sys
import tempfile
import urllib.error
import urllib.request
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
VERSION = "1.6.0"
RELEASE_URL = (
    "https://github.com/CppCXY/EmmyLuaCodeStyle/releases/download/"
    f"{VERSION}/{{asset}}.zip"
)
ASSETS = {
    "Windows": (
        "win32-x64",
        "9eba5778ce40ef4e32e2aa8829f3137577fa8000e09ac8bace737d42d59dc299",
        "win32-x64/bin/CodeFormat.exe",
    ),
    "Linux": (
        "linux-x64",
        "7518ec1702a9833f053b7b4710f20e6205b13204f06562eb226dce409da42298",
        "linux-x64/bin/CodeFormat",
    ),
}
# Workspace mode can report per-file failures while returning success.
FORMAT_FAILURE = re.compile(r"(?m)^(?:Reformat .+ fail\.|Can not read file .+)$")
# CodeFormat 1.6.0 can adjust Allman table-call indentation on a later pass.
MAX_FORMAT_PASSES = 4


class FormatterError(RuntimeError):
    """A setup, scope, or formatter failure with a useful message."""


def _platform_asset() -> tuple[str, str, str]:
    try:
        asset = ASSETS[platform.system()]
    except KeyError as exc:
        raise FormatterError(
            "CodeFormat 1.6.0 is pinned only for Windows and Linux x64"
        ) from exc
    if platform.machine().lower() not in {"amd64", "x86_64", "x64"}:
        raise FormatterError(
            f"CodeFormat 1.6.0 has no pinned {platform.machine()} asset"
        )
    return asset


def _cache_root() -> Path:
    return ROOT / "out" / "tools" / "codeformat" / VERSION


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for block in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def install() -> Path:
    asset, checksum, binary_member = _platform_asset()
    cache = _cache_root()
    destination = cache / f"{asset}-{checksum[:8]}"
    binary = destination / Path(binary_member)
    if binary.is_file():
        if os.name != "nt":
            binary.chmod(
                binary.stat().st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH
            )
        print(f"CodeFormat {VERSION} is installed: {binary}")
        return binary

    downloads = cache / "downloads"
    downloads.mkdir(parents=True, exist_ok=True)
    archive = downloads / f"{asset}.zip"
    if not archive.is_file() or _sha256(archive) != checksum:
        temporary = downloads / f"{asset}.zip.download"
        try:
            request = urllib.request.Request(
                RELEASE_URL.format(asset=asset),
                headers={"User-Agent": "ReRevvedLuaFormatter"},
            )
            with urllib.request.urlopen(request, timeout=60) as response:
                with temporary.open("wb") as output:
                    shutil.copyfileobj(response, output)
            actual = _sha256(temporary)
            if actual != checksum:
                raise FormatterError(
                    f"CodeFormat asset SHA256 mismatch: expected {checksum}, got {actual}"
                )
            os.replace(temporary, archive)
        except (OSError, urllib.error.URLError) as exc:
            raise FormatterError(
                f"could not download CodeFormat {VERSION}: {exc}"
            ) from exc
        finally:
            temporary.unlink(missing_ok=True)

    destination.mkdir(parents=True, exist_ok=True)
    # Extract beside the binary and rename so an interrupted install is never
    # mistaken for a complete one.
    partial = binary.with_name(binary.name + ".partial")
    try:
        with zipfile.ZipFile(archive) as bundle:
            with bundle.open(binary_member) as source:
                binary.parent.mkdir(parents=True, exist_ok=True)
                with partial.open("wb") as output:
                    shutil.copyfileobj(source, output)
        if os.name != "nt":
            partial.chmod(
                partial.stat().st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH
            )
        os.replace(partial, binary)
    except KeyError as exc:
        raise FormatterError(f"CodeFormat archive is missing {exc}") from exc
    finally:
        partial.unlink(missing_ok=True)
    print(f"Installed CodeFormat {VERSION}: {binary}")
    return binary


def _binary_path() -> Path:
    asset, checksum, binary_member = _platform_asset()
    destination = _cache_root() / f"{asset}-{checksum[:8]}"
    binary = destination / Path(binary_member)
    if not binary.is_file():
        raise FormatterError(
            f"CodeFormat {VERSION} is not installed; run "
            "'python tools/format_lua.py install' explicitly"
        )
    if os.name != "nt" and not os.access(binary, os.X_OK):
        raise FormatterError(
            f"CodeFormat {VERSION} is not executable; run "
            "'python tools/format_lua.py install' explicitly"
        )
    return binary


def _tracked_lua() -> list[str]:
    result = subprocess.run(
        ["git", "ls-files", "-z", "--", "mods/*/*.lua"],
        cwd=ROOT,
        check=False,
        capture_output=True,
    )
    if result.returncode:
        detail = result.stderr.decode("utf-8", errors="replace").strip()
        raise FormatterError(f"git ls-files failed: {detail}")

    tracked = [
        path.decode("utf-8")
        for path in result.stdout.split(b"\0")
        if path and path.lower().endswith(b".lua")
    ]
    selected = []
    for relative in tracked:
        parts = Path(relative).parts
        if len(parts) != 3 or parts[0] != "mods" or parts[1] == "common":
            continue
        source = ROOT / Path(relative)
        if not source.is_file():
            continue
        for path in (source, source.parent, source.parent.parent):
            attributes = getattr(path.lstat(), "st_file_attributes", 0)
            if path.is_symlink() or attributes & 0x400:
                raise FormatterError(
                    f"refusing to format linked Lua source: {relative}"
                )
        selected.append(relative)
    return sorted(selected)


def _snapshot(workspace: Path, files: list[str]) -> dict[str, bytes]:
    return {relative: (workspace / Path(relative)).read_bytes() for relative in files}


def _run_codeformat(binary: Path, workspace: Path) -> subprocess.CompletedProcess[str]:
    command = [
        str(binary),
        "format",
        "-w",
        str(workspace),
        "-c",
        str(ROOT / ".editorconfig"),
        "-ow",
    ]
    return subprocess.run(
        command,
        cwd=ROOT,
        capture_output=True,
        text=True,
        errors="replace",
        check=False,
    )


def _report_failure(result: subprocess.CompletedProcess[str]) -> None:
    output = result.stdout + result.stderr
    if output:
        print(output, end="" if output.endswith("\n") else "\n")
    else:
        print(f"CodeFormat exited with status {result.returncode}", file=sys.stderr)


def run(action: str, files: list[str]) -> int:
    if not files:
        print("No authored tracked Lua files selected.")
        return 0
    originals = {relative: (ROOT / Path(relative)).read_bytes() for relative in files}
    binary = _binary_path()
    workspace_parent = _cache_root() / "work"
    workspace_parent.mkdir(parents=True, exist_ok=True)

    with tempfile.TemporaryDirectory(prefix="lua-", dir=workspace_parent) as name:
        workspace = Path(name)
        for relative, content in originals.items():
            target = workspace / Path(relative)
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(content)

        before = _snapshot(workspace, files)
        stable = False
        passes = MAX_FORMAT_PASSES if action == "format" else 1
        for _ in range(passes):
            result = _run_codeformat(binary, workspace)
            if result.returncode or FORMAT_FAILURE.search(
                result.stdout + result.stderr
            ):
                _report_failure(result)
                return 1
            after = _snapshot(workspace, files)
            if after == before:
                stable = True
                break
            before = after

        if not stable:
            if action == "format":
                print(
                    f"CodeFormat did not stabilize in {MAX_FORMAT_PASSES} passes; "
                    "no repository files were written.",
                    file=sys.stderr,
                )
            else:
                changed = [
                    relative
                    for relative in files
                    if originals[relative] != (workspace / Path(relative)).read_bytes()
                ]
                print("Lua formatting required:", file=sys.stderr)
                for relative in changed[:20]:
                    print(f"  {relative}", file=sys.stderr)
                if len(changed) > 20:
                    print(f"  ... and {len(changed) - 20} more", file=sys.stderr)
            return 1

        if action == "check":
            print(f"CodeFormat {VERSION}: {len(files)} authored Lua files conform.")
            return 0

        changed = [
            relative
            for relative in files
            if originals[relative] != (workspace / Path(relative)).read_bytes()
        ]
        changed_during_run = [
            relative
            for relative in files
            if (ROOT / Path(relative)).read_bytes() != originals[relative]
        ]
        if changed_during_run:
            print(
                "Lua files changed while formatting; no files were written: "
                + ", ".join(changed_during_run),
                file=sys.stderr,
            )
            return 1
        for relative in changed:
            (ROOT / Path(relative)).write_bytes(
                (workspace / Path(relative)).read_bytes()
            )
        print(f"CodeFormat {VERSION}: formatted {len(changed)} authored Lua files.")
        return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)
    subparsers.add_parser("install", help="download and verify the pinned formatter")
    subparsers.add_parser("check", help="check all tracked, authored Lua files")
    subparsers.add_parser("format", help="format all tracked, authored Lua files")
    args = parser.parse_args(argv)

    try:
        if args.command == "install":
            install()
            return 0
        return run(args.command, _tracked_lua())
    except FormatterError as exc:
        print(f"Lua formatter: {exc}", file=sys.stderr)
        return 1
    except (OSError, zipfile.BadZipFile) as exc:
        print(f"Lua formatter: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
