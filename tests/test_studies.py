"""Workbench studies: every baseline and variant runs, and every readout exists.

The workbench resolves each study entry itself (``dry_run`` returns the exact
spec id and generator overrides a real run would use, with no side effects).
The document is then built with the strict generator builder, which rejects
undeclared parameters, and run on the real engine. The workbench's static
``check-observables`` cannot see stores that processes create through their
output wires (``vitals/`` here), so the readout paths are checked against the
realized composite instead.
"""

from pathlib import Path

import pytest
import yaml
from process_bigraph import Composite
from process_bigraph.composite_generator import _REGISTRY, build_generator
from vivarium_workbench.lib.study_runs import run_study_baseline, run_study_variant

from viva_pulse.core import build_core
from viva_pulse.runtime import resolve_install_dir

ROOT = Path(__file__).resolve().parents[1]
STUDIES = ROOT / "workspace" / "studies"


def _entries():
    for study_yaml in sorted(STUDIES.glob("*/study.yaml")):
        spec = yaml.safe_load(study_yaml.read_text())
        study = spec["name"]
        for entry in spec.get("baseline", []):
            yield pytest.param(study, "baseline", entry["name"], id=f"{study}/{entry['name']}")
        for entry in spec.get("variants", []):
            yield pytest.param(study, "variant", entry["name"], id=f"{study}/{entry['name']}")


def _resolve(study, kind, name):
    if kind == "baseline":
        body, status = run_study_baseline(ROOT, {"study": study, "composite": name, "dry_run": True})
    else:
        body, status = run_study_variant(ROOT, {"study": study, "variant": name, "dry_run": True})
    assert status == 200, body
    return body["request"]["spec_id"], body["request"]["overrides"]


def _leaf(state, dotted):
    node = state
    for part in dotted.split("."):
        assert isinstance(node, dict) and part in node, f"{dotted!r} missing at {part!r}"
        node = node[part]
    return node


def test_the_three_hemorrhage_studies_exist():
    names = sorted(p.parent.name for p in STUDIES.glob("*/study.yaml"))
    assert names == ["fluid-resuscitation", "hemorrhage-severity-sweep", "patient-cohort"]


def test_cohort_covers_every_shipped_patient():
    spec = yaml.safe_load((STUDIES / "patient-cohort" / "study.yaml").read_text())
    entries = spec["baseline"] + spec["variants"]
    state_files = sorted({**e.get("params", {}), **e.get("parameter_overrides", {})}["state_file"]
                         for e in entries)
    shipped = sorted(p.name for p in (resolve_install_dir() / "bin" / "states").glob("*@0s.json"))
    assert state_files == shipped
    assert len(shipped) == 21


@pytest.mark.parametrize("study, kind, name", list(_entries()))
def test_study_entry_runs_and_emits_its_readouts(study, kind, name):
    spec_id, overrides = _resolve(study, kind, name)
    core = build_core()
    document = build_generator(_REGISTRY[spec_id], overrides=overrides, core=core)
    sim = Composite({"state": document}, core=core)
    sim.run(1.0)
    readouts = yaml.safe_load((STUDIES / study / "study.yaml").read_text())["readouts"]
    assert readouts
    for readout in readouts:
        value = _leaf(sim.state, readout["store_path"])
        assert isinstance(value, (int, float)), (readout["store_path"], value)
    assert sim.state["vitals"]["irreversible_state"] is False
