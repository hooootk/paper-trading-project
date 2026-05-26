"""Clean script — remove build artifacts and cache files."""

import shutil
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

DIRS_TO_CLEAN = [
    "__pycache__",
    ".pytest_cache",
    ".mypy_cache",
    "dist",
    "build",
    "*.egg-info",
]


def clean() -> None:
    """Remove build artifacts and cache directories."""
    for pattern in DIRS_TO_CLEAN:
        for path in ROOT.glob(f"**/{pattern}"):
            if path.is_dir():
                shutil.rmtree(path)
                print(f"Removed: {path.relative_to(ROOT)}")
            elif "*" not in pattern:
                shutil.rmtree(path, ignore_errors=True)
    print("Clean complete.")


if __name__ == "__main__":
    clean()
