# Changelog

All notable changes to this project will be documented in this file.

## [0.4.14] - 2025-08-10

### Added
- reimplement CLI with click
- add `--mode` and `--table` options

## [0.4.13] - 2025-08-10

### Added
- add subcommand-based CLI with default `scan`
- add global `--version` flag and `version` subcommand
- add stackable `-v/--verbose` and `--log-level` options

### Changed
- reorganize CLI around subparsers

## [0.4.12] - 2025-08-10

### Added
- add usability review document

### Fixed
- fix type checking for tiktoken model mapping

## [0.4.10] - 2025-08-10

### Added
- add internal model specifications with tokenizers and budget tiers
- allow configuring default CLI options

### Removed
- remove implicit support for .groblignore and .grobl.config.json

### Fixed
- fix summary table header alignment and wording

## [0.4.11] - 2025-08-10

### Added
- add `init-config` subcommand to write default configuration
- add aliases for common model names

### Changed
- hide tokenizer name from summary title
- infer token budget when model or tier provides limits
- improve type annotations and docstrings across modules

### Fixed
- fix summary table column alignment

## [0.4.9] - 2025-08-09

### Added
- allow selecting model to infer tokenizer and token budget
- display token budget size and percentage in summary output
- list models for each tokenizer in model listing

### Changed
- set default tokenizer to `o200k_base`
- improve summary header alignment and clarify inclusion column

## [0.4.8] - 2025-08-09

### Added
- add path groups to configuration for bulk include or exclude
- add CLI flag to list available tiktoken models
- include tokenizer details in verbose output
- add column header indicating whether file contents are included

### Changed
- emit `<directory>` tag with full path attributes in LLM output

### Fixed
- improve error message for unknown tokenizer models

## [0.4.7] - 2025-08-09

### Added
- add optional token counting with `--tokens` flag

## [0.4.6] - 2025-08-09

### Added
- add interactive configuration editor and temporary in-memory adjustments
