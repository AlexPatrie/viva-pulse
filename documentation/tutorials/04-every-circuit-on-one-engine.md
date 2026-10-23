---
file_format: mystnb
kernelspec:
  name: python3
  display_name: Python 3
---

# Tutorial 4: every circuit on one engine

```{include} _hosted.md
```

**What you will do:** run every circuit module on one whole-body engine, put the patient on a
non-rebreather oxygen mask, and see the change show up in three circuits at once.

**What you need:** the installation from {doc}`../installation`. This tutorial runs in a few
seconds.

**Words used here** (see {doc}`../glossary`): circuit module, setpoint.

## One engine, five modules

`pulse_whole_body_circuits` runs the cardiovascular, respiratory, mechanical-ventilator,
thermal and supplemental-oxygen modules on one engine, about 270 readings per row. It takes
every module's parameters; the ventilator and the oxygen start disconnected.

```{code-cell} python
from process_bigraph import Composite, gather_emitter_results

from viva_pulse.composites import pulse_whole_body_circuits
from viva_pulse.core import build_core

mask = dict(oxygen_connected=1.0, oxygen_device="NonRebreatherMask", oxygen_flow_L_per_min=10.0)
final = {}
for label, params in (("room air", {}), ("non-rebreather", mask)):
    core = build_core()
    sim = Composite({"state": pulse_whole_body_circuits(core, interval=30.0, **params)}, core=core)
    sim.run(120)
    final[label] = gather_emitter_results(sim)[("emitter",)][-1]["circuits"]

sorted(final["room air"])
```

## One intervention, three circuits

```{code-cell} python
readings = [
    ("supplemental_oxygen", "oxygenation", "arterial_oxygen_pressure_mmHg", "PaO2 (mmHg)"),
    ("cardiovascular", "hemodynamics", "heart_rate_bpm", "heart rate (1/min)"),
    ("respiratory", "mechanics", "respiration_rate_bpm", "breathing rate (1/min)"),
]
print(f"{'':24s}{'room air':>12s}{'non-rebreather':>16s}")
for module, group, key, label in readings:
    print(f"{label:24s}{final['room air'][module][group][key]:12.1f}"
          f"{final['non-rebreather'][module][group][key]:16.1f}")
```

Within two minutes the mask raises arterial oxygen several-fold. Pulse's reflexes answer in
the other circuits: the heart slows and the breathing rate rises.

## Rules worth knowing

- **One airway device at a time.** Connecting the ventilator while the oxygen is connected
  (or both in one update) raises an error, because Pulse stops advancing with two devices on
  the airway. Disconnect one in an update before connecting the other.
- **Same readings as the single-module composites.** At baseline, each module's readings here
  equal those from its own composite; the test suite checks this.
