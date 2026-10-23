# Guidance for coding agents

Read these before changing the repository:

1. [Pull requests](../development.md#pull-requests): license, branch,
   commit, scope, and review requirements.
2. [Making mods](../making-mods.md): manifest and source contracts.
3. [Style guide](../style-guide.md): authored code and documentation style.
4. [Development](../development.md): tools, checks, and test boundaries.
5. [Comments and prose](comments-and-prose.md) and
   [Evidence and claims](evidence-and-claims.md): editing and verification.
6. [Test authoring](test-authoring.md): coverage, fixtures, and test scope.

Keep Lua packages declarative. Consume the public title API rather than
copying guest addresses, layouts, native headers, or state machines. Coordinate
intentional changes to compatibility locks; do not relax a lock to hide a mismatch.

Preserve unrelated work, source attribution, and license files. Do not add
retail content, extracted assets, generated packages, credentials,
machine-specific paths, private repository references, or session records.
