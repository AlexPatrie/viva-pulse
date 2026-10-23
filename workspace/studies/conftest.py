"""Shared fixture for the study tests run by the workbench (POST /api/study-tests-run).

Each study's runs.db holds one ``runs_meta`` row per run, labelled with the
baseline or variant name it was launched as. ``latest`` maps every label to a
``vivarium_workbench.testing.Run`` for its most recent run, after checking that
the record can be trusted: that run completed, its parameters are the ones the
study declares for that label, every run comes from one commit, and no run hit
an irreversible state (after which Pulse is no longer advanced and the vitals
freeze while time still reaches the end).
"""

import json
import sqlite3
from pathlib import Path

import pytest
import yaml
from vivarium_workbench.testing import Run, RunNotAvailableError


def _study_dir(path: Path) -> Path:
    for parent in path.resolve().parents:
        if (parent / "study.yaml").is_file():
            return parent
    raise RunNotAvailableError(f"no study.yaml above {path}")


def _declared_params(spec: dict) -> dict[str, dict]:
    """The generator parameters each label runs with, resolved as the workbench does."""
    baseline = {entry["name"]: entry for entry in spec["baseline"]}
    params = {name: dict(entry.get("params") or {}) for name, entry in baseline.items()}
    for variant in spec.get("variants") or []:
        base = {} if variant.get("composite") else dict(baseline[variant["base_composite"]]["params"])
        params[variant["name"]] = {**base, **(variant.get("parameter_overrides") or {})}
    return params


@pytest.fixture(scope="module")
def latest(request) -> dict[str, Run]:
    study_dir = _study_dir(Path(request.fspath))
    db = study_dir / "runs.db"
    if not db.is_file() or db.stat().st_size == 0:
        raise RunNotAvailableError(f"runs.db not found at {db}")
    with sqlite3.connect(f"file:{db}?mode=ro", uri=True) as conn:
        rows = conn.execute(
            "SELECT label, run_id, status, params_json, manifest_json FROM runs_meta "
            "ORDER BY started_at ASC, run_id ASC"
        ).fetchall()
    newest = {row[0]: row for row in rows}  # later rows overwrite earlier ones
    declared = _declared_params(yaml.safe_load((study_dir / "study.yaml").read_text()))

    commits = set()
    runs = {}
    for label, (_, run_id, status, params_json, manifest_json) in newest.items():
        assert status == "completed", f"latest run of {label!r} is {status!r}"
        recorded = {k: v for k, v in json.loads(params_json).items() if k != "n_steps"}
        expected = {k: v for k, v in declared[label].items() if k != "n_steps"}
        assert recorded == expected, f"{label!r} ran with {recorded}, study declares {expected}"
        commits.add(json.loads(manifest_json)["code_version"]["git_sha"])
        run = Run(db, run_id)
        assert run.observable("vitals.irreversible_state").max() == 0, f"{label!r} went irreversible"
        runs[label] = run
    assert len(commits) == 1, f"runs come from several commits: {sorted(commits)}"
    return runs
