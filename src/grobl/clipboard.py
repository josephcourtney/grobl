import pyperclip


class ClipboardInterface:
    def copy(self, content: str) -> None:
        raise NotImplementedError


class PyperclipClipboard(ClipboardInterface):
    def copy(self, content: str) -> None:  # noqa: PLR6301
        pyperclip.copy(content)
