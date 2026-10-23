## Current Session

Goal: `/viva-expert ./` (run from `~/uchc/twin/engine`) — heavy single-tool
mode, REAL bridge to the Kitware Pulse Physiology Engine. Wrapper repo is
this directory (user-chosen). Build pins, phase ledger, probe results and
workarounds: [.build-progress.md](.build-progress.md) — read it first.

**Active agenda:** `agenda.md` (repo root, name `circuit-composites`): "fully
implement and complete" [docs/plan/plan-circuit-composites.md](docs/plan/plan-circuit-composites.md).
`agenda.md` is kept out of git via `.git/info/exclude` (user, 2026-10-22).

**Standing user instructions (2026-10-22):**
- Do NOT commit without asking. The only approved commit so far is the
  Phase 4.5 bootstrap `afac8be` on `main`.
- Keep README.md current with every user-visible change.
- Never `uv sync`; always `uv run --no-sync`.
- `../engine` is a separate repo: on branch `viva-wrapper`, with untracked
  `.skills/` and `CLAUDE.md` that this session did not create. Untouched
  this session; ask before committing there.

### State at checkpoint (2026-10-22, late)

- Branch `feat/circuit-cardiovascular` (off `main` @ `afac8be`). **Phase 1 is
  implemented, uncommitted:**
  - Modified: `.build-progress.md`, `CLAUDE.md`, `CURRENT.md`, `README.md`,
    `docs/plan/plan-circuit-composites.md`, `viva_pulse/{__init__,core,processes}.py`,
    `viva_pulse/composites/__init__.py`.
  - New: `viva_pulse/circuits/{__init__,base,cardiovascular}.py`,
    `viva_pulse/composites/circuits.py`, `tests/test_circuits.py`.
- `uv run --no-sync pytest -q`: **61 passed, 1 skipped (~85 s)**, and
  workspace lint OK. Version bumped to 0.2.0. The skip is the template's
  `test_composite_state_artifacts`.
- **The `/adversarial` review is DONE (2026-10-23)**: no blockers; all 10
  findings fixed. They are recorded in `.build-progress.md` and the plan's
  "Phase 1 implementation notes".
- **Release decision (user, 2026-10-23):**
  - Create a **private GitHub repo** (planned name `AlexPatrie/viva-pulse`,
    which is free).
  - Push `main` plus the feature branch, open a PR, then tag v0.2.0 and make a
    GitHub Release after the merge.
  - **Add `eagmon` (Eran Agmon) with write access** (user, 2026-10-23).
- **Blocker before pushing:** the template's CI can't pass.
  - `workspace-ci.yml` runs `pytest tests/` on push and PR, but there is no
    Pulse build on the runners.
  - `publish-dashboard.yml` and `publish-reports.yml` publish to Pages on every
    push to `main`.
  - How to handle this is with the user.

### Phase 1 design (as built; details in `CLAUDE.md` Architecture)

- `PulseCircuitProcess` (`viva_pulse/processes.py`):
  - one real WholeBody engine (`SUPPORTED_MODEL_TYPES = {"whole_body"}`);
  - `config.modules` (default `[]`, empty raises) selects
    `viva_pulse.circuits.MODULES`;
  - outputs nest per module as `float` deltas, plus `irreversible_state`;
  - inputs sit under the single port `setpoints/<module>/...` as
    `overwrite[float]`, each with `_default` = baseline;
  - deduped requests; act-on-change actions; a NaN guard fails the load and
    names the unserved request;
  - shares `_load_engine()` with `PulseProcess`, whose ports and config are
    unchanged.
- `circuits/cardiovascular.py` has 146 outputs:
  - 20 `SECardiovascularSystem` scalars under `hemodynamics/`;
  - Pressure/Volume/Inflow/Outflow for 32 compartments under `central/` (10),
    `renal/` (8) and `peripheral/` (14), minus Pericardium flows.
  - Setpoints: 10 multipliers sent as one `SECardiovascularMechanicsModification`
    with `incremental=True` and the full group resent; plus `hemorrhage_severity`
    with config `hemorrhage_compartment`.
- `composites/circuits.py`: `circuit_node()`, `circuit_emitter()` and
  `@composite_generator pulse_cardiovascular`. Stores: `interventions/<module>`,
  `circuits/<module>`, `circuits/irreversible_state`, `emitter`.

### Bugs found and fixed this session (each is non-obvious)

1. **Spelling:** Pulse's compartment flow properties are `Inflow`/`Outflow`. An
   Explore subagent's `InFlow` returned NaN for every compartment. Found by
   probe P3, then read in `SEDataRequestTracker.cpp`.
2. **Store leak:** process-bigraph projects `initial_state()` through **input**
   wires as well as output wires. When the input and output ports shared the
   module name, readings leaked into `interventions/cardiovascular`.
   - Fix: a disjoint `setpoints` input namespace; `RESERVED_NAMES` in
     `circuits/base.py`.
   - Regression test: `test_stores_hold_only_their_own_ports`, verified to fail
     on a scratch reconstruction of the old design.
3. **Test arithmetic:** my compartment count was off (31 vs the real 32).

### Verified engine facts used by Phase 1 (also in `.build-progress.md`)

- Measured effects at 60 s from baseline:
  - systemic resistance x2: HR 72 -> 43, CO 5.78 -> 4.00 L/min, MAP 95.3 -> 97.1
    (the baroreflex defends MAP);
  - x0.5: HR 113, CO 8.11;
  - arterial resistance x2: no measurable change;
  - HR multiplier 1.3: HR 85.7.
- Baseline drift over 60 s: MAP 95.25 -> 95.26.
- Hemorrhage, RightLeg 0.8, 120 s: BV deficit 355 mL vs 360 mL reported lost;
  RightLeg volume 215.5 -> 146.1 mL; HR only +2.6 bpm by then.
- Compartment values are instantaneous within each heartbeat; 1 s sampling
  aliases them, and `interval=0.02` resolves waveforms.
- Non-incremental CV modification triggers a hidden restabilization
  (`Controller.cpp:1050-1068`).
- Hemodynamics engine: segfaults on its first advance (null ECG model, crash log
  `~/Library/Logs/DiagnosticReports/python3.12-2026-10-22-185434.ips`), and
  Python silently falls back to WholeBody (`PulseEngine.py:46-49`). Fixing it
  is an optional, deferred local `../engine` track.

### Next

1. Get the `/adversarial` result (or re-run it); fix real gaps; re-run pytest.
2. Bump the version to 0.2.0 in `pyproject.toml` (BOJ: same unit as the fix
   and tests). Ask the user to commit Phase 1 on `feat/circuit-cardiovascular`,
   and how to handle PR, tag and release with no remote configured.
3. Phase 2 (respiratory + ventilator): first probe in a subprocess that
   VentilationMechanics advances cleanly; reference
   `HowTo_VentilationMechanics.py`. Then Phase 3 thermal, Phase 4 ECMO and
   equipment, Phase 5 the whole-body composite.
4. Earlier backlog, still open:
   - `CONTRIBUTING.md` and `.github/workflows/release.yml`.
   - Phase 5 investigation (`vwb scaffold-investigation --name pulse --studies
     viva_pulse.composites.hemorrhage.pulse_hemorrhage,viva_pulse.composites.hemorrhage.pulse_resuscitation`;
     fill `expected_behavior`/`behavior_tests` from the reference results below;
     `studies/*/sims/run.py` with `build_core()`; Plotly viz, loading the
     `dataviz` skill first).
   - Optionally, `pulse_cardiovascular` in that investigation.

### Earlier verified state (pre-circuit work)

- Pulse superbuild in `.pulse-build/` (gitignored); Pulse 4.4.0 @ engine commit
  `5e29e5b13`; `PyPulse` built for the `.venv` CPython 3.12.12.
- Phase 4.5 (2026-10-22): `vwb scaffold-workspace --in-place` produced commit
  `afac8be` (51 template files, including template tests
  `test_composite_state_artifacts.py` and `test_core_registration.py`).
  `scripts/lint-workspace.py` reports `workspace lint: OK`.
  - Only `pyyaml` and `jsonschema[format-nongpl]` were installed from the new
    pyproject deps; protobuf stays 7.35.0. A full install would downgrade
    python-dateutil and pull vivarium-workbench 0.3.92.
  - Catalog entry fixed to `package: viva_pulse` (forget + add).
- Reference results (StandardMale, RightLeg 0.8, 600 s): untreated HR
  72->107, MAP 95->84, BV 5487->3936 mL, 1577 mL lost. With controller
  (target 90): MAP 86.3, BV 4014. Aorta 1.0 is irreversible at t=68 s.

### Open items to report upstream

- process-bigraph 1.10 / bigraph-schema 1.8.2 drop `initial_state()` values
  for `overwrite[float]` and `boolean` output ports (repro in
  `.build-progress.md`), and also project `initial_state()` through input
  wires (bug 2 above).
- viva-superpowers `workspace_catalog.add` reads workspace.yaml `package`, but
  the template writes `package_path`.
- Pulse (Kitware):
  - the Hemodynamics engine has a null ECG dereference;
  - `PulseEngine.py` silently falls back to WholeBody for Hemodynamics;
  - `process_action(s)` discards the engine's success flag;
  - `set_event_handler` calls an unbound `keep_event_changes`.
