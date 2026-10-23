# Plan: per-circuit Pulse composites (hybrid native)

> On approval, copy this file to `docs/plan/plan-circuit-composites.md` (user request), copy `../engine/docs/Images/Cardiovascular/CardiovascularCircuit.png` (514x720 PNG, Apache-2.0, upstream Kitware) to `docs/images/circuit-cardio.png` (user request, sidebar 2026-10-22), sync `CURRENT.md` and memory (deferred `/checkpoint -d`, blocked by plan mode), then **stand by**.

## Checkpoint (2026-10-22, plan mode, pre-compaction)

- **Task:** user ran `/plan`. Scope a strategy for one process-bigraph composite per Pulse circuit type, and settle native bindings vs a Python-native implementation. When finalized, write the plan to `docs/plan/plan-circuit-composites.md` and stand by. Gather input with `/open-question`.
- **Status:** the plan was **approved** on 2026-10-22, after an adversarial review and revision. All questions are resolved (see "Resolved: whole-body first"). Nothing is implemented yet.
- **Standing constraints:** do NOT commit in viva-pulse without asking (`CURRENT.md`). Never `uv sync`; always `uv run --no-sync`. `../engine` is a separate repo, so ask before committing there too.
- **Next:** Phase 4.5 (needs commit OK), then Phase 0 probes P5/P3, then Phase 1.

## Context

Pulse documents its physiology as lumped-parameter circuits (diagrams in `../engine/docs/Images/<System>/*Circuit*.png`). The goal is one composite per circuit family, built from modular, efficient Process/Step/Composite units, so circuits can be studied alone or composed. viva-pulse today has `PulseProcess` (WholeBody engine, 9 vitals as float deltas, hemorrhage/IV `overwrite[float]` setpoints, `irreversible_state` latch), `MapFluidController` (Step), and generators `pulse_hemorrhage` / `pulse_resuscitation`. There are 22 real-engine tests.

**User decisions (2026-10-22):**
- Strategy: **hybrid native.**
  - Pulse's own reduced engines where they exist: cardiovascular on `HumanAdultHemodynamics`, respiratory + ventilator on `HumanAdultVentilationMechanics`.
  - Modules on the WholeBody engine for the rest.
  - Rejected: binding the bare C++ solver (the circuits are passive without the C++ model drivers, so it would mean a partial reimplementation), and a Python-native rewrite (a reproduction, unvalidated).
- Engine change: a **local patch** in `../engine`, with the option of a Kitware MR "if/when needed".
- Order: **cardiovascular first**, then respiratory + ventilator, then thermal, then ECMO + other equipment.
- Sequencing: **after Phase 4.5** (workspace promotion; it creates a commit, so it needs user OK).

## Verified facts (primary source, re-checked by me)

| Fact | Source |
|---|---|
| PyPulse exposes only a whole-engine handle (state load/init, actions, advance, pull_data of data requests). No circuits, nodes, paths or solver | `../engine/src/python/pybind/PulseEngines.cpp:18-44` |
| Data requests cover physiology, compartment-level (gas/liquid/thermal/tissue Pressure/Volume/InFlow/OutFlow, substances) and equipment. There is no circuit node/path category. Unsupported requests return **NaN** with an "Unhandled data request" log; they do not raise | `SEDataRequest.h:10-14`, `pulse/cdm/engine.py:507-522`; NaN behavior from the reviewer's probe |
| Four independent solves per step (blood, airway, heat, ECMO gas), coupled by explicit lagged exchange. Renal, tissue, CSF and GI share the blood solve's matrix | `CardiovascularModel.cpp:1185`, `RespiratoryModel.cpp:1082`, `EnergyModel.cpp:493`, SCC:899/1750/2096 |
| WholeBody model order: Environment, CV, Inhaler, Respiratory, Anesthesia, BVM, MechVent, GI, Hepatic, Renal, Nervous, Energy, Endocrine, Drug, BloodChem, Tissue, ECG, ECMO | `human_adult/whole_body/controller/Controller.cpp:101-118` |
| Hemodynamics engine: CardiovascularModel only. No serialization (`serialize_from_file` returns False). `Stabilize` is a no-op. Drug, Nervous and Energy are allocated but not processed; **no ECG model is allocated** | `human_adult/hemodynamics/controller/Controller.cpp` |
| Python can't select Hemodynamics: the pybind enum lacks it, and `PulseEngine.__init__` silently falls back to WholeBody. (The reviewer reports `PyPulse.model_type(2)` constructs it anyway via an int cast) | `PyPulse.cpp:55-58`, `PulseEngine.py:46-49` |
| **Hemodynamics segfaults on its first advance**: `CardiovascularModel::Arrhythmia()` calls `m_data.GetECG().IsDefibrillating()` on a null ECG model. Init itself succeeds (~1.7 s; HR 72, MAP 95.3, BV 5487) | `CardiovascularModel.cpp:2291` (also 2301/2307/2313), `common/controller/Controller.cpp:201`; crash log `~/Library/Logs/DiagnosticReports/python3.12-2026-10-22-185434.ips` (stack: AdvanceModelTime > CV PreProcess > ProcessActions > Arrhythmia > GetECG) |
| A non-incremental `SECardiovascularMechanicsModification` triggers `Stabilize(*m_Stabilizer, AdvanceUntilStable)`. `m_Stabilizer` is null except on WholeBody. On WholeBody it is a hidden restabilization with the baroreflex off, plus a MAP/SBP/DBP baseline reset. Python defaults `_incremental = False` | `common/controller/Controller.cpp:1050-1068`, `Controller.h:339`, `whole_body/controller/Controller.cpp:75`, `pulse/cdm/patient_actions.py:303` |
| `list[string]` config **merges** an override into a non-empty default: `['a','b','c']` + `['x']` gives `['a','b','c','x']`; an empty default works | reproduced in `.venv` (bigraph-schema 1.8.2) |
| VentilationMechanics initializes from `SEPatientConfiguration` with only sex set | `pulse/howto/HowTo_VentilationMechanics.py:70-74` |
| `composite_generator` `choices` is UI-only and not enforced | `process_bigraph/composite_generator.py:30-35` (reviewer) |
| `PulseEngine.process_action(s)` discard the thunk's success bool | `PulseEngine.py:214-227` (reviewer) |
| Fast rebuild after an engine edit: `VIRTUAL_ENV=$PWD/.venv cmake --build .pulse-build/Innerbuild --target install -j 12` (copies PyPulse `.so` + `pulse` pkg). Do NOT use the outer superbuild: its `PulseData` target reruns genData/genStates and overwrites `bin/states` | `src/python/CMakeLists.txt:2,39-40,50`, `cmake/external/CMakeLists.txt:116-131` (reviewer) |
| `PulseConfiguration.json` merge is cwd-relative | `common/controller/Controller.cpp:532` (reviewer) |

Consequences:
- **A circuit is never split below its solve.** Renal and tissue are sub-stores of the cardiovascular composite.
- **One Pulse engine maps to one Process.** That Process owns `advance_time_s`; there is no `shared_process`.

## Resolved: whole-body first (user, 2026-10-22)

The cardiovascular composite is built on the **WholeBody** engine first. The Hemodynamics C++ fix is an **optional later track**. The smallest first patch is to allocate `m_ElectroCardioGramModel = new pulse::ElectroCardioGramModel(*this);` beside the other "CV looks for data on them" allocations (hemodynamics `Controller.cpp:68-71`); more null dependencies may follow. Because the module doesn't depend on the engine, enabling `engine=hemodynamics` later needs no change to the module.

The implementation approach is confirmed with the user: process-bigraph Process and Step classes wrap the **real Pulse Python bindings** (`PulseEngine`, data requests, actions), are composed into documents, and run through `process_bigraph.Composite`. There is **no Python-native rewrite** of Pulse's physiology or solver.

## Architecture

### Circuit modules (declarative registry)

New package `viva_pulse/circuits/`:
- `base.py` holds the dataclasses:
  - `Request(port, category, name, unit, compartment=None)` maps to `pulse.cdm.engine.SEDataRequest.create_*_request`.
  - `ActionBinding(ports: dict[str, float], build(values, params) -> SEAction, validate)` is a setpoint group that becomes one action. The **whole group** is resent on any change (`Copy` replaces the full modifier set, `SEPatientActionCollection.cpp:316`). CV modifications always call `set_incremental(True)`.
  - `CircuitModule(name, model_types, outputs, bindings, params)`.
- Registry `MODULES` holds `vitals`, `hemorrhage`, `infusion` (moved from `processes.py`, which keeps re-exporting `VITALS` / `HEMORRHAGE_COMPARTMENTS`), and `cardiovascular`. Later modules: `respiratory_mechanics`, `mechanical_ventilator`, `thermal`, `ecmo`, `bag_valve_mask`, `supplemental_oxygen`, `anesthesia_machine`, `inhaler`.
- `model_types` gates validity:
  - `infusion` is `{whole_body}` only, because DrugModel is not processed on Hemodynamics.
  - The `vitals` module, which includes SpO2 and RR, is `{whole_body}` only.

### Processes

- Extract a small base (lazy engine, request dedupe by (category, compartment, property, unit), delta outputs seeded by `initial_state()`, `irreversible_state` latch, act-on-change bindings).
- **`PulseProcess` stays the unchanged WholeBody legacy subclass.** Same ports and config, and it keeps `_read_vitals()`, which `tests/test_composites.py:29` uses. The 22 tests are the guard.
- New sibling **`PulseCircuitProcess`** with config:
  - `model_type` (`whole_body` | `hemodynamics` | `ventilation_mechanics`), validated in `__init__`
  - `modules: list[string]` with `_default: []`; empty raises
  - `state_file` (WholeBody) / `patient_file` (Hemodynamics, VM: `initialize_engine`); a state file on an engine without serialization raises
  - module params merged into `config_schema` from `MODULES` at import
- Ports are **nested per module**: `outputs() -> {module: {port: "float"}}`, wired to `circuits/<module>`; setpoints go to `interventions/<module>`. One `pull_data()` per update. Actions go through `process_actions` only on change, and the result is checked (needs the `PulseEngine.py` return-bool patch).
- After the first advance, any NaN in a requested value raises, naming the request. Silent NaN ports are not allowed.
- Output contract unchanged. `float` deltas are kept on purpose (`.build-progress.md`: upstream drops `initial_state()` on `overwrite[float]`/`boolean`).
- Controllers stay separate Steps (pattern: `MapFluidController`).

### Composites

- New `viva_pulse/composites/circuits.py` gets a wiring helper (module port lists to nested store paths, plus `RAMEmitter` over the `circuits` subtree).
- `composites/hemorrhage.py` is **left untouched**.
- `pulse_cardiovascular`:
  - Parameters: `engine` (validated in the Process), `interval` (1.0 s for trends, 0.02 s for per-beat waveforms), the CV multipliers, hemorrhage site and severity.
  - `fidelity="real-bridge"`, `core_extensions=[register_processes]`.

## Phase 0: probes + engine track

Probe scripts live in the scratchpad and run with `uv run --no-sync`. **Every Hemodynamics probe and test runs in a subprocess**, because a segfault kills the interpreter or pytest. Results are recorded in `.build-progress.md`.

- P5: process-bigraph accepts nested per-module output ports with delta seeding through `initial_state()` (first emitted row equals the loaded values), plus the import-time `config_schema`.
- P3 (WholeBody): which CV/renal/tissue liquid compartments return non-NaN **after advancing**. The CV module's request list is fixed to these.
- Engine track (**optional, deferred until after Phase 1**), gated, local branch in `../engine`:
  1. Python: `PyPulse.cpp` enum value `human_adult_hemodynamics`; `PulseEngine.__init__` maps it, and unknown types raise; `process_action(s)` return the thunk bool.
  2. C++: allocate the ECG model in hemodynamics `Allocate`. Rebuild with the Innerbuild install command above. Probe advancing in a subprocess, and repeat patch then probe until a 600 s run is clean.
  3. P1: HR, MAP and CO stay physiological over 600 s; drift is reported.
  4. P4: hemorrhage lowers BV; multipliers (incremental) move MAP; infusion is inert, confirming the gate.
  5. P2 regression discriminator: `serialize_from_file("StandardMale@0s.json")` returns **False** on Hemodynamics and True on WholeBody.
  6. If it doesn't converge, stop and report to the user.
  Commits in `../engine` need user OK. The pin (branch + commit) goes in `.build-progress.md`. MR deferred.

## Phase 1: cardiovascular on whole_body (one PR)

- `circuits/cardiovascular.py`:
  - Outputs: HR, MAP, SBP, DBP, CO, stroke volume, CVP, pulmonary arterial pressure, SVR, BV, and the P3-verified compartment Pressure/Volume/InFlow, with renal and tissue as nested sub-stores.
  - Bindings: `SECardiovascularMechanicsModifiers` multipliers (`pulse/cdm/physiology.py:59+`, default 1.0, incremental) and hemorrhage.
  - Docstring cites `../engine/docs/Images/Cardiovascular/CardiovascularCircuit.png`.
- Tests, real engine, nothing mocked. Each test names the proposition it falsifies:
  - Registry (no engine): unique ports per module, defaults pass validators, unsupported module/engine combinations raise, an empty `modules` raises.
  - First emitted row equals the loaded values (nested ports).
  - Arterial resistance multiplier 2.0 gives a higher MAP than 1.0 after N s.
  - Hemorrhage lowers BV and raises HR (baroreflex on, whole_body).
  - No NaN in any requested value after 1 s.
  - The existing 22 tests pass unchanged.
- Follow-up PR, when the engine track passes:
  - `engine=hemodynamics` is enabled.
  - New tests: the P2 regression test (fails on the unpatched `PulseEngine.py`), a subprocess "advance 600 s without crash" test (fails without the ECG fix), and isolated vs coupled (HR flat on Hemodynamics, rising on whole_body under the same hemorrhage).

## Later phases (one PR each)

| Phase | Module(s) | Engine | Inputs | Notes |
|---|---|---|---|---|
| 2 | `respiratory_mechanics`, `mechanical_ventilator` | ventilation_mechanics (+ whole_body) | `SERespiratoryMechanicsConfiguration`; ventilator PC/VC/CPAP | **First probe that VM advances cleanly** (subprocess). Reference `HowTo_VentilationMechanics.py`. Diagrams `Respiratory/RespiratoryCircuit.png`, `MechanicalVentilator/MechanicalVentilatorCircuit.png` |
| 3 | `thermal` | whole_body | `SEChangeEnvironmentalConditions`, `SEThermalApplication` | Internal + External form one solve. Diagrams `Energy/internalThermal.png`, `Environment/EnvironmentCircuit.png` |
| 4 | `ecmo`, `bag_valve_mask`, `supplemental_oxygen`, `anesthesia_machine`, `inhaler` | whole_body | equipment configs | Anesthesia machine and inhaler have no Python action classes (engine-side, scoped at that phase). At most one airway device is active (`CircuitManager.cpp:191-216`) |
| 5 | `pulse_whole_body_circuits` | whole_body | union | All modules on one engine |

## Sequencing and hygiene

1. Phase 4.5 from `CURRENT.md` comes first (commit needs user OK).
2. Each phase is one branch, one PR, tests and a version bump, then a tag and release (BOJ 1 and 2). Every commit and push needs user OK.
3. `CURRENT.md` is updated at each checkpoint.

## Verification

- `uv run --no-sync pytest -q` (timeout 600000 ms): everything passes against the real engine, with Hemodynamics tests isolated in subprocesses.
- Phase 0 probe outputs recorded in `.build-progress.md`.
- `/viva-run pulse_cardiovascular` smoke run once the workspace exists.
- `/adversarial` review of each phase's diff.

## Critical files

- Modify: `viva_pulse/processes.py` (base extraction, new sibling), `viva_pulse/core.py`, `CLAUDE.md`, `.build-progress.md`, `CURRENT.md`
- Add: `viva_pulse/circuits/{__init__,base,vitals,hemorrhage,infusion,cardiovascular}.py`, `viva_pulse/composites/circuits.py`, `tests/test_circuits.py`, `docs/plan/plan-circuit-composites.md`
- Untouched: `viva_pulse/composites/hemorrhage.py`, the existing tests
- Engine (local branch): `src/python/pybind/PyPulse.cpp`, `src/python/pulse/engine/PulseEngine.py`, `src/cpp/engine/human_adult/hemodynamics/controller/Controller.cpp`
