# Welcome to the grobl documentation

grobl is a command-line utility that condenses a directory into a concise context payload for large language models (LLMs). It scans paths, builds a directory tree, collects text file contents with metadata, and emits a well-structured payload while respecting ignore patterns.

## Why grobl?

* **Purpose-built payloads** – produce Markdown and JSON bundles that are ready to share with tooling or assistants.
* **Deterministic output** – identical inputs yield identical payloads so diffs stay small.
* **Smart filtering** – ignore rules and traversal controls help you share only the files that matter.

## Installation

The recommended installation method uses [`uv`](https://docs.astral.sh/uv/):

```bash
uv tool install grobl
```

After installation, the `grobl` executable is available in your `uv` tool environment.

## Getting started

Once installed you can copy a full project summary to your clipboard with a single command:

```bash
grobl
```

Running without subcommands defaults to `grobl scan .`. When stdout is a TTY the payload is copied to the clipboard and a human-friendly summary prints to the terminal.

Need an explicit output file instead?

```bash
grobl --output context.txt
```

This writes the payload to `context.txt` while still printing the summary to stdout.

For more workflows, continue to the [usage guide](usage.md).
