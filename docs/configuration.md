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

Ignore rules cover both tree visibility and content capture. Use `exclude_tree` to hide files from the rendered tree, and `exclude_print` to control whether contents of included files are captured. The configuration loader also accepts `exclude_content` as an alias for `exclude_print`, but existing configs continue to write `exclude_print` as the canonical key.

## Output controls

Payloads and summaries are configured separately. Set defaults in the `[output]` table of `.grobl.toml` to control formats:

```toml
[output]
payload_format = "markdown"
summary_format = "auto"

`summary_format` accepts `auto`, `table`, `json`, or `none`; `auto` is the default behavior that prints a table when stdout is a TTY and suppresses output otherwise.
```

Destination flags (`--copy` / `--output`) always override configuration file settings, so you can send payloads to the clipboard, stdout, or a file per invocation.
