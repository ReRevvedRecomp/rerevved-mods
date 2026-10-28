# Asset packs

Asset packs are separate from Lua mods. This repository provides generic
assembly and validation tools, but contains no `asset-packs/` source tree.
An absent source directory is a valid empty catalog. The title supplies its
own default logo pack.

## Source layout and manifest

Create `asset-packs/<id>/asset-pack.toml` and a nonempty `assets/` directory.
IDs use the same lowercase, hyphen-separated
[package ID grammar](making-mods.md#source-layout) as Lua mods. The directory
name must match the manifest ID.

A manifest has this form:

```toml
manifest_version = 1

[asset_pack]
id = "example-pack"
name = "Example Pack"
version = "1.0"
```

`id`, nonempty `name`, and `version` are required. `author` and `description`
are optional strings. The version uses exactly two non-negative ASCII numeric
components, `major.minor`. Unknown top-level or `[asset_pack]` fields produce
warnings in the package tooling.

Asset paths are relative to the package and use forward slashes. The tools
validate regular files and reject unsafe paths, links, and reparse points; they
do not validate a general archive format or define which files the title consumes.
Use only original or otherwise authorized assets, not extracted retail files.

## Build and check

Python 3.11 or newer is sufficient; no SDK or native build is required. Run
from the repository root:

```text
python tools/build_asset_packs.py --list
python tools/build_asset_packs.py --pack <id> --package
python tools/verify_asset_packs.py --package
```

Repeat `--pack` to select multiple packs, or omit it to build all discovered
packs. Unlike the Lua mod builder, the asset pack builder writes ZIP archives
only with `--package`.

```text
asset-packs/<id>/             source
  asset-pack.toml
  assets/                    at least one file

out/asset-overrides/<id>/     generated runtime tree
  asset-pack.toml
  assets/

out/pkg/asset-overrides/<id>.zip  archive rooted at asset-overrides/<id>/
```

Optional `icon.png`, `README.md`, and existing `LICENSE*` files are also copied
from the pack root. Keep source edits outside generated output: assembly
recreates each selected `out/asset-overrides/<id>/` folder.

Without `--package`, `verify_asset_packs.py` checks source manifests and asset
trees. With it, the script also checks the generated archives. It does not
assemble missing packages or prove that the title accepts the asset contents.

## Install and select

Close the title and back up any installed pack you intend to replace outside
the discovery root. Place the generated `<id>` folder under
`asset-overrides/` beside the executable, without merging it with an older
copy. The result must be `asset-overrides/<id>/asset-pack.toml`.

Use F2's **Asset Overrides** tab to manage selection and priority separately
from Lua mods. The title and SDK define runtime path matching and override
behavior; see the title's
[runtime integration guide](https://github.com/ReRevvedRecomp/rerevved/blob/main/docs/rexglue-runtime.md).
A successful archive check is not evidence that a particular asset is loaded.
