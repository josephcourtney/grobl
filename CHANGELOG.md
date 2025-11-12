## [Unreleased]

### Added
- add new CLI enum definitions (`ContentScope`, `PayloadFormat`, `PayloadSink`) and extend summary format options

### Changed
- route bare `grobl` invocations through the `scan` command using Click's default dispatch

## [1.0.3] - 2025-10-20

### Fixed
- raise a config load error when an explicit --config path does not exist

## [0.7.4] - 2025-10-19

### Fixed
- fix scan traversal to accept single-file inputs without raising directory errors

=======

## [0.7.3] - 2025-10-18

### Added
- change: apply gitignore-style pattern semantics (including `**`) for all exclude lists
- add file handling strategy registry and template-based handlers for text and binary files
- add structured logging helpers and emit scan lifecycle events
- add property-based regression for runtime ignore merging logic

### Changed
- refactor summary builders to share a dataclass context and guard JSON emission flow
- refactor scan execution to inject dependencies and collapse message chains
- refactor output writer creation into a factory-driven strategy chain with graceful clipboard fallback
- enforce scan input validation and capture traversal timing metrics

### Fixed
- guard clipboard copies with bounded retries and timeout logging

## [0.7.2] - 2025-10-13

### Added
- add regression test ensuring JSON payload emission respects requested format

### Changed
- replace summary format string flags with a SummaryFormat enum across CLI and services
- make scan option and result dataclasses immutable to prevent accidental mutation

### Fixed
- fix clipboard fallback by importing contextlib in the output strategy composer

## [0.7.1] - 2025-08-28

### Fixed
- append trailing slashes to directory entries in tree output for clarity
- restore zsh completion snippet to use `eval "$(env _GROBL_COMPLETE=zsh_source grobl)"`
- update bundled default config to exclude `.grobl.config.toml` instead of `.grobl.toml`

### Documentation
- clarify shell completion setup in the README and add an end-to-end workflow overview

## [0.6.0] - 2025-08-28

### Added
- add `completions` subcommand to generate shell completion scripts (bash/zsh/fish)
- document configuration precedence, heavy-dir warnings, exit codes, payload format, and usage in README

### Changed
- centralize TTY detection and clipboard decisions in `grobl.tty`
- refine exit codes for path/config/usage errors and interrupt handling
## [0.7.0] - 2025-08-28

### Added
- add `--format json` pretty-printed summary with deterministic keys
- add binary file details to JSON summary (size; image width/height where available)
- add tests for JSON summary schema and binary details

### Changed
- change `grobl init` to write the default config preserving human-friendly formatting
