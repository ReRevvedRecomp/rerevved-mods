# Test authoring

A test earns its place by catching a defect that no cheaper check catches.
Use standard-library `unittest`. Keep fixtures small and expected values explicit.

## When to add a test

Add the narrowest test that fails for a demonstrated defect or an uncovered
branch. Examples include manifest rejection, archive roots, source byte limits,
optional file copying, bounded cleanup, and formatter failure handling.

Test output bytes when copying is the contract. Test preserved files when an
operation fails. Keep gameplay assertions in the title's tests or runtime
checks; package validation does not execute Lua or prove a rule works.

## When not to add a test

- Another test already reaches the same branch with the same assertions.
- Only the package ID or declared domain changes on the same packaging path.
- An earlier guard rejects the fixture before the intended check runs.
- Expected values come from the production constant or validator being tested.
  Use the documented 256 KiB limit as an independent boundary.
- The test only checks repository layout, public-file hygiene, or lock values.
  Keep those checks in [the verifier](../../scripts/verify.py). Tests of its
  rejection behavior should use small fixtures.

## Choose the cheapest fixture that proves the claim

Pick the first level that can expose the defect:

1. Literal dictionaries, bytes, or paths passed to `parse_manifest_data`,
   `validate_lua_source`, or `parse_asset_pack_data` in the
   [mod](../../scripts/build_mods.py) and
   [asset pack](../../scripts/build_asset_packs.py) tools.
2. One data test over authored manifests. Keep expected package IDs and domains
   independent, as in `LUA_PACKAGES` in
   [test_packaging.py](../../tests/test_packaging.py).
3. A small `TemporaryDirectory` tree for loading, discovery, or runtime checks.
   Use `write_source` and `write_runtime` in that module, or
   `AssetPackTests.write_source` in
   [test_asset_packs.py](../../tests/test_asset_packs.py).
4. A ZIP written with `ZipFile.writestr` for archive rejection. Parse the
   expected manifest directly; do not assemble a package to create bad input.
5. Assembly and packaging for copy behavior, archive layout, or output isolation.
   Mock external tools and keep every output under the temporary root.

## Products and matrices

Check every authored manifest in one data test. Use `subTest` to identify the
row. Assemble representative fixtures for distinct behavior, not every ID.

Keep Lua mods and asset packs separate: their parsers and archive validators
are separate implementations. Keep the same-ID coexistence case because it
checks that the two output roots do not overwrite each other.

Cover each mechanism once at its cheapest level, then keep a small integration
case showing that its caller invokes it. Retain separate disk and ZIP size
checks because each performs its own bounded read. Keep native filename and
binary signature checks distinct.

When reducing an integration matrix, name the lost combinations and retained
branches in the pull request. Keep the complete data check in the same change.

## Scaffolding

Reuse `LUA_MANIFEST`, `LUA_SOURCE`, `MANIFEST`, and the existing fixture
builders in the test modules above. Keep literal expectations independent of
production tables. Share repeated builders when another caller needs them;
do not instantiate another `TestCase` just to call its helper.

Use `unittest.mock` at the external boundary. The formatter tests patch
`ROOT`, `_platform_asset`, `_run_codeformat`, and network access in
[test_format_lua.py](../../tests/test_format_lua.py). Do not download a tool or
run CodeFormat to test wrapper control flow.

Give distinct failures separate test methods or named `subTest` rows. Make
the invalid field reach its intended validator. Preserve fixture literals
that express the contract.

## Commands and boundaries

Run `python -m unittest discover -s tests` from the repository root.
To select one module, add `-p test_format_lua.py`.
[Checks and tests](../development.md#checks-and-tests) owns the full commands.

Unit tests create temporary files and some assemble packages. The full
`python scripts/verify.py` run also writes generated packages; neither is a
read-only check. Follow the task's execution limits.

Assert the [Lua source contract](../making-mods.md#source-and-runtime-files)
and [asset pack contract](../asset-packs.md#source-layout-and-manifest) at the
appropriate boundary. Report package checks and gameplay observations
separately, following [Evidence and claims](evidence-and-claims.md).
