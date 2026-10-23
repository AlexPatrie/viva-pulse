## Current Session

Goal: `/viva-expert ./` (run from `~/uchc/twin/engine`) — heavy single-tool
mode, REAL bridge to the Kitware Pulse Physiology Engine. Wrapper repo is
this directory (user-chosen). Build pins, phase ledger and workarounds:
[.build-progress.md](.build-progress.md) — read it first.

**User instruction (2026-10-22): do NOT commit.** Repo is `git init`'d on
`main` with zero commits; everything is untracked. Ask before any commit.
Note `vwb scaffold-workspace` (Phase 4.5) creates a bootstrap commit by
default — confirm with the user before running it.

### Done (verified)

- Pulse superbuild in `.pulse-build/` (gitignored), Pulse 4.4.0 @ engine
  commit `5e29e5b13`; `PyPulse` built for the `.venv` CPython 3.12.12.
- Package `viva_pulse/`:
  - `runtime.py` — locates the Pulse install: `install_dir` config >
    `$PULSE_INSTALL_DIR` > `.pulse-build/install`; an explicitly given
    location that is invalid raises `PulseNotFoundError` (no fallback).
  - `processes.py` — `PulseProcess` (inputs `hemorrhage_severity`,
    `iv_rate_mL_per_min` as `overwrite[float]` setpoints, sent to Pulse as
    actions only on change; outputs 9 vitals as `float` deltas seeded by
    `initial_state()`, plus `irreversible_state` boolean) and
    `MapFluidController` (proportional MAP->IV-rate Step).
  - `core.py` — `build_core()` / `register_processes()`.
  - `composites/hemorrhage.py` — `@composite_generator`s `pulse_hemorrhage`
    and `pulse_resuscitation` (`fidelity="real-bridge"`, `core_extensions`).
- `pyproject.toml` (hatchling, `[dev]` extra); installed editable in `.venv`.
- Tests: `.venv/bin/python -m pytest -q` -> 22 passed (~65 s), all against
  the real engine. Regression test for the t=0 zero-vitals bug verified to
  fail on the old `overwrite[float]` design.
- Reference results (StandardMale, RightLeg sev 0.8, 600 s): untreated
  HR 72->107, MAP 95->84, BV 5487->3936 mL, 1577 mL lost; with controller
  (target 90) MAP 86.3, BV 4014. Aorta sev 1.0 -> irreversible at t=68 s.

### Per-circuit composites (plan approved 2026-10-22)

Plan: [docs/plan/plan-circuit-composites.md](docs/plan/plan-circuit-composites.md).
Diagram copied to `docs/images/circuit-cardio.png` (Kitware, Apache-2.0).
Decisions: process-bigraph Processes/Steps over Pulse's real Python bindings,
run via `process_bigraph.Composite`, with no Python-native rewrite.
Cardiovascular goes first, on the **WholeBody** engine. The HumanAdultHemodynamics
(CV-only) engine segfaults on its first advance (null ECG model, crash log
`~/Library/Logs/DiagnosticReports/python3.12-2026-10-22-185434.ips`), so fixing
it is an optional later track as a local `../engine` patch. Then respiratory +
ventilator, then thermal, then ECMO and other equipment. This work comes after Phase 4.5.
Keep README.md current with every user-visible change (user, 2026-10-22).

### Next

1. README.md is written (setup, usage, composites, diagram) and its usage
   example was verified by a real 5 s run. Still to do: `CONTRIBUTING.md`,
   `.github/workflows/release.yml`.
2. Phase 4.5: `vwb scaffold-workspace --in-place --name pulse --target .
   --package viva_pulse --branch main` (makes a commit — ask first), then
   `vwb catalog-add`, `python scripts/lint-workspace.py`, re-run pytest.
3. Phase 5: `vwb scaffold-investigation --name pulse --studies
   viva_pulse.composites.hemorrhage.pulse_hemorrhage,viva_pulse.composites.hemorrhage.pulse_resuscitation`;
   fill `expected_behavior`/`behavior_tests` with the reference results above;
   `studies/*/sims/run.py` per the viva-expert reference template (use
   `build_core()`); Plotly viz (load the `dataviz` skill first); publish.
4. Circuit composites: Phase 0 probes P5 (nested per-module ports) and P3
   (non-NaN CV compartments on WholeBody), then Phase 1 (`PulseCircuitProcess`,
   `viva_pulse/circuits/`, `pulse_cardiovascular`). See the plan.
5. `/adversarial` review of the package before calling it done.

### Open item to report upstream

process-bigraph 1.10 / bigraph-schema 1.8.2 drop `initial_state()` values for
`overwrite[float]` and `boolean` output ports (minimal repro in
`.build-progress.md`). Worked around by design here, not patched.
