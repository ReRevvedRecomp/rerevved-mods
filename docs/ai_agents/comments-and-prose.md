# Comments and prose

The [style guide](../style-guide.md#comments-and-prose) owns prose conventions.
Use this checklist when editing documentation or comments:

- State current behavior, not development history, migration stories, planned
  features, or the process used to write the text.
- Give each fact one home. Link to the title's gameplay contract instead of
  maintaining a second list of accepted selectors here.
- Keep player tasks separate from instructions for package authors and
  explanations of runtime internals.
  Use exact F2 labels and explain when a restart is needed.
- Verify commands, paths, flags, and output against the scripts that implement
  them. Distinguish checks that write packages from read-only checks.
- Keep comments that explain a non-obvious constraint. Do not churn correct
  comments just to shorten them; correct factual errors with source evidence.
- Preserve identifiers, numeric constants, hashes, citations, and license
  notices. Do not turn a wording edit into a metadata or behavior change.
- Keep public content free of private project names, machine paths, session
  records, and claims that unavailable resources can be accessed.

After restructuring, update the [index](../README.md), inbound links, and
anchors. Review the result once as a new player, once as a contributor, and
once as a maintainer. Check ASCII, trailing whitespace, and line wrapping.
