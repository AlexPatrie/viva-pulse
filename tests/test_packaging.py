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


def test_wheel_declares_the_license_it_ships(tmp_path):
    """Falsifies: the package metadata names a different license than the LICENSE file it
    ships. Regression: pyproject declared MIT while the repo was published as Apache 2.0."""
    import zipfile

    uv = shutil.which("uv")
    assert uv, "uv is required to develop viva-pulse (see README.md)"
    result = subprocess.run([uv, "build", "--wheel", "-o", str(tmp_path), str(ROOT)],
                            capture_output=True, text=True, timeout=300)
    assert result.returncode == 0, result.stderr
    (wheel,) = tmp_path.glob("*.whl")
    with zipfile.ZipFile(wheel) as zf:
        names = zf.namelist()
        metadata = zf.read(next(n for n in names if n.endswith(".dist-info/METADATA"))).decode()
        shipped = zf.read(next(n for n in names if n.endswith(".dist-info/licenses/LICENSE"))).decode()
    assert "License-Expression: Apache-2.0" in metadata.splitlines()
    assert "Apache License" in shipped and "Version 2.0, January 2004" in shipped
    assert shipped == (ROOT / "LICENSE").read_text()
