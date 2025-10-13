## [Unreleased]

### Added
- change: apply gitignore-style pattern semantics (including `**`) for all exclude lists

### Changed
- refactor summary builders to share a dataclass context and guard JSON emission flow

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
