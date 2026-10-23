# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this is

`viva-pulse` is a process-bigraph wrapper that drives the **real** Kitware Pulse Physiology Engine (whole-body adult model). Pulse has no PyPI release: it is built from source (sibling checkout `../engine`, which has its own CLAUDE.md) through its CMake superbuild into `.pulse-build/` (gitignored). Build pins, the exact configure command, and known build workarounds are in [.build-progress.md](.build-progress.md); read it before touching the build.

Session state (active work, next steps, user instructions such as "do not commit") lives in [CURRENT.md](CURRENT.md).

## Commands

The venv is `.venv` (uv-created, CPython 3.12.12, the same Python `PyPulse` was compiled against).

```bash
uv run --no-sync pytest -q                                              # full suite, ~65 s, real engine
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
- `viva_pulse/core.py`: `build_core()` registers the processes explicitly on an `allocate_core()` core, because discovery can miss editable installs. Tests and any `studies/*/sims/run.py` should use it.
- `viva_pulse/composites/hemorrhage.py`: `@composite_generator`s `pulse_hemorrhage` and `pulse_resuscitation` (`fidelity="real-bridge"`, `core_extensions=[register_processes]`). Store layout: `interventions/` (setpoints), `vitals/` (engine outputs), and a `RAMEmitter` step at `emitter`. `PulseProcess` runs at `interval: 1.0`, so a run of `N` simulated seconds emits `N + 1` rows, the first at t=0.

## Tests

Nothing is mocked. Tests that need the engine drive the real Pulse build. The validation, controller and registry tests don't load the engine at all. `tests/conftest.py::run_composite` builds a generator's document on a fresh `build_core()` and returns `(sim, emitter rows)`. Engine loads are cheap (well under a second); the suite's runtime comes from simulated time, mostly the two 600 s runs in `test_resuscitation_controller_engages_and_preserves_volume`.
