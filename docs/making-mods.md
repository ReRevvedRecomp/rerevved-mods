# Making ReRevved mods

This guide covers the supported source layout, manifest fields, and build and
package commands.

## Source layout

Put each mod directly under `src/<name>/`.

- A code mod has `src/<name>/CMakeLists.txt` and `src/<name>/mod.toml`.
- An asset mod has `src/<name>/mod.toml` and no `CMakeLists.txt`.
- `src/common/` is reserved for shared helpers and the mirrored title API.

List the mods discovered by this rule with:

```text
python scripts/build_mods.py --list
```

## Manifest

Every source mod under `src/` requires `name`, `version`, `author`, and
`description` in `mod.toml`. A code mod also sets `code` to the exact source
directory name.

```toml
name = "Example Mod"
version = "1.0.0"
author = "Example Author"
description = "A focused example mod."
code = "example_mod"
```

The repository verifier enforces only the manifest rules described above. Do
not infer behavior for additional keys from their presence in an example.

## Code mod build

Use the shared helper from `src/common/mod_cmake/rexmod.cmake`:

```cmake
cmake_minimum_required(VERSION 3.25)
project(example_mod LANGUAGES CXX)

include("${CMAKE_CURRENT_LIST_DIR}/../common/mod_cmake/rexmod.cmake")

rexmod_add_plugin(example_mod mod_main.cpp)
```

`rexmod_add_plugin` creates a shared library, requires C++23, links
`rex::runtime`, and adds `src/common/api/` to the private include path.

The title API mirror must match the public headers byte for byte at the commit
in `rerevved-api.lock.json`. Build native plugins with the SDK repository,
commit, and version recorded in `rexglue-sdk.lock.json`.

Unique Unit (UU) scalar rules are registered through `unique_unit_rules.h`.
Use a stable lowercase provider ID owned by the mod author. Treat each provider
and rule ID pair as immutable for the process lifetime. Rules normally load
before starting a game; the title does not restrict mid-game registration.
Base attack and defense rules compose before the title applies civilization,
era, unit, army, and earned combat modifiers.

`Cataphracts Test` is the permanent minimal reference for this API. Its
deliberately conspicuous attack value of 50 is a test baseline, not a balance
recommendation.

## Build and package

For selected code mods, the build script selects the detected native host
target and requires the matching SDK tree. Native Windows, Linux, and macOS
hosts are supported on x64 and ARM64. Optionally select one or more mods:

```text
python scripts/build_mods.py --sdk-dir <sdk> --mod <name>
```

The script configures and builds code mods, assembles selected mods under
`mods/<name>/`, and places a code mod binary under its generated target
subdirectory. It can also assemble asset mod source directories, but this does
not establish runtime asset loading support. Add `--package` to create
`pkg/<name>.zip` with `<name>/` as its archive root:

```text
python scripts/build_mods.py --sdk-dir <sdk> --mod <name> --package
```

Generated target labels describe where this build script assembled output.
Windows uses `.dll`, Linux uses `.so`, and macOS uses `.dylib` plugins under the
matching `code/<platform>/` directory.

Check manifests, lock files, tracked-file hygiene, whitespace, and C/C++
formatting with:

```text
python scripts/verify.py
```

Provide the locked title checkout and SDK tree to also check the title mirror,
build and package the discovered mods, and inspect the archives:

```text
python scripts/verify.py --title-dir <rerevved> --sdk-dir <sdk>
```

Build and package success does not prove runtime behavior. Runtime claims also
require applicable title evidence and regression testing.
