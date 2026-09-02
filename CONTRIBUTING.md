# Contributing

ReRevved Mods accepts focused changes to its plugins, shared build support,
manifests, packaging, and public documentation. Contributions use the
[GNU General Public License version 3 only](LICENSE).

## Scope

- Keep guest behavior and the versioned title API in `rerevved`.
- Mirror public title headers exactly and update `rerevved-api.lock.json` in
  the same change.
- Build native plugins from the SDK repository, commit, and version recorded in
  `rexglue-sdk.lock.json`.
- Keep plugins focused on their UI and packaging. Put reusable runtime
  facilities in `rerevved-sdk`.
- Do not submit retail files, extracted assets, generated packages, build
  output, credentials, machine paths, or guest addresses.

## Making a change

Follow [Making ReRevved mods](docs/making-mods.md) for the source, manifest,
build, and package requirements.

If automated or AI assistance is used, follow the same rules. Read the
[automated and AI-assisted contribution policy](docs/ai_agents/README.md).
