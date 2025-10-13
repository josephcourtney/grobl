## P4 — Design & architecture (apply pragmatically with YAGNI)

* [ ] Enforce **Single Responsibility** where classes/modules span multiple concerns.
* [ ] Use **Dependency Inversion/Injection** for I/O, clock, configuration, and output sinks (protocols + constructor injection).
* [ ] Introduce **Strategy** only where real variation exists now (e.g., formatter selection); avoid speculative abstraction.
* [ ] Consider **Factory** for constructing related objects (e.g., output sinks) without leaking creation logic.
* [ ] Apply **Template Method** where a workflow is fixed and steps vary by subtype.
* [ ] Ensure **Open/Closed**: extend via registration/composition, not by editing existing code paths.
* [ ] Check **Liskov** and **Interface Segregation** when introducing/adjusting interfaces.

## P5 — Code quality & consistency

* [ ] Prefer **keyword arguments**; order consistently (inputs → options → dependencies).
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
