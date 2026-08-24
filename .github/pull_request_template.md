## Summary

<!-- Describe the problem, the focused change, and the user or contributor impact. Use "Closes #123" when applicable. -->

## Scope

<!-- Check every area changed by this pull request. -->

- [ ] Mod source, UI, or manifest
- [ ] Shared mod build or packaging support
- [ ] Mirrored public title API and lock
- [ ] SDK lock
- [ ] Documentation only

<!-- Link any required title, analysis, or SDK change. Guest semantics do not belong in this repository. -->

## Evidence and behavior

<!-- Cite title or analysis evidence for gameplay claims, or write "Not applicable". A build alone does not prove runtime behavior. -->

## Submission checklist

- [ ] I read `CONTRIBUTING.md` and can explain every submitted change.
- [ ] The change stays within this repository's plugin, build, manifest, package, or documentation scope.
- [ ] Mirrored title headers match the commit in `rerevved-api.lock.json` byte for byte.
- [ ] Native code builds against the exact commit and version in `rexglue-sdk.lock.json`.
- [ ] Changed C/C++ passes the repository clang-format check.
- [ ] The diff contains no generated packages, build output, credentials, machine paths, private material, retail files, or extracted assets.
- [ ] Behavior visible to users and compatibility impact are documented.
