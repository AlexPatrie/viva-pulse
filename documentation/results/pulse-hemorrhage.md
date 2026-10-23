---
file_format: mystnb
kernelspec:
  name: python3
  display_name: Python 3
---

# Results: the `pulse-hemorrhage` investigation

Three workbench studies of a right-leg hemorrhage, ten minutes each. Everything on this page is
computed, while the docs build, from the run records committed in each study's `runs.db`; no
simulation runs here. {doc}`../howto/run-studies-in-the-workbench` explains how the runs were
made.

```{code-cell} python
:tags: [remove-cell]
import sqlite3
from pathlib import Path

import numpy as np
from IPython.display import HTML, Markdown
from process_bigraph import Composite, allocate_core
from vivarium_workbench.lib.investigations import build_viz_composite, gather_emitter_outputs
from vivarium_workbench.testing import Run
import yaml

STUDIES = Path("../../workspace/studies").resolve()
MAP, HR, BV, LOST = ("vitals.mean_arterial_pressure_mmHg", "vitals.heart_rate_bpm",
                     "vitals.blood_volume_mL", "vitals.total_hemorrhaged_volume_mL")


def runs(study):
    db = STUDIES / study / "runs.db"
    with sqlite3.connect(f"file:{db}?mode=ro", uri=True) as conn:
        rows = conn.execute("SELECT label, run_id FROM runs_meta WHERE status = 'completed' "
                            "ORDER BY started_at").fetchall()
    return {label: Run(db, run_id) for label, run_id in rows}


def figure(study, name):
    """Render a study's declared figure the way the workbench does."""
    from viva_pulse.visualizations.cohort_blood_loss import CohortBloodLoss
    from viva_pulse.visualizations.hemorrhage_severity_response import HemorrhageSeverityResponse
    classes = {c.__name__: c for c in (CohortBloodLoss, HemorrhageSeverityResponse)}
    spec = yaml.safe_load((STUDIES / study / "study.yaml").read_text())
    viz = next(v for v in spec["visualizations"] if v["name"] == name)
    cls = classes[viz["address"].removeprefix("local:")]
    core = allocate_core()
    core.register_link(cls.__name__, cls)
    doc = build_viz_composite(viz, gather_emitter_outputs(STUDIES / study / "runs.db"), {cls.__name__: cls})
    sim = Composite({"state": doc}, core=core)
    sim.run(1)
    return HTML(sim.state["output_store"])
```

## How the record was made

```{code-cell} python
:tags: [remove-input]
import json

lines = ["| Study | Runs | Commit | Python |", "|---|---|---|---|"]
for study in ("hemorrhage-severity-sweep", "fluid-resuscitation", "patient-cohort"):
    db = STUDIES / study / "runs.db"
    with sqlite3.connect(f"file:{db}?mode=ro", uri=True) as conn:
        manifests = [json.loads(m) for (m,) in conn.execute("SELECT manifest_json FROM runs_meta")]
    commits = sorted({m["code_version"]["git_sha"][:7] for m in manifests})
    pythons = sorted({m["env"]["python"] for m in manifests})
    lines.append(f"| `{study}` | {len(manifests)} | {', '.join(commits)} | {', '.join(pythons)} |")
Markdown("\n".join(lines))
```

The pass criteria for each study were fixed before these runs, after pilot runs recorded in
`workspace/experiments/_runs.yaml`. Pulse is deterministic, so where a pilot used the same
settings as a canonical run, that criterion confirms a known outcome rather than predicting
one; each study's `study.yaml` says which.

## Severity sweep

StandardMale, severity 0 (no bleed) to 1.

```{code-cell} python
:tags: [remove-input]
sweep = runs("hemorrhage-severity-sweep")
order = sorted(sweep, key=lambda label: float(label.split("-")[1]))
lines = ["| Severity | Blood lost (mL) | Heart rate (1/min) | MAP (mmHg) |", "|---|---|---|---|"]
for label in order:
    r = sweep[label]
    lines.append(f"| {label.split('-')[1]} | {r.final(LOST):.0f} | {r.final(HR):.1f} | "
                 f"{r.final(MAP):.1f} (start {r.initial(MAP):.1f}) |")
Markdown("\n".join(lines))
```

Blood loss and heart rate rise steadily with severity. MAP holds close to its start for the
milder bleeds, while the faster heart rate compensates, and falls once the bleed outruns that
compensation.

```{code-cell} python
:tags: [remove-input]
figure("hemorrhage-severity-sweep", "severity-response")
```

## Fluid resuscitation

The same bleed (severity 0.8) untreated, or with the MAP-targeted controller (target 90 mmHg)
infusing saline or whole blood.

```{code-cell} python
:tags: [remove-input]
arms = runs("fluid-resuscitation")
lines = ["| Arm | Blood volume (mL) | MAP (mmHg) | Infused (mL) |", "|---|---|---|---|"]
for label in ("untreated", "saline-map-90", "blood-map-90"):
    r = arms[label]
    infused = r.observable("interventions.iv_rate_mL_per_min")[:-1].sum() / 60.0
    lines.append(f"| {label} | {r.final(BV):.1f} | {r.final(MAP):.2f} | {infused:.1f} |")
Markdown("\n".join(lines))
```

Both treated arms keep more blood volume and a higher MAP than the untreated arm. Saline and
whole blood can't be told apart here: the controller only starts once MAP falls below its
target, late in the run, and delivers well under 100 mL. Comparing the two fluids needs a
longer run or an earlier-engaging controller.

## All 21 shipped patients

The same bleed (severity 0.8) from each of the 21 stabilized states Pulse ships.

```{code-cell} python
:tags: [remove-input]
cohort = runs("patient-cohort")
volume = np.array([r.initial(BV) for r in cohort.values()])
fraction = np.array([r.final(LOST) / r.initial(BV) for r in cohort.values()])
ranks = lambda values: values.argsort().argsort()
rho = np.corrcoef(ranks(volume), ranks(fraction))[0, 1]
lines = ["| Patient | Starting blood volume (mL) | Lost (mL) | Lost (%) | MAP start → end (mmHg) |",
         "|---|---|---|---|---|"]
for label, r in sorted(cohort.items(), key=lambda item: item[1].initial(BV)):
    lines.append(f"| {label} | {r.initial(BV):.0f} | {r.final(LOST):.0f} | "
                 f"{100 * r.final(LOST) / r.initial(BV):.1f} | {r.initial(MAP):.1f} → {r.final(MAP):.1f} |")
Markdown(f"Spearman rank correlation of the fraction lost with starting blood volume: "
         f"**{rho:.2f}**.\n\n" + "\n".join(lines))
```

Every patient loses blood volume and MAP and raises heart rate. The absolute loss varies much
less than the starting blood volume does, so smaller patients lose a larger share of their
blood.

```{code-cell} python
:tags: [remove-input]
figure("patient-cohort", "cohort-blood-loss")
```
