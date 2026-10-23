---
file_format: mystnb
kernelspec:
  name: python3
  display_name: Python 3
---

# Tutorial 2: the cardiovascular circuit, region by region

**What you will do:** double the systemic vascular resistance of the cardiovascular circuit and
see how the whole circuit responds; then resolve a few heartbeats of aortic pressure.

**What you need:** the installation from {doc}`../installation`. This tutorial runs in about
ten seconds.

**Words used here** (see {doc}`../glossary`): circuit module, region, setpoint.

## The composite

`pulse_cardiovascular` runs one `PulseCircuitProcess` with the `cardiovascular` module on the
whole-body engine. Its readings land under `circuits/cardiovascular/`:

- `hemodynamics/`: whole-circuit values such as heart rate, cardiac output and MAP;
- `central/`, `renal/` and `peripheral/`: pressure, volume, inflow and outflow for each region
  of the circuit diagram in {doc}`../concepts/circuits`.

Its setpoints, under `interventions/cardiovascular/`, are Pulse's ten resistance and
compliance multipliers (1.0 means unchanged) and a hemorrhage.

```{code-cell} python
from process_bigraph import Composite, gather_emitter_results

from viva_pulse.composites import pulse_cardiovascular
from viva_pulse.core import build_core


def run(seconds, **params):
    core = build_core()
    sim = Composite({"state": pulse_cardiovascular(core, **params)}, core=core)
    sim.run(seconds)
    return gather_emitter_results(sim)[("emitter",)]


baseline = run(60)
stiff = run(60, systemic_resistance_multiplier=2.0)
sorted(baseline[-1]["circuits"]["cardiovascular"])
```

## How the whole circuit answers

```{code-cell} python
def hemodynamics(rows):
    return rows[-1]["circuits"]["cardiovascular"]["hemodynamics"]

for key in ("heart_rate_bpm", "cardiac_output_L_per_min", "mean_arterial_pressure_mmHg",
            "systemic_vascular_resistance_mmHg_min_per_L"):
    print(f"{key:46s}{hemodynamics(baseline)[key]:9.2f}{hemodynamics(stiff)[key]:9.2f}")
```

```{code-cell} python
:tags: [remove-cell]
from myst_nb import glue

svr = "systemic_vascular_resistance_mmHg_min_per_L"
glue("svr_ratio", hemodynamics(stiff)[svr] / hemodynamics(baseline)[svr], display=False)
```

Doubling the multiplier raises the measured systemic vascular resistance
{glue:text}`svr_ratio:.2f`-fold, yet MAP barely moves: the baroreflex slows the heart and
cardiac output falls, which holds pressure steady.

## Every region at once

Each region carries the same four readings. Here is the aorta, the kidneys and the legs
after 60 s.

```{code-cell} python
cv = stiff[-1]["circuits"]["cardiovascular"]
regions = [("central", "aorta"), ("renal", "left_kidney"), ("peripheral", "left_leg"),
           ("peripheral", "right_leg")]
print(f"{'region':24s}{'pressure':>10s}{'volume':>10s}{'inflow':>10s}{'outflow':>10s}")
for group, name in regions:
    r = cv[group][name]
    print(f"{group + '/' + name:24s}{r['pressure_mmHg']:10.1f}{r['volume_mL']:10.1f}"
          f"{r['inflow_mL_per_min']:10.0f}{r['outflow_mL_per_min']:10.0f}")
```

## Resolve the heartbeat

Region readings are instantaneous. At the default one reading per second they alias the
cardiac cycle, so to see a waveform, sample at Pulse's own timestep, `interval=0.02`.

```{code-cell} python
import matplotlib.pyplot as plt

beats = run(3.0, interval=0.02)
t = [r["time"] for r in beats]
aorta = [r["circuits"]["cardiovascular"]["central"]["aorta"]["pressure_mmHg"] for r in beats]
fig, ax = plt.subplots(figsize=(7, 3))
ax.plot(t, aorta, color="#2a78d6", lw=2)
ax.set_xlabel("Time (s)")
ax.set_ylabel("Aortic pressure (mmHg)")
ax.grid(color="#e1e0d9")
fig.tight_layout()
```

process-bigraph accumulates time as floats, so an interval that isn't exact in binary, such as
0.02, can drop the last update of a run: here the last row is at t = {glue:text}`last_time:.2f` s.

```{code-cell} python
:tags: [remove-cell]
glue("last_time", t[-1], display=False)
```
