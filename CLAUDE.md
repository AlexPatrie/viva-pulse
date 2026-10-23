# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this is

`viva-pulse` is a process-bigraph wrapper that drives the **real** Kitware Pulse Physiology Engine (whole-body adult model). Pulse has no PyPI release: it is built from source (sibling checkout `../engine`, which has its own CLAUDE.md) through its CMake superbuild into `.pulse-build/` (gitignored). Build pins, the exact configure command, and known build workarounds are in [.build-progress.md](.build-progress.md); read it before touching the build.

Session state (active work, next steps, user instructions such as "do not commit") lives in [CURRENT.md](CURRENT.md).

## Commands

The venv is `.venv` (uv-created, CPython 3.12.12, the same Python `PyPulse` was compiled against).

```bash
uv run --no-sync pytest -q                                              # full suite, ~80 s, real engine
uv run --no-sync pytest -q tests/test_processes.py::test_zero_severity_does_not_bleed   # one test
```

Always pass `--no-sync`, and never run `uv sync`. The venv was assembled by hand, not from a lockfile: the Pulse build installed protobuf 7.35.0 to match its generated `_pb2` code, and `../engine/requirements.txt` was installed into it. With no `uv.lock` present, a sync would write a lock and resolve protobuf to a newer version (7.36.x at the time of writing). `uv sync` is also exact, so it would remove pytest (only in the `[dev]` extra) and the engine requirements.

Rebuilding Pulse (only after changing `../engine`): run the configure + build pair in `.build-progress.md` from the repo root. `--fresh` discards the CMake cache. `-DPython3_EXECUTABLE` is ignored by Pulse's CMake; the venv is selected with `-DPulse_PYTHON_HOME_DIR` plus `VIRTUAL_ENV`. `README.md` carries the user-facing setup, usage and composite list (`pyproject.toml` and the `PulseNotFoundError` message point to it); keep it current with every user-visible change. `.build-progress.md` remains the authority for build pins and workarounds.

The per-circuit composite plan (approved 2026-10-22) is [docs/plan/plan-circuit-composites.md](docs/plan/plan-circuit-composites.md).

## Architecture

- `viva_pulse/runtime.py` resolves the Pulse install prefix (`install_dir` config > `$PULSE_INSTALL_DIR` > `.pulse-build/install`) and puts `bin/` (holds `PyPulse*.so`; also the engine's data root, incl. `bin/states/*.json`) and `python/` (the `pulse` package) on `sys.path`. An explicitly given location that is invalid raises `PulseNotFoundError`; it never falls back.
- `viva_pulse/processes.py`
  - `PulseProcess` loads a stabilized state file lazily on first use, then advances Pulse by `interval` seconds per update. Its inputs (`hemorrhage_severity`, `iv_rate_mL_per_min`) are `overwrite[float]` setpoints, forwarded to Pulse as patient actions only when they change.
  - The outputs are the `VITALS` table (port name -> Pulse property, unit). Vitals are plain `float` ports carrying **deltas** (`current - previous`), seeded with absolute readings by `initial_state()`, so the store always equals Pulse's own value. This is deliberate: process-bigraph 1.10 / bigraph-schema 1.8.2 discard `initial_state()` values on `overwrite[float]` and `boolean` output ports (repro in `.build-progress.md`). Don't "simplify" the vitals to `overwrite[float]`; `tests/test_composites.py::test_first_emitted_row_carries_loaded_vitals` guards this.
  - `irreversible_state` flips to True when `advance_time_s` fails. After that the engine is not advanced again and the update returns `{}`.
  - `MapFluidController` is a proportional MAP -> IV-rate `Step` that writes the `overwrite[float]` setpoint.
  - `PulseCircuitProcess` is the per-circuit sibling of `PulseProcess`. It shares `_load_engine()` and the same delta/latch output contract.
    - `config.modules` selects entries of `viva_pulse.circuits.MODULES`. The default is `[]` and an empty list raises: a non-empty `list[string]` default would *merge* with overrides.
    - Output ports nest per module, e.g. `cardiovascular/central/aorta/pressure_mmHg`.
    - Setpoints live under the single input port `setpoints/<module>/...`. Each port's schema `_default` is its baseline, so an omitted setpoint is never 0.0.
    - Input and output top-level names must stay disjoint. process-bigraph projects `initial_state()` through input wires too, and a shared name copied readings into `interventions/` (`test_stores_hold_only_their_own_ports` guards this).
    - Only `model_type: whole_body` is supported (`SUPPORTED_MODEL_TYPES`).
- `viva_pulse/circuits/`: a declarative registry; modules compute nothing.
  - `base.py` defines `Request` (one Pulse data request at a port path), `ActionBinding` (a group of setpoints resent whole as one action) and `CircuitModule`.
  - `cardiovascular.py` covers the cardiovascular circuit plus its renal and tissue branches, which share one Pulse solve. It has 146 outputs:
    - 20 system scalars under `hemodynamics/`;
    - Pressure/Volume/Inflow/Outflow for 32 regions under `central/`, `renal/` and `peripheral/`.
  - Its setpoints are the 10 `SECardiovascularMechanicsModifiers` multipliers, always sent with `incremental=True` (non-incremental reruns stabilization and resets baselines), plus hemorrhage.
  - Pulse spells compartment flows `Inflow`/`Outflow`; `InFlow` returns NaN.
  - A request Pulse can't serve returns NaN, so the process fails the load instead of emitting it.
- `viva_pulse/core.py`: `build_core()` registers the processes explicitly on an `allocate_core()` core, because discovery can miss editable installs. Tests and any `studies/*/sims/run.py` should use it.
- `viva_pulse/composites/hemorrhage.py`: `@composite_generator`s `pulse_hemorrhage` and `pulse_resuscitation` (`fidelity="real-bridge"`, `core_extensions=[register_processes]`). Store layout: `interventions/` (setpoints), `vitals/` (engine outputs), and a `RAMEmitter` step at `emitter`. `PulseProcess` runs at `interval: 1.0`, so a run of `N` simulated seconds emits `N + 1` rows, the first at t=0.
- `viva_pulse/composites/circuits.py`: `circuit_node()` / `circuit_emitter()` wiring helpers and the `pulse_cardiovascular` generator. Store layout: `interventions/<module>/`, `circuits/<module>/`, `circuits/irreversible_state`, and `emitter`, which emits both subtrees.

## Tests

Nothing is mocked. Tests that need the engine drive the real Pulse build. The validation, controller and registry tests don't load the engine at all. `tests/conftest.py::run_composite` builds a generator's document on a fresh `build_core()` and returns `(sim, emitter rows)`. Engine loads are cheap (well under a second); the suite's runtime comes from simulated time, mostly the two 600 s runs in `test_resuscitation_controller_engages_and_preserves_volume`. In `tests/test_circuits.py` the expected values come from one of three places:
- a separate engine loaded directly through Pulse's API, with requests spelled out independently in `ORACLE` (`_direct_engine`);
- the actions active in Pulse's own serialized state (`_active_actions`);
- measured physiological effect thresholds, e.g. systemic resistance x2 drops HR by more than 15 bpm.

The new tests were checked against deliberately broken copies of the code in the scratchpad: per-group validation, and never forwarding a return to baseline.
