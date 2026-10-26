"""Pinned formatter setup, tracked scope, and workspace failure checks."""

import contextlib
import hashlib
import io
import subprocess
import sys
import tempfile
import unittest
import zipfile
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))

import format_lua


def formatter_archive(member):
    data = io.BytesIO()
    with zipfile.ZipFile(data, "w") as bundle:
        bundle.writestr(member, b"formatter fixture")
    return data.getvalue()


class LuaFormatterTests(unittest.TestCase):
    def test_install_uses_verified_cached_archive_without_network(self):
        with tempfile.TemporaryDirectory() as directory:
            cache = Path(directory)
            archive = cache / "downloads/test-x64.zip"
            archive.parent.mkdir()
            member = "test-x64/bin/CodeFormat"
            archive.write_bytes(formatter_archive(member))
            checksum = hashlib.sha256(archive.read_bytes()).hexdigest()
            with (
                mock.patch.object(format_lua, "_cache_root", return_value=cache),
                mock.patch.object(
                    format_lua,
                    "_platform_asset",
                    return_value=("test-x64", checksum, member),
                ),
                mock.patch("format_lua.urllib.request.urlopen") as network,
                contextlib.redirect_stdout(io.StringIO()),
            ):
                binary = format_lua.install()
                self.assertEqual(binary.read_bytes(), b"formatter fixture")
                self.assertEqual(format_lua._binary_path(), binary)
                network.assert_not_called()

    def test_install_replaces_corrupt_cached_archive(self):
        with tempfile.TemporaryDirectory() as directory:
            cache = Path(directory)
            archive = cache / "downloads/test-x64.zip"
            archive.parent.mkdir()
            archive.write_bytes(b"corrupt cache")
            member = "test-x64/bin/CodeFormat"
            data = formatter_archive(member)
            checksum = hashlib.sha256(data).hexdigest()
            with (
                mock.patch.object(format_lua, "_cache_root", return_value=cache),
                mock.patch.object(
                    format_lua,
                    "_platform_asset",
                    return_value=("test-x64", checksum, member),
                ),
                mock.patch(
                    "format_lua.urllib.request.urlopen", return_value=io.BytesIO(data)
                ) as network,
                contextlib.redirect_stdout(io.StringIO()),
            ):
                binary = format_lua.install()
            network.assert_called_once()
            self.assertEqual(archive.read_bytes(), data)
            self.assertEqual(binary.read_bytes(), b"formatter fixture")
            self.assertFalse((cache / "downloads/test-x64.zip.download").exists())

    def test_install_cleans_failed_downloads(self):
        for failure, message in (
            ("download", "could not download CodeFormat"),
            ("hash", "SHA256 mismatch"),
        ):
            with (
                self.subTest(failure=failure),
                tempfile.TemporaryDirectory() as directory,
            ):
                cache = Path(directory)
                archive = cache / "downloads/test-x64.zip"
                archive.parent.mkdir()
                archive.write_bytes(b"corrupt cache")
                checksum = "a" * 64
                member = "test-x64/bin/CodeFormat"

                def download(source, output):
                    output.write(source.read())
                    if failure == "download":
                        raise OSError("download interrupted")

                with (
                    mock.patch.object(format_lua, "_cache_root", return_value=cache),
                    mock.patch.object(
                        format_lua,
                        "_platform_asset",
                        return_value=("test-x64", checksum, member),
                    ),
                    mock.patch(
                        "format_lua.urllib.request.urlopen",
                        return_value=io.BytesIO(b"partial download"),
                    ),
                    mock.patch("format_lua.shutil.copyfileobj", side_effect=download),
                ):
                    with self.assertRaisesRegex(format_lua.FormatterError, message):
                        format_lua.install()
                self.assertEqual(archive.read_bytes(), b"corrupt cache")
                self.assertFalse((cache / "downloads/test-x64.zip.download").exists())
                self.assertFalse((cache / "test-x64-aaaaaaaa" / member).exists())

    def test_install_cleans_missing_member_and_interrupted_extraction(self):
        for failure, error, message in (
            ("missing", format_lua.FormatterError, "archive is missing"),
            ("interrupted", OSError, "extraction interrupted"),
        ):
            with (
                self.subTest(failure=failure),
                tempfile.TemporaryDirectory() as directory,
            ):
                cache = Path(directory)
                archive = cache / "downloads/test-x64.zip"
                archive.parent.mkdir()
                member = "test-x64/bin/CodeFormat"
                archive.write_bytes(
                    formatter_archive("other" if failure == "missing" else member)
                )
                checksum = hashlib.sha256(archive.read_bytes()).hexdigest()
                binary = cache / f"test-x64-{checksum[:8]}" / member

                def interrupted_copy(source, output):
                    output.write(source.read(1))
                    raise OSError("extraction interrupted")

                with (
                    mock.patch.object(format_lua, "_cache_root", return_value=cache),
                    mock.patch.object(
                        format_lua,
                        "_platform_asset",
                        return_value=("test-x64", checksum, member),
                    ),
                    mock.patch("format_lua.urllib.request.urlopen") as network,
                    mock.patch(
                        "format_lua.shutil.copyfileobj", side_effect=interrupted_copy
                    ),
                ):
                    with self.assertRaisesRegex(error, message):
                        format_lua.install()
                    network.assert_not_called()
                self.assertFalse(binary.exists())
                self.assertFalse(binary.with_name(binary.name + ".partial").exists())
                self.assertEqual(
                    hashlib.sha256(archive.read_bytes()).hexdigest(), checksum
                )

    def test_platform_guards(self):
        for system, machine, message in (
            ("Darwin", "x86_64", "pinned only for Windows and Linux x64"),
            ("Windows", "ARM64", "no pinned ARM64 asset"),
            ("Linux", "aarch64", "no pinned aarch64 asset"),
        ):
            with (
                self.subTest(system=system, machine=machine),
                mock.patch("format_lua.platform.system", return_value=system),
                mock.patch("format_lua.platform.machine", return_value=machine),
            ):
                with self.assertRaisesRegex(format_lua.FormatterError, message):
                    format_lua._platform_asset()

    def test_missing_formatter_reports_install_command(self):
        with tempfile.TemporaryDirectory() as directory:
            with (
                mock.patch.object(format_lua, "ROOT", Path(directory)),
                mock.patch.object(
                    format_lua,
                    "_platform_asset",
                    return_value=format_lua.ASSETS["Windows"],
                ),
            ):
                with self.assertRaisesRegex(
                    format_lua.FormatterError, "python tools/format_lua.py install"
                ):
                    format_lua._binary_path()

    def test_scope_uses_tracked_direct_package_lua_files(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            names = (
                "mods/example/main.lua",
                "mods/example/nested/extra.lua",
                "mods/common/helper.lua",
                "tests/fixture.lua",
            )
            for name in (*names, "mods/example/untracked.lua"):
                path = root / name
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_bytes(b"return {}\n")
            tracked = "\0".join((*names, "mods/deleted/main.lua")) + "\0"
            result = subprocess.CompletedProcess([], 0, tracked.encode(), b"")
            with (
                mock.patch.object(format_lua, "ROOT", root),
                mock.patch("format_lua.subprocess.run", return_value=result) as git,
            ):
                self.assertEqual(format_lua._tracked_lua(), ["mods/example/main.lua"])
                self.assertEqual(
                    git.call_args.args[0],
                    ["git", "ls-files", "-z", "--", "mods/*/*.lua"],
                )

    def test_scope_reports_git_failure(self):
        result = subprocess.CompletedProcess([], 1, b"", b"not a repository\n")
        with mock.patch("format_lua.subprocess.run", return_value=result):
            with self.assertRaisesRegex(
                format_lua.FormatterError, "git ls-files failed: not a repository"
            ):
                format_lua._tracked_lua()

    def test_scope_rejects_linked_source_and_parents(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            relative = "mods/example/main.lua"
            source = root / relative
            source.parent.mkdir(parents=True)
            source.write_bytes(b"return {}\n")
            result = subprocess.CompletedProcess([], 0, relative.encode() + b"\0", b"")
            for linked in (source, source.parent, source.parent.parent):
                for kind in ("symlink", "reparse"):
                    with (
                        self.subTest(linked=linked, kind=kind),
                        mock.patch.object(format_lua, "ROOT", root),
                        mock.patch("format_lua.subprocess.run", return_value=result),
                        mock.patch.object(
                            Path,
                            "lstat",
                            autospec=True,
                            side_effect=lambda path: SimpleNamespace(
                                st_file_attributes=(
                                    0x400 if kind == "reparse" and path == linked else 0
                                )
                            ),
                        ),
                        mock.patch.object(
                            Path,
                            "is_symlink",
                            autospec=True,
                            side_effect=lambda path: (
                                kind == "symlink" and path == linked
                            ),
                        ),
                    ):
                        with self.assertRaisesRegex(
                            format_lua.FormatterError,
                            "refusing to format linked Lua source",
                        ):
                            format_lua._tracked_lua()

    def test_workspace_failure_preserves_sources_after_staged_edit(self):
        for status, output in (
            (0, "Reformat main.lua fail.\n"),
            (0, "Can not read file main.lua\n"),
            (1, ""),
        ):
            with (
                self.subTest(status=status, output=output),
                tempfile.TemporaryDirectory() as directory,
            ):
                root = Path(directory)
                source = root / "mods/example/main.lua"
                source.parent.mkdir(parents=True)
                source.write_bytes(b"return {}\n")

                def fail_after_edit(binary, workspace):
                    (workspace / "mods/example/main.lua").write_bytes(b"staged edit\n")
                    return subprocess.CompletedProcess([], status, output, "")

                with (
                    mock.patch.object(format_lua, "ROOT", root),
                    mock.patch.object(
                        format_lua, "_binary_path", return_value=root / "bin"
                    ),
                    mock.patch.object(
                        format_lua, "_run_codeformat", side_effect=fail_after_edit
                    ),
                    contextlib.redirect_stdout(io.StringIO()),
                    contextlib.redirect_stderr(io.StringIO()),
                ):
                    self.assertEqual(
                        format_lua.run("format", ["mods/example/main.lua"]), 1
                    )
                self.assertEqual(source.read_bytes(), b"return {}\n")

    def test_format_exhaustion_and_concurrent_edit_preserve_sources(self):
        for failure, expected, message in (
            ("exhaustion", b"original\n", "did not stabilize"),
            (
                "concurrent edit",
                b"concurrent edit\n",
                "Lua files changed while formatting",
            ),
        ):
            with (
                self.subTest(failure=failure),
                tempfile.TemporaryDirectory() as directory,
            ):
                root = Path(directory)
                relative = "mods/example/main.lua"
                source = root / relative
                source.parent.mkdir(parents=True)
                source.write_bytes(b"original\n")

                def reformat(binary, workspace):
                    path = workspace / relative
                    if failure == "exhaustion":
                        path.write_bytes(path.read_bytes() + b"changed\n")
                    else:
                        path.write_bytes(b"stable\n")
                        source.write_bytes(b"concurrent edit\n")
                    return subprocess.CompletedProcess([], 0, "", "")

                with (
                    mock.patch.object(format_lua, "ROOT", root),
                    mock.patch.object(
                        format_lua, "_binary_path", return_value=root / "bin"
                    ),
                    mock.patch.object(
                        format_lua, "_run_codeformat", side_effect=reformat
                    ),
                    contextlib.redirect_stdout(io.StringIO()),
                    contextlib.redirect_stderr(io.StringIO()) as stderr,
                ):
                    self.assertEqual(format_lua.run("format", [relative]), 1)
                    self.assertIn(message, stderr.getvalue())
                self.assertEqual(source.read_bytes(), expected)

    def test_format_stabilizes_multiple_passes_and_check_does_not_write(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            relative = "mods/example/main.lua"
            source = root / relative
            source.parent.mkdir(parents=True)
            source.write_bytes(b"original\n")

            def reformat(binary, workspace):
                path = workspace / relative
                before = path.read_bytes()
                after = b"middle\n" if before == b"original\n" else b"stable\n"
                path.write_bytes(after)
                return subprocess.CompletedProcess([], 0, "", "")

            with (
                mock.patch.object(format_lua, "ROOT", root),
                mock.patch.object(
                    format_lua, "_binary_path", return_value=root / "bin"
                ),
                mock.patch.object(format_lua, "_run_codeformat", side_effect=reformat),
                contextlib.redirect_stdout(io.StringIO()),
                contextlib.redirect_stderr(io.StringIO()),
            ):
                self.assertEqual(format_lua.run("check", [relative]), 1)
                self.assertEqual(source.read_bytes(), b"original\n")
                self.assertEqual(format_lua.run("format", [relative]), 0)
                self.assertEqual(source.read_bytes(), b"stable\n")
                self.assertEqual(format_lua.run("check", [relative]), 0)


if __name__ == "__main__":
    unittest.main()
