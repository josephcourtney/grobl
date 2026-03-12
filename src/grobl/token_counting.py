"""Token counting helpers backed by ``tiktoken``."""

from __future__ import annotations

from functools import lru_cache

import tiktoken

DEFAULT_TOKEN_MODEL = "gpt-5-"  # noqa: S105 - tokenizer model identifier, not a secret


@lru_cache(maxsize=8)
def _encoding_for_model(model: str) -> tiktoken.Encoding:
    return tiktoken.encoding_for_model(model)


def count_tokens(text: str, *, model: str = DEFAULT_TOKEN_MODEL) -> int:
    """Return the token count for ``text`` using the configured default model."""
    return len(_encoding_for_model(model).encode(text))
