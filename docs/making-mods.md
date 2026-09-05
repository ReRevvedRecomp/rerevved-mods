# Making ReRevved mods

This guide covers the supported source layout, manifest fields, and build and
package commands.

## Source layout

Put each native mod directly under `src/<id>/`. The directory name is the
package ID and must match the manifest ID. Package IDs use one to 63 lowercase
ASCII letters or digits separated by single hyphens, such as
`roman-cataphracts-defense`.

- A native mod has `src/<id>/CMakeLists.txt`, `mod.toml`, and its C++ sources.
- `src/common/` is reserved for shared helpers and the mirrored title API.

The CMake project and target may keep an underscore stem when the native binary
uses one, so `roman-cataphracts-defense` can build
`roman_cataphracts_defense.dll`.

List the discovered package IDs with:

```text
python scripts/build_mods.py --list
```

## Manifest

Every package uses manifest version 1 and a `[mod]` table. The required fields
are `id`, nonempty display `name`, strict numeric `version`, native `code`, and
`plugin_abi = 1`. `author`, `description`, and strict numeric
`min_game_version` are optional.

```toml
manifest_version = 1

[mod]
id = "roman-cataphracts-defense"
name = "Roman Cataphracts Defense"
version = "1.0"
author = "Aeshur"
description = "Roman Cataphracts gain +1 base Defense compared with ordinary Knights, reflecting their heavily armored cavalry theme."
code = "roman_cataphracts_defense"
plugin_abi = 1
```

Package versions require exactly two non-negative ASCII numeric components:
`major.minor`. Optional minimum game versions keep three non-negative ASCII
numeric components: `major.minor.patch`. The `code` value is one native
filename stem with no path component. Unknown version 1 fields produce
warnings and have no build or runtime meaning.

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
See the title's [Mod APIs guide](https://github.com/ReRevvedRecomp/rerevved/blob/main/docs/modding-api.md) for supported public interfaces and ownership boundaries.

Unique Unit (UU) scalar rules are registered through `unique_unit_rules.h`.
Use a stable lowercase provider ID owned by the mod author. Treat each provider
and rule ID pair as immutable for the process lifetime. Rules normally load
before starting a game; the title does not restrict mid-game registration.
Base attack and defense rules compose before the title applies civilization,
era, unit, army, and earned combat modifiers.

`Roman Cataphracts Defense` adds one point to the base Defense of Roman Knights
with the Cataphract identity. The rule is limited to that civilization, base
unit type, and identity, so ordinary Knights and other civilizations keep their
native values.

Unique Era Ability (UEA) replacements are registered through
`unique_era_abilities.h`. ABI 2 replaces one civilization and unlock-era cell
with another accepted UEA. Distinct cells compose. Multiple replacements for
the same cell leave that cell at its native UEA, independent of plugin order.
The API does not change Unique Abilities or exact-era lookup mode. Mods may use
the title-owned Knowledge of Horseback Riding synthetic UEA, which grants
technology ID 4 through the normal turn-advance technology path and suppresses
the displaced Mongolian village-conversion effect at its native gate. Mods
cannot define synthetic IDs or select a different technology.

`Mongol Horseback Riding` is the permanent minimal reference for the synthetic
UEA. It replaces the Mongolian Ancient UEA, Captured Barbarian villages become
cities, with Knowledge of Horseback Riding. Test it in a fresh game. Once the
technology has been granted, its ordinary saved ownership persists after the
mod is disabled or removed.

`State Inspector` is an optional development tool that shows the read-only
gameplay state published by ReRevved. Keep it available when checking overlay
regressions.

## Build and package

For selected native packages, the build script selects the detected native host
target and requires the matching SDK tree. Native Windows, Linux, and macOS
hosts are supported on x64 and ARM64. Optionally select one or more package IDs:

```text
python scripts/build_mods.py --sdk-dir <sdk> --mod <id>
```

The script supports `--target` and `--config` (`Release`, `Debug`, or
`RelWithDebInfo`) for the native host. It configures CMake with both the SDK
prefix and its explicit `lib/cmake/rexglue` directory, then assembles a
runtime-only package under `mods/<id>/`:

```text
mods/<id>/
  mod.toml
  icon.png                         optional
  code/<runtime-platform>/<binary>
  LICENSE*                         optional
  README.md                        optional
```

The recognized runtime-platform names are `windows-x64`, `windows-arm64`,
`linux-x64`, `linux-arm64`, `macos-x64`, and `macos-arm64`. CMake preset names
such as `win-amd64` are SDK build targets, not package directory names.

Add `--package` to create `pkg/<id>.zip`. Archives have the same runtime-only
files rooted at `mods/<id>/`; source files, CMake files, object files, build
trees, and repository metadata are excluded.

```text
python scripts/build_mods.py --sdk-dir <sdk> --mod roman-cataphracts-defense --package
```

Generated target labels describe where this build script assembled output.
Windows uses `.dll`, Linux uses `.so`, and macOS uses `.dylib` plugins under the
matching `code/<runtime-platform>/` directory.

Check manifests, lock files, tracked-file hygiene, whitespace, C/C++ formatting,
and package archive layout with:

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
