# Evidence and claims

Use the narrowest evidence that answers the claim:

| Claim | Required evidence |
|---|---|
| A package declares a rule | Its `mod.toml` and Lua source. |
| A command accepts an option or writes a path | Its argument parser and implementation. |
| A package passes structural checks | The relevant validator result and exact source revision. |
| A title supports a contract | The title and SDK implementation at the tested revisions. |
| A rule changes gameplay | An applicable title test or an observed gameplay result. |
| A workflow runs or publishes an artifact | The workflow's triggers, commands, and upload steps. |

Keep declarations, validation, activation, and gameplay results separate. An
assembled ZIP, an active F2 row, a stateless preview, or visible descriptive
text does not establish that every gameplay path works. Do not infer online
correctness from a single-player observation.

[Compatibility locks](../development.md#compatibility-locks) record target
revisions; they are not proof that a test ran. `--title-dir` compares HEAD with
the title lock, and does not verify an SDK checkout or execute the game.

When reporting a change, name the files or tests supporting it, the checks
actually run, and any skipped or unavailable checks. Preserve negative
results and known limits. Do not claim builds, tests, downloads, or runtime
observations that were not performed. Follow task-specific restrictions;
`verify.py` and the unit tests can build packages, and tool installation can
use the network.
