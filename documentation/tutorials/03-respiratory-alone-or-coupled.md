---
file_format: mystnb
kernelspec:
  name: python3
  display_name: Python 3
  language: python
---

# Tutorial 3: the respiratory circuit, alone or coupled to the body

```{include} _hosted.md
```

**What you will do:** stiffen both lungs and run the same respiratory module on two engines:
the airway circuit alone, then the airway inside the whole body. The difference shows how much
of the response comes from the circuit itself and how much from the rest of the body.

**What you need:** the installation from {doc}`../installation`. This tutorial runs in a few
seconds.

**Words used here** (see {doc}`../glossary`): engine, circuit module.

## Two engines, one module

`pulse_respiratory` takes `model_type`:

- `ventilation_mechanics`: the airway circuit only. No blood, so no chemoreflex. It has no
  state files, so it starts from a patient file and settles for about one breath before t = 0.
- `whole_body`: the same circuit inside the full adult model.

Halving the lung compliance multipliers makes both lungs stiffer.

```{code-cell} python
from process_bigraph import Composite, gather_emitter_results

from viva_pulse.composites import pulse_respiratory
from viva_pulse.core import build_core

results = {}
for engine in ("ventilation_mechanics", "whole_body"):
    for label, params in (("normal", {}),
                          ("stiff", dict(left_compliance_multiplier=0.5,
                                         right_compliance_multiplier=0.5))):
        core = build_core()
        sim = Composite({"state": pulse_respiratory(core, model_type=engine, **params)}, core=core)
        sim.run(60)
        results[engine, label] = gather_emitter_results(sim)[("emitter",)][-1]["circuits"]["respiratory"]

print(f"{'engine':24s}{'lungs':8s}{'tidal volume (mL)':>20s}{'breaths/min':>14s}")
for (engine, label), resp in results.items():
    m = resp["mechanics"]
    print(f"{engine:24s}{label:8s}{m['tidal_volume_mL']:20.0f}{m['respiration_rate_bpm']:14.1f}")
```

## What the difference means

On the airway alone, stiffer lungs simply take in less air per breath at the same rate: there
is nothing to notice the change. In the whole body, the chemoreflex, which senses the blood
gases, raises the breathing rate. The coupled run's extra response is the body's, not the
circuit's.

## Lung regions

The module also reads the lung and pleural regions. Their `absolute_pressure_cmH2O` is
absolute, with Pulse's ambient at 1033.2 cmH2O; the `mechanics` pressures are relative to the
atmosphere.

```{code-cell} python
lungs = results["whole_body", "stiff"]["lungs"]
{name: round(region["volume_mL"]) for name, region in lungs.items()}
```
