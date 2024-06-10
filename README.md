# Grobl

**Grobl** is a command-line tool designed to generate and copy a complete code project file tree along with the contents of valid text files. It's particularly useful for sharing code projects in communication platforms.

## Features

- Generate a file tree for a given list of paths.
- Exclude specific files and directories from the tree display.
- Print contents of valid text files (source code, markdown, txt, etc.).
- Exclude specific files from printing their contents while still showing them in the tree.
- Parse settings from `pyproject.toml` files in the directory hierarchy.
- Copy the output to the clipboard for easy sharing.

## Installation

### Prerequisites

- Python 3.11 or later.
- `pipx` for isolated Python application installations.

### Install using `pipx`

To install `grobl`, use the following command:

```bash
pipx install grobl
```

If you don't have pipx installed, you can install it using:

```bash
python -m pip install --user pipx
python -m pipx ensurepath
```

## Usage

To use grobl, run the following command:

```bash
grobl <paths> [--exclude-tree <patterns>] [--exclude-print <patterns>]
```

Arguments
- `<paths>`: List of file paths to include in the tree.
- `--exclude-tree`: Patterns to exclude from the tree display.
- `--exclude-print`: Patterns to exclude from file printing.

Example

```bash
grobl ./snoop/apriquot ./snoop/weasel --exclude-tree "*.md" --exclude-print "*.css"
```

This command will:

- Generate the file tree for the specified paths.
- Exclude files matching *.md from the tree display.
- Exclude files matching *.css from being printed.
- Copy the final output to the clipboard.

## `pyproject.toml` Configuration

You can configure grobl using a pyproject.toml file in your directory hierarchy. The settings in this file will affect the directories containing them and override settings from ancestor directories.
Example pyproject.toml

```toml
[tool.file_tree_printer]
exclude_tree = ["*.jsonl", "*.jsonl.*", "tests/*", "cov.xml", "*.log", "*.tmp"]
exclude_print = ["*.json", "*.html"]
```

Configuration Details

- `exclude_tree`: A list of glob patterns to exclude from the file tree display. Files and directories matching these patterns will not appear in the tree structure.
- `exclude_print`: A list of glob patterns to exclude from file printing. Files matching these patterns will appear in the tree structure but their contents will not be printed.

### Example Configuration

Consider the following directory structure:

```
project-root/
│
├── pyproject.toml
├── src/
│   ├── main.py
│   ├── utils.py
│   └── config.json
├── tests/
│   ├── test_main.py
│   └── test_utils.py
└── README.md
```

With the following `pyproject.toml`:

```toml
[tool.file_tree_printer]
exclude_tree = ["tests/*", "*.json"]
exclude_print = ["*.md"]
```

Running `grobl project-root/` will:

1. Exclude the tests directory and config.json file from the tree display.
2. Exclude README.md from being printed.
3. Copy the output to the clipboard.

## Contributing

Contributions are welcome! Please feel free to submit a pull request or open an issue.
License

This project is licensed under the MIT License.
