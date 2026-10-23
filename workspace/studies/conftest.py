"""Shared fixture for the study tests run by the workbench (POST /api/study-tests-run).

Each study's runs.db holds one ``runs_meta`` row per run, labelled with the
baseline or variant name it was launched as. ``latest`` maps every label to a
``vivarium_workbench.testing.Run`` for its most recent completed run.
"""

import sqlite3
from pathlib import Path

import pytest
from vivarium_workbench.testing import Run, RunNotAvailableError


def _study_dir(path: Path) -> Path:
    for parent in path.resolve().parents:
        if (parent / "study.yaml").is_file():
            return parent
    raise RunNotAvailableError(f"no study.yaml above {path}")


@pytest.fixture(scope="module")
def latest(request) -> dict[str, Run]:
    db = _study_dir(Path(request.fspath)) / "runs.db"
    if not db.is_file():
        raise RunNotAvailableError(f"runs.db not found at {db}")
    with sqlite3.connect(db) as conn:
        rows = conn.execute(
            "SELECT label, run_id FROM runs_meta WHERE status = 'completed' "
            "ORDER BY started_at ASC, run_id ASC"
        ).fetchall()
    # Later rows overwrite earlier ones, so each label keeps its latest run.
    return {label: Run(db, run_id) for label, run_id in rows}
