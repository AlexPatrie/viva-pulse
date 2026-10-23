# Circuits

`PulseCircuitProcess` exposes Pulse's circuits through **circuit modules**, defined in
`viva_pulse.circuits`. A module computes nothing. It names the Pulse values that become its
output ports and the Pulse actions its setpoints drive.

| Module | Engines | Readings | Setpoints |
|---|---|---|---|
| `cardiovascular` | whole_body | 20 hemodynamic values; pressure, volume, inflow and outflow for 32 regions under `central/`, `renal/`, `peripheral/` | 10 resistance and compliance multipliers; a hemorrhage |
| `respiratory` | both | 24 breathing-mechanics values; lung and pleural regions | 10 resistance and compliance multipliers; intubation |
| `mechanical_ventilator` | both | 18 ventilator monitor values | one pressure-control group, including `connected` |
| `thermal` | whole_body | energy, heat loss, the environment as applied, thermal regions | the environment; active heating, cooling or an applied temperature |
| `supplemental_oxygen` | whole_body | inspired oxygen fraction, SpO2, PaO2, PaCO2 | `oxygen_connected`, `oxygen_flow_L_per_min` |

Every module's setpoints are applied as Pulse actions. Multipliers are always sent as an
incremental change of the whole group, because a non-incremental change makes Pulse
re-stabilize and reset its baselines.

## The cardiovascular circuit

The `central`, `renal` and `peripheral` stores follow the diagram's branches.

```{image} ../../docs/images/circuit-cardio.png
:alt: Pulse cardiovascular circuit
```

*Pulse cardiovascular circuit. Copyright Kitware, Inc. and Contributors, Apache License 2.0,
from `engine/docs/Images/Cardiovascular/CardiovascularCircuit.png`.*

Region readings are instantaneous within each heartbeat. The default one-second sampling
aliases the cardiac cycle; use `interval=0.02` (Pulse's timestep) to resolve waveforms, as
{doc}`../tutorials/02-cardiovascular-circuit` does.

## The thermal circuit

```{image} ../../docs/images/circuit-environment.png
:alt: Pulse environment circuit
```

*Pulse environment circuit, the external half of the temperature circuit. Copyright Kitware,
Inc. and Contributors, Apache License 2.0, from
`engine/docs/Images/Environment/EnvironmentCircuit.png`.*

Skin responds within minutes; core temperature takes tens of minutes. Pulse's stabilized
states aren't thermally settled (skin drifts from 32.4 to 30.0 °C over 30 minutes with nothing
changed), so compare a thermal intervention against an unperturbed run.

## Rules that come from Pulse

- **One airway device at a time.** With the ventilator and supplemental oxygen both connected,
  every engine step fails, so the process raises an error instead. To switch devices,
  disconnect one in an update before connecting the other.
- **Intubation is one-way.** Pulse's Python API drops extubation, so setting `intubated` back
  to 0 raises an error rather than leaving the store and the engine disagreeing.
- **The ventilator in `AssistedControl` mode** can lock into auto-triggering at a rate above
  the patient's own. Use `ContinuousMandatoryVentilation` when the set rate must hold.
- **Supplemental oxygen comes from a wall supply.** A finite bottle would refill every time a
  setpoint change resends the action.
- **Hemodynamics, Pulse's cardiovascular-only engine, isn't supported**: it crashes on its
  first step. So the cardiovascular circuit runs inside the whole body only.
