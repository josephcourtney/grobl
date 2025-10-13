## P6 — Types, style, and Python best practices

* [ ] Add **type annotations** across public functions and critical internals; run a type checker (`ty`, `mypy`, or `pyright`).
* [ ] Replace ad-hoc data carriers with **@dataclass** (use `frozen=True` where appropriate; `slots=True` for many instances).
* [ ] Use **pathlib.Path** everywhere instead of str paths.
* [ ] Avoid **mutable default arguments**; use `None` and set defaults inside.
* [ ] Use **context managers** for files/locks/network connections.
* [ ] Prefer stdlib/built-ins over new dependencies; remove unnecessary third-party libs.

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

* [ ] Mock external dependencies via injected interfaces; avoid real network in unit tests.
* [ ] Add **property-based tests** where pure functions have rich input spaces.
* [ ] Ensure determinism (seed RNG, injectable clock); keep tests independent of system state/time.
