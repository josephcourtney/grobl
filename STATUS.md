# Status

Last updated: 2026-01-11

## Highlights

- Completed the ignore UX overhaul with explainable decisions and dual tree/content handling, including provenance tracking and the new describe helpers.
- Added intuitive scoped `--exclude`/`--include` CLI flags (plus file-target variants) while deprecating the legacy `--add-ignore`/`--remove-ignore`/`--unignore`/`--ignore-file` flags.
- Updated documentation (README, SPEC, usage guide, configuration notes) to describe the tree vs content model, explain new options, and note the legacy removal timeline; runtime tests and helpers were refreshed accordingly.
