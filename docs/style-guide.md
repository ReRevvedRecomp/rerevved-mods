# Style guide

The [pull request rules](development.md#pull-requests) own repository
boundaries, licensing, branches, and commit subjects. The
[authoring guide](making-mods.md) owns package layout and manifests;
[Development](development.md) owns tool setup and check commands.

## Lua

- Keep scripts declarative and focused on the domains in their manifests.
  Guest semantics belong in the title; shared runtime facilities belong in
  the SDK.
- Use four spaces, single quotes, Allman table braces, and LF endings. Run the
  [pinned formatter](development.md#lua-formatter).
- Use descriptive kebab-case package IDs and `lower_snake_case` Lua locals.
- Keep editable amounts in named local values. Derive display text from the
  same value where practical; maintain separately authored text after a
  gameplay edit.
- Keep provider and rule identities stable. Changing them is not formatting.
- Do not add a configuration layer or helper framework for one small package
  without a concrete caller need.

## Python and manifests

Use four spaces, `snake_case` functions and variables, and `UPPER_SNAKE_CASE`
constants. Follow the standard-library scripts and `unittest` tests already
in the repository. Keep filesystem effects explicit and paths bounded.

Ruff is pinned in `tools/requirements-dev.txt`; its configuration targets
Python 3.11 and uses an 88-character line length. For local fixes:

```text
python -m ruff check --fix tools tests
python -m ruff format tools tests
```

Use the [development checks](development.md#checks-and-tests) afterward.
Preserve manifest keys, meaningful field order, package identities, and literal
test fixtures. Runtime metadata is product data, not disposable commentary.
Keep source files, build output, and retail inputs out of runtime packages.

## Comments and prose

Write plain ASCII, short paragraphs, and direct sentences. Wrap prose at about
80 columns; keep lines under 100 columns except tables, URLs, and code. Use
exact API names, UI labels, commands, and paths.

Put a short field-specific comment beside its field; put a shared explanation
above its group. Explain constraints, ownership, platform differences, or
non-obvious decisions rather than restating code. Put long contracts in their
owning guide and link to them instead of duplicating them.

Preserve source citations and license notices, including packaged metadata.
Keep private paths and session records out of public files. See
[Comments and prose](ai_agents/comments-and-prose.md) for the editing checklist
and [Evidence and claims](ai_agents/evidence-and-claims.md) for verification
boundaries.
