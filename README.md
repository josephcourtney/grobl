# grobl

grobl is a command-line utility for condensing a directory and its contents into a markdown string suitable for use with a large language model. It scans the current directory, builds a tree representation of all directories and files, while respecting ignore patterns, and then outputs both the tree structure and the file contents as a markdown-formatted string, copied to the clipboard.

---

## Purpose

- **Directory Visualization:** Quickly see a tree-like view of your project's directory structure.
- **Content Inspection:** Extract and display the contents of text files, complete with metadata such as line and character counts.
- **Customizable Filtering:** Exclude files and directories using ignore patterns

---

## Features

- **Recursive Directory Traversal:** Scans all subdirectories starting from a common ancestor.
- **Markdown Escaping:** Automatically escapes Markdown characters to ensure proper formatting when copying the output.
- **Clipboard Integration:** Copies the final output directly to your clipboard.
- **Detailed File Metadata:** Provides line and character counts for each file alongside the file's content.
