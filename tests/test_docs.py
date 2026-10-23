"""The user documentation builds with no warnings, executing every tutorial.

The tutorials and the results page are notebooks run against the real engine and the
committed study records during the build (``nb_execution_mode = "force"``), so a code
change that breaks an example, a renamed port, or a missing reference fails here, the same
way it would fail ``make docs``. About a minute of build time.

The Read the Docs build (``READTHEDOCS=True``) can't use Pulse, so it publishes the tutorials
as code only; ``test_hosted_build_needs_no_engine`` builds it that way with Pulse unreachable.
"""

import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]


def _build(out: Path, env: dict | None = None) -> None:
    pytest.importorskip("sphinx", reason="install the docs group: uv pip install --group docs")
    result = subprocess.run(
        [sys.executable, "-m", "sphinx", "-W", "--keep-going", "-b", "html",
         str(ROOT / "documentation"), str(out)],
        capture_output=True, text=True, cwd=ROOT, timeout=600, env=env,
    )
    assert result.returncode == 0, result.stderr[-4000:]


def test_docs_build_without_warnings(tmp_path):
    """Falsifies: a tutorial cell raises, a cross-reference or image is broken, or a docstring
    the API pages render has invalid markup (``-W`` turns every warning into a failure)."""
    out = tmp_path / "html"
    _build(out)
    for page in ("index", "tutorials/01-hemorrhage-and-resuscitation", "results/pulse-hemorrhage",
                 "concepts/composites", "api/composites"):
        assert (out / f"{page}.html").is_file(), page
    shutil.rmtree(out)


def test_hosted_build_needs_no_engine(tmp_path):
    """Falsifies: the Read the Docs build executes a page that needs Pulse (with
    ``PULSE_INSTALL_DIR`` pointing nowhere, any engine load raises ``PulseNotFoundError``
    and fails the build), or the hosted pages lose the note that the tutorials show code only."""
    out = tmp_path / "html"
    env = {**os.environ, "READTHEDOCS": "True", "PULSE_INSTALL_DIR": str(tmp_path / "no-pulse")}
    _build(out, env)
    tutorial = (out / "tutorials/01-hemorrhage-and-resuscitation.html").read_text()
    assert "show their code without its output" in tutorial
    assert "show their code without its output" in (out / "index.html").read_text()
    assert "cell_output" not in tutorial  # published as code only
    results = (out / "results/pulse-hemorrhage.html").read_text()
    assert "cell_output" in results  # pages without the engine still execute
    shutil.rmtree(out)
