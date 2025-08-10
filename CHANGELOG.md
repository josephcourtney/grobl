# Changelog

All notable changes to this project will be documented in this file.

## [0.4.10] - 2025-08-10

### Added
- add internal model specifications with tokenizers and budget tiers
- allow configuring default CLI options

### Removed
- remove implicit support for .groblignore and .grobl.config.json

### Fixed
- fix summary table header alignment and wording

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
