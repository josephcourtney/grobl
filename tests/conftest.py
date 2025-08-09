import sys
from pathlib import Path

import pytest

from grobl.clipboard import (
    ClipboardInterface,
)
from grobl.config import (
    DOTIGNORE_CONFIG,
)

# Add the project root directory to the sys.path
sys.path.append(str(Path(__file__).parent.parent / "grobl"))


@pytest.fixture
def mock_clipboard():
    class MockClipboard(ClipboardInterface):
        def __init__(self):
            self.copied_content = None

        def copy(self, content: str) -> None:
            self.copied_content = content

    return MockClipboard()


@pytest.fixture
def temp_directory(tmp_path):
    project_dir = tmp_path / "project"
    project_dir.mkdir()

    # Create src with Python files
    src = project_dir / "src"
    src.mkdir()
    (src / "main.py").write_text("def main():\n    pass\n", encoding="utf-8")
    (src / "utils.py").write_text("def util():\n    return True\n", encoding="utf-8")

    # Create tests folder
    tests_dir = project_dir / "tests"
    tests_dir.mkdir()
    (tests_dir / "test_main.py").write_text(
        "def test_main():\n    assert True\n", encoding="utf-8"
    )

    # Add a .groblignore
    (project_dir / DOTIGNORE_CONFIG).write_text(
        "*.pyc\n__pycache__/\n", encoding="utf-8"
    )

    return project_dir
