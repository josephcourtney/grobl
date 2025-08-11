"""Custom exception classes and error messages."""

ERROR_MSG_EMPTY_PATHS = "The list of paths is empty"
ERROR_MSG_NO_COMMON_ANCESTOR = "No common ancestor found"


class PathNotFoundError(Exception):
    """Raised when no common ancestor can be found."""


class ConfigLoadError(Exception):
    """Raised when a configuration file cannot be loaded."""


class ScanInterrupted(KeyboardInterrupt):
    """Raised when a scan is interrupted; carries partial state."""

    def __init__(self, builder, common):
        super().__init__("Scan interrupted")
        self.builder = builder
        self.common = common
