## [Unreleased]

### Added
- change: apply gitignore-style pattern semantics (including `**`) for all exclude lists

### Changed
- nothing yet

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
