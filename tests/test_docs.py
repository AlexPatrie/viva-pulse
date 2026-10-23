"""The user documentation builds with no warnings, executing every tutorial.

The tutorials and the results page are notebooks run against the real engine and the
committed study records during the build (``nb_execution_mode = "force"``), so a code
change that breaks an example, a renamed port, or a missing reference fails here, the same
way it would fail ``make docs``. About a minute of build time.
"""

import shutil
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]


def test_docs_build_without_warnings(tmp_path):
    """Falsifies: a tutorial cell raises, a cross-reference or image is broken, or a docstring
    the API pages render has invalid markup (``-W`` turns every warning into a failure)."""
    pytest.importorskip("sphinx", reason="install the docs group: uv pip install --group docs")
    out = tmp_path / "html"
    result = subprocess.run(
        [sys.executable, "-m", "sphinx", "-W", "--keep-going", "-b", "html",
         str(ROOT / "documentation"), str(out)],
        capture_output=True, text=True, cwd=ROOT, timeout=600,
    )
    assert result.returncode == 0, result.stderr[-4000:]
    for page in ("index", "tutorials/01-hemorrhage-and-resuscitation", "results/pulse-hemorrhage",
                 "concepts/composites", "api/composites"):
        assert (out / f"{page}.html").is_file(), page
    shutil.rmtree(out)
