"""Package initialization for grobl."""

import contextlib
from importlib.metadata import PackageNotFoundError, version

__version__ = "0.0.0"
with contextlib.suppress(PackageNotFoundError):
    if __package__ is not None:
        __version__ = version(__package__)

__all__ = ["__version__"]
