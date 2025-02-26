# grobl

grobl is a command-line utility for condensing a directory and its contents into a markdown string suitable for use with a large language model. It scans the current directory, builds a tree representation of all directories and files, while respecting ignore patterns, and then outputs both the tree structure and the file contents as a markdown-formatted string, copied to the clipboard.

---

## Purpose

- **Directory Visualization:** Quickly see a tree-like view of your project's directory structure.
- **Content Inspection:** Extract and display the contents of text files, complete with metadata such as line and character counts.
- **Customizable Filtering:** Exclude files and directories using ignore patterns (supports a default set along with custom entries from a `.groblignore` file).

---

## Features

- **Recursive Directory Traversal:** Scans all subdirectories starting from a common ancestor.
- **Markdown Escaping:** Automatically escapes Markdown characters to ensure proper formatting when copying the output.
- **Clipboard Integration:** Copies the final output directly to your clipboard.
- **Configurable Ignore Patterns:** Uses both default and custom ignore patterns (via `.groblignore`) to filter out unwanted files.
- **Detailed File Metadata:** Provides line and character counts for each file alongside the file's content.
- **Extensive Testing:** Comes with a comprehensive test suite using pytest to ensure reliability and correct behavior.

---

## Installation

### Using pipx

[pipx](https://pipxproject.github.io/pipx/) allows you to run Python applications in isolated environments. To install grobl via pipx, run:

```bash
pipx install grobl
```

After installation, you can use the `grobl` command from your terminal:

```bash
grobl
```

### Using uv tool

If you prefer to use the `uv` tool for managing and running Python projects, install grobl with:

```bash
uv install grobl
```

Then, run it using:

```bash
uv run grobl
```

---

## Usage

To generate and copy a directory structure along with file contents:

1. Open your terminal.
2. Navigate to the root directory of the project you want to inspect.
3. Run the `grobl` command:

   ```bash
   grobl
   ```

The output, which includes a directory tree and the contents of all text files, will be automatically copied to your clipboard. A summary including file metadata and overall counts will also be printed to the terminal.

---

## Configuration

### Ignore Patterns

grobl uses a set of default ignore patterns to exclude common directories and files (e.g., `.git/`, `node_modules/`, etc.). To customize this behavior, create a `.groblignore` file in the directory from which you run grobl. Each line in the file should contain a glob pattern for files or directories to ignore. For example:

```
*.pyc
__pycache__/
```

---

## Development & Testing

The project uses [pytest](https://docs.pytest.org/) for its test suite. To run the tests, simply execute:

```bash
pytest
```

This will run all tests in the `tests/` directory and provide feedback on functionality and coverage.
