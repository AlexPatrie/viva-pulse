# viva-pulse

A [process-bigraph](https://github.com/vivarium-collective/process-bigraph) wrapper that drives the **real** [Kitware Pulse Physiology Engine](https://gitlab.kitware.com/physiology/engine) (whole-body adult model). Pulse runs as a time-stepped `Process`. Interventions are input ports, vital signs are output ports, and simulations are ordinary `process_bigraph.Composite` documents. Nothing is reimplemented or mocked: every number comes from Pulse's C++ engine through its own Python bindings.

## Status

- **Available:** the `PulseProcess` and `MapFluidController` processes, and the `pulse_hemorrhage` and `pulse_resuscitation` composites. All are tested against the real engine.
- **Planned:** one composite per Pulse circuit family, starting with cardiovascular, then respiratory and ventilator, thermal, and ECMO and other equipment. See [docs/plan/plan-circuit-composites.md](docs/plan/plan-circuit-composites.md).

## Requirements

Pulse has no PyPI release, so it is built from source.

- A Pulse source checkout at `../engine`, pinned to engine commit `5e29e5b13` (Pulse 4.4.0).
- CMake ≥ 3.31, a C++20 compiler, and a JDK (Pulse's data generation uses Java).
- [uv](https://docs.astral.sh/uv/) and CPython 3.12. `PyPulse` must be compiled against the same Python that runs this package.

## Setup

```bash
uv venv --seed --python 3.12 .venv      # --seed: the Pulse build pip-installs protobuf into this venv

# Configure and build Pulse into .pulse-build/install (gitignored). Takes a while the first time.
VIRTUAL_ENV=$PWD/.venv cmake --fresh -S ../engine -B .pulse-build \
  -DCMAKE_BUILD_TYPE:STRING=Release -DPulse_PYTHON_HOME_DIR=$PWD/.venv \
  -DPython3_FIND_VIRTUALENV=ONLY \
  -DPulse_JAVA_API=ON -DPulse_PYTHON_API=ON -DPulse_GEN_DATA=ON
VIRTUAL_ENV=$PWD/.venv cmake --build .pulse-build -j 12

uv pip install -r ../engine/requirements.txt
uv pip install -e '.[dev]'
```

`-DPython3_EXECUTABLE` is ignored by Pulse's CMake; the venv is selected with `-DPulse_PYTHON_HOME_DIR` together with `VIRTUAL_ENV`. Build pins and known workarounds are in [.build-progress.md](.build-progress.md).

**Never run `uv sync`.** The venv is assembled by hand, and a sync would resolve protobuf away from the version Pulse generated its bindings with. It would also remove the dev and engine requirements. Run everything with `uv run --no-sync`.

### Finding the Pulse install

`viva_pulse.runtime` uses the first of these that is set:
1. the `install_dir` process config;
2. `$PULSE_INSTALL_DIR`;
3. `.pulse-build/install`.

An explicitly given location that is not a valid install raises `PulseNotFoundError`; it never falls back to another location.

## Usage

```python
from process_bigraph import Composite, gather_emitter_results

from viva_pulse.composites.hemorrhage import pulse_resuscitation
from viva_pulse.core import build_core

core = build_core()   # registers viva-pulse's processes explicitly
doc = pulse_resuscitation(core, compartment="RightLeg", severity=0.8, target_map_mmHg=90.0)
sim = Composite({"state": doc}, core=core)
sim.run(600)          # 600 simulated seconds -> 601 emitted rows (first at t=0)
rows = gather_emitter_results(sim)[("emitter",)]
```

### Composites

| Generator | What it runs |
|---|---|
| `pulse_hemorrhage` | Untreated hemorrhage at a chosen compartment and severity. Emits vital signs every second. |
| `pulse_resuscitation` | The same hemorrhage plus a closed-loop IV fluid controller that targets mean arterial pressure. |

Both use `fidelity="real-bridge"`. Patients load from Pulse's stabilized state files (`<install>/bin/states/*.json`, default `StandardMale@0s.json`).

### Processes

- **`PulseProcess`**:
  - Loads a stabilized Pulse state and advances the engine by `interval` seconds per update.
  - Inputs `hemorrhage_severity` and `iv_rate_mL_per_min` are setpoints, sent to Pulse as actions only when they change.
  - Outputs are nine vital signs plus an `irreversible_state` flag. Vitals are `float` ports carrying deltas, seeded with the loaded readings, so each store always equals Pulse's own value. The reason for this design is in `.build-progress.md`.
- **`MapFluidController`**: a proportional `Step` that maps mean arterial pressure to IV infusion rate.

## Pulse circuits

Pulse models physiology as lumped-parameter circuits. Below is the cardiovascular circuit, the target of the first circuit composite:

![Pulse cardiovascular circuit](docs/images/circuit-cardio.png)

*Pulse cardiovascular circuit diagram. Copyright Kitware, Inc. and Contributors, Apache License 2.0, from `engine/docs/Images/Cardiovascular/CardiovascularCircuit.png`.*

## Tests

```bash
uv run --no-sync pytest -q
```

The full suite takes about 65 s. Every engine-dependent test drives the real Pulse build; nothing is mocked.

## License

viva-pulse is MIT-licensed. Pulse is distributed by Kitware, Inc. under the Apache License 2.0; see `../engine/LICENSE` and `../engine/NOTICE`.
