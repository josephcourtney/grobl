import pyperclip

from grobl.clipboard import PyperclipClipboard


def test_pyperclip_clipboard(monkeypatch):
    called = {}

    def fake_copy(content):
        called["content"] = content

    monkeypatch.setattr(pyperclip, "copy", fake_copy)

    clip = PyperclipClipboard()
    clip.copy("test content")

    assert called["content"] == "test content"
