# Welcome to the grobl documentation

grobl is a command-line utility that condenses a directory into a concise context payload for large language models (LLMs). It scans paths, builds a directory tree, collects eligible text file contents with metadata, and emits a well-structured payload through an explainable three-state inclusion policy.

## Why grobl?

* **Purpose-built payloads** – produce Markdown and JSON bundles that are ready to share with tooling or assistants.
* **Deterministic output** – identical inputs yield identical payloads so diffs stay small.
* **Explainable inclusion** – `full`, `tree_only`, and `omit` states make it explicit which paths contribute structure or contents.

## Installation

The recommended installation method uses [`uv`](https://docs.astral.sh/uv/):

```bash
uv tool install grobl
```

After installation, the `grobl` executable is available in your `uv` tool environment.

## Getting started

Once installed you can copy a prompt-ready project context payload to your clipboard with a single command:

```bash
grobl
```

Running without subcommands defaults to `grobl scan .`. With no explicit payload destination, an interactive run (stdout is a TTY) copies the payload to the clipboard and reports the successful copy on stderr; when stdout is not a TTY, the payload is written to stdout instead.

Need an explicit output file instead?

```bash
grobl --output context.txt
```

This writes the payload to `context.txt` while the summary remains on stderr by default.

For more workflows, continue to the [usage guide](usage.md).
