"""Packaging: the declared dependencies must be installable on every Python
version that ``requires-python`` admits.

Regression: ``requires-python = ">=3.10"`` together with ``bigraph-viz>=2.0.3``
(which requires Python >= 3.11) could not be resolved, so the v0.2.0 image build
(``uv sync`` in the Dockerfile) failed. This runs ``uv lock``, the same
resolution that ``uv sync`` performs, on a copy of pyproject.toml, so no lock
file is written into the repo. It queries the live package index.
"""

import shutil
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_dependencies_resolve_for_every_supported_python(tmp_path):
    """Falsifies: some Python version inside requires-python cannot install the
    declared dependencies (uv lock resolves every version in the range)."""
    uv = shutil.which("uv")
    assert uv, "uv is required to develop viva-pulse (see README.md)"
    shutil.copy(ROOT / "pyproject.toml", tmp_path / "pyproject.toml")
    result = subprocess.run([uv, "lock", "--project", str(tmp_path)],
                            capture_output=True, text=True, timeout=300)
    assert result.returncode == 0, result.stderr
