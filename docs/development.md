# Development

Run commands from the repository root. Package assembly uses Python and does
not require the ReXGlue SDK or a C++ compiler.

## Prerequisites

- Python 3.11 or newer; the scripts use the standard-library `tomllib` module.
- Git and a checkout for the formatter and full verification. They enumerate
  files with `git ls-files`; an exported source tree is enough for assembly,
  but is not a substitute for the checkout-based checks.
- The pinned Python tools in
  [`scripts/requirements-dev.txt`](../scripts/requirements-dev.txt).
- CodeFormat 1.6.0 for Lua formatting. The wrapper pins Windows x64 and Linux
  x64 assets with SHA-256 checks.

Install the development tools explicitly:

```text
python -m pip install -r scripts/requirements-dev.txt
python scripts/format_lua.py install
```

These installation commands can download tools. Neither Lua `check` nor
`format` installs or downloads the formatter.

## Build packages

List package IDs without generating output:

```text
python scripts/build_mods.py --list
```

Assemble all packages, or select IDs with repeated `--mod` options:

```text
python scripts/build_mods.py
python scripts/build_mods.py --mod hills-production
python scripts/build_mods.py --mod founding-militia --mod chinese-library-gold
```

Every selected package produces both:

- `mods/<id>/`, the runtime tree containing the manifest, Lua entry, and
  allowed optional files.
- `pkg/mods/<id>.zip`, rooted at `mods/<id>/` for installation.

`--package` is accepted but unnecessary for Lua mods: archives are always
written. Assembly recreates each selected generated `mods/<id>/` folder.
Keep edits in `src/<id>/`, not the generated tree. The
[authoring guide](making-mods.md#source-and-runtime-files) defines the contents;
the title's [mods guide](https://github.com/ReRevvedRecomp/rerevved/blob/main/docs/mods.md#install-or-customize-a-package)
covers installation.

The package builder validates all discovered source packages before selecting
what to assemble. An invalid unselected package can therefore block a build.

## Checks and tests

After installing the tools, run:

```text
python scripts/format_lua.py check
python -m ruff check scripts tests
python -m ruff format --check scripts tests
python -m unittest discover -s tests
python scripts/verify.py
```

`verify.py` includes those formatter, lint, and unit-test checks. It also
validates manifests and lock declarations, checks public-file hygiene and
`git diff --check`, builds all Lua mods and any asset packs, and checks the
resulting archives. It writes generated package output; it is not a read-only
check. The unit tests also exercise assembly and packaging in temporary trees.

On a host without a pinned CodeFormat asset, use:

```text
python scripts/verify.py --skip-lua-format
```

That skips only CodeFormat; Lua source checks and every other verification
step still run. Report the skipped formatting check rather than calling it a
full formatter pass.

Before submitting a change, inspect the complete diff, run `git diff --check`,
and check documentation links. Runtime tests belong in a compatible ReRevved
installation. A passing package test does not prove gameplay behavior.

## Compatibility locks

The [title lock](../rerevved-api.lock.json) and
[SDK lock](../rexglue-sdk.lock.json) record the target title/SDK revisions.
They are compatibility records, not package build dependencies. The verifier
checks their declared repositories, commit syntax, SDK version suffix, and
expected title ABI fields; it does not fetch or run either dependency.

To also require a local title checkout's HEAD to match the title lock:

```text
python scripts/verify.py --title-dir <title-checkout>
```

This is an exact commit check, not a gameplay test or an SDK checkout check.
Use the locked checkout for that check; do not rewrite a lock merely to make
an unrelated local checkout pass.

## Lua formatter

The root [`.editorconfig`](../.editorconfig) uses the Lua settings from
[LandSandBoat/server](https://github.com/LandSandBoat/server/blob/6f40ea8625f1baf10b7060210937491b28181a4e/.editorconfig)
at commit `6f40ea8625f1baf10b7060210937491b28181a4e`: four-space indentation,
single quotes, and Allman table braces.

[`scripts/format_lua.py`](../scripts/format_lua.py) wraps
[EmmyLuaCodeStyle CodeFormat 1.6.0](https://github.com/CppCXY/EmmyLuaCodeStyle/releases/tag/1.6.0).
After installation:

```text
python scripts/format_lua.py format
python scripts/format_lua.py check
```

The wrapper selects tracked Lua files directly inside each package directory
(`src/*/*.lua`), excluding `src/common/`. Track new files before expecting the
formatter to check them.
Formatting stabilizes in a temporary workspace before writing source; a failed
pass writes no source.

Installation reuses a verified cached archive or downloads the pinned asset.
The cache is under `out/tools/codeformat/1.6.0/`, with downloaded archives in
its `downloads/` directory. Package discovery and assembly also enforce the
[Lua source constraints](making-mods.md#source-and-runtime-files), independently
of CodeFormat.

## Continuous integration

[Checks](../.github/workflows/checks.yml) runs on pushes to `main`, pull
requests, and manual dispatch. Its Linux x64 job uses Ubuntu 24.04 and Python
3.12, checks out the locked title revision, installs the pinned tools, and
runs `verify.py --title-dir title-src`.

It uploads `pkg/mods/*.zip` and `pkg/asset-overrides/*.zip` as the
`rerevved-mods-linux-x64` workflow artifact, retained for 14 days. This workflow
does not publish a title release. The title chooses the mods revision and
[bundled package set](packages.md#bundled-packages) in its own packaging flow.

## Pull requests

Contributions are GPL-3.0-only. Open pull requests against `main`. Keep changes
to Lua rules, manifests, packaging, and documentation. Guest behavior and the
gameplay API belong in the title; reusable runtime facilities belong in the SDK.
Keep the title and SDK locks exact, and change them only together with the
matching runtime change. Do not submit retail files, extracted assets, guest
addresses, generated packages, build output, credentials, or machine paths.

Read [Making mods](making-mods.md) and the [style guide](style-guide.md), then
run the [checks](#checks-and-tests). Explain the change, the checks run, and
what you tested in the game. A package that builds is not proof that its rule
works in the game.

Commit subjects use `type: imperative summary`, at most 50 characters, with a
lowercase type and a lowercase opening verb.
