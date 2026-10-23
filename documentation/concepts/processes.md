# Processes

viva-pulse has three process-bigraph components. Register them on a core with
`viva_pulse.core.build_core()`, which registers them explicitly, because process-bigraph's
automatic discovery can miss editable installs.

## `PulseProcess`: whole-body vital signs

Loads a stabilized Pulse state (default `StandardMale@0s.json`) the first time it's used, then
advances the engine by `interval` seconds per update.

- **Inputs** `hemorrhage_severity` and `iv_rate_mL_per_min` are setpoints, sent to Pulse as
  actions only when they change. The bleed site is the `hemorrhage_compartment` config and the
  infused fluid the `iv_compound` config (a compound Pulse ships, such as `Saline` or `Blood`;
  an unknown one fails when the engine loads).
- **Outputs** are nine vital signs plus an `irreversible_state` flag.

The vital-sign outputs are delta ports. `initial_state()` seeds each store with the reading
Pulse loaded, and every update emits the change since the last one, so the store always
equals Pulse's own value. This is deliberate: process-bigraph discards `initial_state()`
values on `overwrite[float]` and `boolean` output ports, which would make the first row zero.

Once Pulse reports an irreversible state, the process stops advancing the engine and its
updates return nothing, so the vitals keep their last reading while time continues.

## `PulseCircuitProcess`: circuits, region by region

One real Pulse engine exposing the circuit modules named in `config.modules` (see
{doc}`circuits`).

- Each module's readings form a nested subtree of delta ports, for example
  `cardiovascular/central/aorta/pressure_mmHg`.
- Its setpoints sit under the single input port `setpoints`, for example
  `setpoints/cardiovascular/hemorrhage_severity`. Each defaults to its baseline (multipliers
  1.0, no bleed), so an omitted setpoint never becomes 0.
- Identical requests from several modules share one Pulse request. A request Pulse can't serve
  returns NaN, so the process fails the load, or the update where it appears, instead of
  emitting NaN.
- `model_type` picks the engine. `whole_body` loads a `state_file`. `ventilation_mechanics`
  (airway only) has no state files: it starts from a `patient_file` and settles, in one-second
  steps, until every requested value is defined. Setting the file the chosen engine doesn't
  use raises an error.

Inputs and outputs use different top-level names on purpose: process-bigraph projects
`initial_state()` through input wires too, so a shared name would copy readings into the
setpoint store.

## `MapFluidController`: a closed-loop Step

A proportional controller. It sets the IV infusion rate to
`gain_mL_per_min_per_mmHg × (target_map_mmHg − MAP)`, clipped to
`[0, max_rate_mL_per_min]`. It is a process-bigraph `Step` that reads one store and writes
another, so the same pattern gives any closed-loop controller: read a circuit's outputs, write
its setpoints. {doc}`../tutorials/01-hemorrhage-and-resuscitation` runs it.
