- [ ] add a sub-command to place a default config in the current folder (or project root if a known project structure is recognized. ask for confirmation before placing the file anywhere but the CWD)
- [ ] make sure that all functions and methods in src/ have accurate, narrow type annotations
- [ ] replace conditionals and loops in tests with parameterization or other appropriate techniques
- [ ] identify functions that are too long or complex. if it makes sense, break them apart into smaller, more modular, reusable pieces
- [ ] make sure all methods, classes, and modules have high quality docstrings
- [ ] write tests to check for accurate alignment in summary table output. Currently, the output is poorly aligned:
```
═════════════ Project Summary (o200k_base) ═════════════
                            lines chars tokens included
nvim
├── .gitignore                    8    51     20
├
...
```
- [ ] do not show tokenizer model in summary title
- [ ] make aliases for common models like "gpt-5"
- [ ] if a model does not have separate subscription tiers, or the subscription tier is specified (e.g. `gpt-5:plus`), enable the `budget` option with the known token limit
