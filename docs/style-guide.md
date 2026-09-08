# Style guide

This guide covers native plugins, package tooling, and authored documentation.
The [contribution contract](../CONTRIBUTING.md) owns repository boundaries;
[Making ReRevved mods](making-mods.md) owns API use, package layout, and build
commands. Keep those contracts authoritative when changing implementation style.

## Plugin structure

- Keep each plugin focused on its advertised behavior. Guest semantics belong
  in the title API and reusable runtime facilities belong in the SDK.
- Put package source under `src/<package-id>/`. Use the shared
  [CMake helper](../src/common/mod_cmake/rexmod.cmake) instead of copying its
  build setup into each plugin.
- Resolve host functions and check their ABI versions before use. Keep
  registration and lifecycle ordering explicit.
- Do not introduce registries, configuration layers, or helper frameworks for
  a single small plugin without a concrete caller need.

## C++

The shared plugin build selects C++23. Use
[`.clang-format`](../.clang-format) with clang-format 22 for authored C++.
Keep the guide and formatter consistent when changing a formatting rule.

- Use Allman braces, four spaces, no tabs, and braced control-flow bodies.
- Use `Type* pointer`, `const Type* pointer`, and `Type& reference`.
- Use `UpperCamelCase` for types, scoped enum values, and namespaced functions;
  `lowerCamelCase` for variables, parameters, fields, and private helpers; and
  `k` followed by `UpperCamelCase` for internal constants, such as
  `kProviderId`. Plain enum values use
  `UPPER_SNAKE_CASE`.
- Use namespaces and descriptive internal names instead of repeating the
  product name. Scoped enum values do not repeat their enum's name.
  Preserve SDK overrides, plugin entry points, and the feature-scoped names of
  the public title API. Public title C names have no mandatory product prefix;
  do not add aliases solely to reintroduce one.
- Keep one statement per line. Use early returns for unavailable host APIs or
  rejected registrations where the existing lifecycle contract requires them.
- Align consecutive declarations, assignments, enum values, macros, and
  trailing comments with the formatter. Declaration alignment also applies
  to parameter names in multiline function-pointer declarations.
- There is no fixed column limit. Wrap long declarations at meaningful
  boundaries, using one parameter per line when multiline.
- Include direct dependencies and keep private helpers in the implementation.
  Use explicit types when width, signedness, or ownership would otherwise be
  unclear. Keep platform-specific symbol resolution at the host API boundary.
- Use `static_cast` for intentional value conversions and `dynamic_cast` for
  checked downcasts of polymorphic C++ objects. Avoid C-style casts. Exceptions
  must not escape a C ABI boundary.

Use descriptive kebab-case package IDs and `lower_snake_case` CMake targets,
as in `keshik-movement` and `keshik_movement`. Provider IDs and rule IDs are
part of registration identity; changing them is not a formatting operation.

## Mirrored headers

`src/common/api/` is an exact mirror of the pinned title's public headers.
Apply header changes in the title first, then copy them and update
[`rerevved-api.lock.json`](../rerevved-api.lock.json). Do not independently
reformat mirrored headers. Preserve their LF checkout rules in
[`.gitattributes`](../.gitattributes).

The [SDK lock](../rexglue-sdk.lock.json) records the dependency contract.
Do not edit installed SDK or generated package files as source changes.

## Comments and documentation

Put short comments about individual enum values, structure fields, and list
entries inline. Keep shared explanations above their group and longer
contracts in the relevant public header or owning guide. Comments should
explain API constraints, platform differences, ownership, or non-obvious
decisions rather than restate the code. Preserve source citations and license
notices, including in packaged metadata.

Use plain ASCII prose, short paragraphs, and exact names for APIs and package
paths. Link the canonical authoring guide instead of duplicating its package
or ABI contracts. Keep private paths and session records out of tracked files;
the [public contribution policy](ai_agents/README.md) defines the boundary.

## Python, CMake, and manifests

- Python uses four spaces, `snake_case` functions and variables, and
  `UPPER_SNAKE_CASE` constants. Follow the existing standard-library scripts
  and `unittest` tests; keep filesystem effects explicit and paths bounded.
- Keep CMake target-scoped and package CMake files thin. Shared build behavior
  belongs in the existing helper when multiple plugins need it.
- Keep TOML manifest keys, package IDs, and archive paths consistent with the
  authoring guide and validators. Preserve meaningful order and literal test
  fixtures. Runtime metadata is product data, not disposable commentary.
- Assembly and archive contents must remain reproducible. Do not mix source,
  build output, or private retail inputs into runtime packages.

## Verification

Run `python scripts/verify.py` from the repository root. It checks authored
plugin C++ formatting and runs the focused Python tests. Mirrored API headers
are excluded from formatting; use `--title-dir <title-checkout>` to check their
exact bytes against the pinned title. The title checkout must match the lock.

Use the build and package commands in the authoring guide for changed native
plugins or packaging behavior. Tests should exercise observable registration,
validation, and archive contracts. Formatting-only edits should retain code
tokens, API layouts, package identity, and all source citations. Run
`git diff --check` and inspect the complete diff before committing.
