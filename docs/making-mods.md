# Making ReRevved mods

This guide owns the Lua package layout and manifest rules. For commands and
checks, use [Development](development.md). For accepted gameplay fields and
selectors, use the title's
[Lua rules contract](https://github.com/ReRevvedRecomp/rerevved/blob/main/docs/modding-api.md#lua-rules-contract-1).
Do not copy guest addresses, layouts, or native state machines into a mod.

## Source layout

Put each mod directly under `mods/<id>/`. The directory name and `[mod].id`
must match. IDs use one to 63 lowercase ASCII letters or digits, with single
hyphens between groups, such as `hills-production`.

Each package contains `mod.toml` and one declared Lua entry file, normally
`main.lua`. All first-party packages use Lua. Independent asset overrides use
[a separate layout](asset-packs.md), not a Lua payload.

## Manifest

Use manifest version 2. The Hills Production manifest is a complete example:

```toml
manifest_version = 2

[mod]
id = "hills-production"
name = "Hills Production"
version = "1.0"
author = "Aeshur"
description = "Hills provide +1 base Production for every player."
min_game_version = "0.5.0"

[payload]
kind = "lua"
entry = "main.lua"
api = "rerevved.rules"
api_version = 1
requires = ["terrain_yield"]
```

Required `[mod]` fields are `id`, nonempty display `name`, and `version`.
`author`, `description`, and `min_game_version` are optional. Package versions
use exactly two non-negative ASCII numeric components, `major.minor`. A
minimum game version uses three: `major.minor.patch`. It refers to the
ReRevved application, not the retail title update or the package version.

Exactly one `[payload]` table is required, with all five fields shown above:

- `kind` must be `lua`.
- `entry` must name one `.lua` file directly inside the package directory.
  Separators, absolute paths, colons, control characters, Windows-reserved
  filename characters, and device names are rejected.
- `api` must be a nonempty string. These packages use `rerevved.rules`.
- `api_version` must be an integer from 1 through 4294967295, not a Boolean.
- `requires` must be a nonempty array of distinct domain names. Each name
  has 1 to 63 lowercase ASCII letters, digits, underscores, or hyphens.

Declare every domain the script can return, including conditional branches.
Declared but unused domains are allowed. The installed title must advertise
the requested API version and all declared domains; assembling a package does
not check an installed title's capabilities.

Unknown top-level and `[mod]` fields produce warnings in the package tooling.
Unknown `[payload]` fields are errors. Native `code` and `plugin_abi` fields
are rejected wherever they appear, and version 1 manifests are rejected by
this repository's Lua tooling. For native plugins, consult the SDK's
[mod-system documentation](https://github.com/ReRevvedRecomp/rerevved-sdk/blob/main/docs/mod-system.md).

## Lua declaration

The complete Hills Production entry is:

```lua
local production_bonus = 1

return
{
    provider_id = 'aeshur.hills-production',
    rules =
    {
        {
            id = 'hills-production',
            kind = 'terrain_yield',
            terrain = 'hill',
            component = 'production',
            operation = 'add',
            value = production_bonus,
        },
    },
}
```

Return one plain table containing `provider_id` and `rules`. The SDK evaluates
the entry once at launch; local functions, arithmetic, conditionals, and loops
can construct the declaration. Module imports and gameplay callbacks are not
available. The title validates, publishes, and executes the resulting rules.

Use the title's [Lua rules contract](https://github.com/ReRevvedRecomp/rerevved/blob/main/docs/modding-api.md#lua-rules-contract-1)
for the complete table shape, rule count, identity syntax, numeric bounds,
accepted fields and selectors, and failure diagnostics. A package publishes
all of its rules together or none of them. Array order does not override the
composition rules of the title's registries.

Provider and rule IDs are stable registration identities, not balance values.
Give a new independently authored package its own identities. For a local
variant, enable the variant instead of its original; renaming the folder alone
does not make duplicate providers safe to enable together. See
[Package customization](packages.md#editable-values) for first-party values.

## Source and runtime files

The entry must be ASCII, at most 256 KiB, with LF line endings and a final
newline. Tabs, trailing whitespace, UTF-8 BOMs, and Lua bytecode are rejected.
The tooling rejects links and reparse points.

The assembled runtime tree has this layout:

```text
out/mods/<id>/
  mod.toml
  main.lua       the declared entry; another safe filename is allowed
  icon.png       optional
  README.md      optional
  LICENSE*       optional existing license files
  assets/        optional mod-owned runtime files
```

Native source, native binaries, CMake files, `code/`, and root-level files
outside the listed layout are rejected. Executable signatures are checked even
when a binary is renamed. Files under `assets/` are runtime data, not
additional entry points; modules cannot be imported. Do not include
repository metadata or retail assets.

Each build writes the runtime tree and a ZIP rooted at `mods/<id>/`. See
[Build packages](development.md#build-packages) for commands and output paths.
After installation, use F2 to check compatibility, save the loadout, and
restart. Then verify the intended gameplay effect.

## Nation Select Text

A `nation_select_text` rule replaces a complete civilization information line,
not a fragment. Keep the line accurate when its gameplay rule changes. Derive
text from the same local value where practical. After changing Hoplite's cost,
edit its displayed Production cost and verify it in the title.

The title's [text surface contract](https://github.com/ReRevvedRecomp/rerevved/blob/main/docs/modding-api.md#lua-rules-contract-1)
defines the accepted surfaces, selectors, and text limits. Registration alone
does not guarantee visibility, and a visible description does not prove the
gameplay rule ran.

## Lua style and formatter

Use the [pinned formatter and Lua style](development.md#lua-formatter).

## Verification

Run the [development checks](development.md#checks-and-tests), then test
runtime behavior in a compatible title. Report those results separately.
