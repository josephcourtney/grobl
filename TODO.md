## P0 — Immediate fixes (user-visible / correctness)

* [ ] Append trailing “/” to directory entries in the tree output (`src/grobl/directory.py`: `TreeCollector.add_dir`).
* [ ] Correct legacy filename/comment in default config: exclude `.grobl.config.toml` (not `.grobl.toml`) and fix the adjacent comment (`src/grobl/resources/default_config.toml`).

## P1 — Tests & release hygiene

* [ ] Add test: directories end with `/` in tree lines (`tests/test_tree_trailing_slash.py`).
* [ ] Extend completions test to cover zsh; assert it contains `eval "$(env _GROBL_COMPLETE=zsh_source grobl)"` (`tests/test_cli_features.py`).
* [ ] Resource regression test: bundled default config `exclude_tree` contains `.grobl.config.toml` and **not** `.grobl.toml` (new test).
* [ ] Update `CHANGELOG.md`: note trailing-slash change, zsh completions fix, and default-config correction; bump patch version in `pyproject.toml`.
* [ ] Review `README.md` completion instructions; ensure zsh uses `eval "$(env _GROBL_COMPLETE=zsh_source grobl)"`.

## P2 — Small refactors (low risk / tidy-ups)

* [ ] Centralize shell completion snippets in a small dictionary to reduce duplication/typos (`src/grobl/cli/completions.py`).
* [ ] Extract tree connector glyphs (`"└── "`, `"├── "`) into named constants in `src/grobl/directory.py`.

## P3 — Documentation quality

* [ ] Clarify each module’s **purpose** at the top via a brief docstring (1–2 sentences).
* [ ] Add a high-level **README** section explaining end-to-end flow (inputs → processing → outputs).
* [ ] Add **module/class/function docstrings** (purpose, params, returns, raises, examples as applicable).
* [ ] Add targeted **inline comments** for non-obvious logic (avoid narrating the obvious).

## P4 — Design & architecture (apply pragmatically with YAGNI)

* [ ] Enforce **Single Responsibility** where classes/modules span multiple concerns.
* [ ] Use **Dependency Inversion/Injection** for I/O, clock, configuration, and output sinks (protocols + constructor injection).
* [ ] Introduce **Strategy** only where real variation exists now (e.g., formatter selection); avoid speculative abstraction.
* [ ] Consider **Factory** for constructing related objects (e.g., output sinks) without leaking creation logic.
* [ ] Apply **Template Method** where a workflow is fixed and steps vary by subtype.
* [ ] Ensure **Open/Closed**: extend via registration/composition, not by editing existing code paths.
* [ ] Check **Liskov** and **Interface Segregation** when introducing/adjusting interfaces.

## P5 — Code quality & consistency

* [ ] Replace repeated parameter groups with **Parameter Objects** (`@dataclass`, `slots=True` where many instances).
* [ ] Prefer **keyword arguments**; order consistently (inputs → options → dependencies).
* [ ] Simplify conditionals with extracted predicates and guard clauses.
* [ ] Reduce **message chains** by introducing well-named locals/facades.
* [ ] DRY up duplicate logic via shared helpers/utilities.
* [ ] Remove unreachable code, unused functions/classes, and commented-out blocks.

## P6 — Types, style, and Python best practices

* [ ] Add **type annotations** across public functions and critical internals; run a type checker (`ty`, `mypy`, or `pyright`).
* [ ] Replace ad-hoc data carriers with **@dataclass** (use `frozen=True` where appropriate; `slots=True` for many instances).
* [ ] Use **pathlib.Path** everywhere instead of str paths.
* [ ] Avoid **mutable default arguments**; use `None` and set defaults inside.
* [ ] Use **context managers** for files/locks/network connections.
* [ ] Prefer stdlib/built-ins over new dependencies; remove unnecessary third-party libs.
* [ ] Replace magic strings/ints with **Enums** or typed sentinels.
* [ ] Prefer **immutable data** for shared state to avoid aliasing bugs.

## P7 — Logging, security, and reliability

* [ ] Introduce **structured logging** (level, event name/id, key/value context) and log once at the appropriate layer.
* [ ] Validate external inputs at boundaries; fail fast with clear messages.
* [ ] Avoid leaking secrets in logs; load secrets from env/secret manager.
* [ ] Wrap external calls with timeouts/retries; consider backoff/circuit-breaker patterns where relevant.

## P8 — Performance & concurrency (measure first)

* [ ] Identify hot paths; add basic timing to confirm real bottlenecks before optimizing.
* [ ] Prefer generators/iterators for streaming; use lazy loading for heavy resources.
* [ ] Consider `async` for I/O-bound work and multiprocessing/workers for CPU-bound tasks (only if justified by measurements).

## P9 — Testing depth & determinism

* [ ] Add **unit tests** for core logic and **golden-path** integration tests.
* [ ] Mock external dependencies via injected interfaces; avoid real network in unit tests.
* [ ] Add **property-based tests** where pure functions have rich input spaces.
* [ ] Ensure determinism (seed RNG, injectable clock); keep tests independent of system state/time.
