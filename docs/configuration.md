# Configuration

grobl reads configuration from `.grobl.toml` files. The bundled defaults ship with the project and the `grobl init` command can write them to a target directory.

## Default configuration locations

1. `.grobl.toml` in the current working directory
2. `.grobl.toml` in ancestor directories
3. Legacy `.grobl.config.toml` files (merged when a modern config is not present)
4. Built-in defaults packaged with grobl

## Creating a configuration file

Run the `init` command to scaffold the default configuration:

```bash
grobl init --path .
```

Add `--force` to overwrite an existing file:

```bash
grobl init --path . --force
```

## Ignore rules

Ignore settings let you exclude files, directories, or glob patterns from the payload. Update the `[ignore]` table in `.grobl.toml` to fine-tune traversal. For example:

```toml
[ignore]
patterns = [
  "node_modules/",
  "*.pyc",
]
```

## Output controls

Payloads and summaries are configured separately. Set defaults in the `[output]` table of `.grobl.toml` to control formats and sinks:

```toml
[output]
payload_format = "markdown"
payload_sink = "clipboard"
summary_format = "human"
summary_sink = "stdout"
```

Command-line options always override configuration file settings, allowing ad-hoc adjustments without editing the file.
