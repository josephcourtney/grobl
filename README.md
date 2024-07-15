# grobl

`grobl` is a command-line utility designed to summarize the contents of a code project and copy it into the clipboard in markdown format. It is primarily useful for interacting with LLM-based code assistants. It generates a file tree structure and prints the contents of valid text files within specified directories. It automatically ignores typical computer-generated files like build directories, linter caches, etc. It has configuration options for excluding certain files or directories from the tree display and file printing.

## Features

- Generate a file tree structure for specified directories.
- Print contents of valid text files.
- Exclude files or directories from the tree display and file printing using patterns.
- Detect project types based on specific markers and apply corresponding exclusion patterns.
- Support for different output formats: plain text, JSON, and Markdown.
- Copy the final output to the clipboard.

## Installation

To install `grobl`, clone the repository and install the required dependencies:

```sh
git clone https://github.com/your-username/grobl.git
cd grobl
pip install -r requirements.txt
```

## Usage

To run `grobl` and generate a summary of your project, navigate to the root directory of your project and run the following command:

```sh
grobl
```

This will generate a file tree structure and print the contents of valid text files within the current directory and its subdirectories. You can also specify specific directories to include or exclude using the following options:

```sh
grobl --include dir1,dir2 --exclude dir3,dir4
```

## Configuration

`grobl` can be configured using a configuration file or command-line options. The configuration file should be named `grobl.conf` and placed in the root directory of your project. The file should contain a JSON object with the following properties:

- `include`: A list of directories to include in the file tree structure and file printing.
- `exclude`: A list of directories or files to exclude from the file tree structure and file printing.
- `output_format`: The output format for the summary. Valid values are `plain`, `json`, and `markdown`.

For example:

```json
{
  "include": [
    "src",
    "docs"
  ],
  "exclude": [
    "node_modules",
    "build"
  ],
  "output_format": "markdown"
}
```

You can also specify these options using command-line arguments:

```sh
grobl --include src,docs --exclude node_modules,build --output-format markdown
```

## Output

The output of `grobl` will depend on the specified output format. Here are some examples:

### Plain Text

```
File Tree:
src
  file1.txt
  file2.txt
docs
  README.md
  CHANGELOG.md

File Contents:
src/file1.txt:
This is the contents of file1.txt

src/file2.txt:
This is the contents of file2.txt

docs/README.md:
This is the contents of README.md

docs/CHANGELOG.md:
This is the contents of CHANGELOG.md
```

### JSON

```json
{
  "file_tree": {
    "src": [
      "file1.txt",
      "file2.txt"
    ],
    "docs": [
      "README.md",
      "CHANGELOG.md"
    ]
  },
  "file_contents": {
    "src/file1.txt": "This is the contents of file1.txt",
    "src/file2.txt": "This is the contents of file2.txt",
    "docs/README.md": "This is the contents of README.md",
    "docs/CHANGELOG.md": "This is the contents of CHANGELOG.md"
  }
}
```

### Markdown

```markdown
# File Tree

- src
  - file1.txt
  - file2.txt
- docs
  - README.md
  - CHANGELOG.md

# File Contents

## src/file1.txt

This is the contents of file1.txt

## src/file2.txt

This is the contents of file2.txt

## docs/README.md

This is the contents of README.md

## docs/CHANGELOG.md

This is the contents of CHANGELOG.md
```