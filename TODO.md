- [x] add an internal listing of models, correct tokenizers, and budgets by subscription tier
  - example: {'model': 'gpt-5', 'tokenizer': 'o200k_base', 'budget': {'free': 16000, 'plus': 32000, 'pro': 128000}} except stored as a toml file
- [x] remove implicit support for .groblignore and .grobl.config.json files. If they exist, inform the user and tell them that the files will be migrated to toml, then migrate them
- [x] add the ability to set default values for these command line options in the config files
  - `--no-clipboard`
  - `--tokens`
  - `--model`
  - `--budget`
  - `--force-tokens`
  - `--verbose`
- [x] fix summary table header and alignment. It currently looks like this:
```
═══════════════════ Project Summary (o200k_base) ═══════════════════
                                            lines chars tokens incl
bingbong
├── .gitignore                                  184  3536      0    *
├── .grobl.config.toml                           25   448    137
```

it should look like this:
```
═══════════════════ Project Summary (o200k_base) ═══════════════════
                                              lines chars tokens included
bingbong
├── .gitignore                                  184  3536      0        *
├── .grobl.config.toml                           25   448    137
```
