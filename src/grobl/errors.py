ERROR_MSG_EMPTY_PATHS = "The list of paths is empty"
ERROR_MSG_NO_COMMON_ANCESTOR = "No common ancestor found"


class PathNotFoundError(Exception):
    """Raised when no common ancestor can be found."""


class ConfigLoadError(Exception):
    """Raised when a configuration file cannot be loaded."""
