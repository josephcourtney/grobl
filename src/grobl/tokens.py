"""Token counting helpers."""

from __future__ import annotations

from pathlib import Path
from typing import Callable

import json

TOKEN_LIMIT_BYTES = 1_000_000


class TokenizerNotAvailableError(RuntimeError):
    """Raised when the tokenization dependency is not installed."""


def load_tokenizer(name: str) -> Callable[[str], int]:
    """Return a function that counts tokens for the given tokenizer name."""
    try:
        import tiktoken  # type: ignore
    except ModuleNotFoundError as exc:
        raise TokenizerNotAvailableError(
            "Token counting requires 'tiktoken'. Install with 'pip install grobl[tokens]'"
        ) from exc
    try:
        enc = tiktoken.get_encoding(name)
    except Exception as exc:
        available = ", ".join(sorted(tiktoken.list_encoding_names()))
        msg = (
            f"Unknown tokenizer '{name}'. Available models: {available}. "
            "Use --list-token-models to see options."
        )
        raise ValueError(msg) from exc
    return lambda text: len(enc.encode(text))


def load_cache(path: Path) -> dict[str, dict[str, int]]:
    """Load the token cache from disk."""
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except OSError:
        return {}
    except json.JSONDecodeError:
        return {}


def save_cache(cache: dict[str, dict[str, int]], path: Path) -> None:
    """Persist the token cache to disk."""
    try:
        path.write_text(json.dumps(cache, indent=2, sort_keys=True), encoding="utf-8")
    except OSError:
        pass


def count_tokens(
    text: str,
    file_path: Path,
    tokenizer: Callable[[str], int],
    cache: dict[str, dict[str, int]],
    *,
    force: bool,
    warn: Callable[[str], None] = print,
) -> int:
    """Count tokens for ``text`` using ``tokenizer`` with caching."""
    stat = file_path.stat()
    key = str(file_path)
    size = stat.st_size
    mtime = int(stat.st_mtime)
    entry = cache.get(key)
    if (
        entry
        and entry.get("size") == size
        and entry.get("mtime") == mtime
        and not force
    ):
        return entry["tokens"]
    if not force and size > TOKEN_LIMIT_BYTES:
        warn(
            f"Skipping tokenization for {file_path} ({size} bytes). Use --force-tokens to override."
        )
        tokens = 0
    else:
        tokens = tokenizer(text)
    cache[key] = {"size": size, "mtime": mtime, "tokens": tokens}
    return tokens
