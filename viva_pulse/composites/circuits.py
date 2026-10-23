"""Per-circuit composites driving the real Pulse engine.

Store layout:
- ``interventions/<module>/``: setpoints;
- ``circuits/<module>/``: the module's Pulse readings;
- ``circuits/irreversible_state``;
- a ``RAMEmitter`` step at ``emitter`` that emits both subtrees every update.
"""

from process_bigraph.composite_generator import composite_generator

from ..circuits.cardiovascular import CARDIOVASCULAR, HEMORRHAGE_COMPARTMENTS, MULTIPLIERS
from ..circuits.respiratory import (
    INTUBATION_TYPES, MECHANICAL_VENTILATOR, MULTIPLIERS as RESPIRATORY_MULTIPLIERS, RESPIRATORY,
    VENTILATOR_BASELINE, VENTILATOR_MODES)
from ..core import register_processes


def circuit_node(modules, *, model_type="whole_body", state_file="StandardMale@0s.json",
                 patient_file="StandardMale.json", interval=1.0, **params):
    """A ``PulseCircuitProcess`` node wired to the standard store layout."""
    return {
        "_type": "process",
        "address": "local:PulseCircuitProcess",
        "config": {"model_type": model_type, "modules": list(modules),
                   "state_file": state_file, "patient_file": patient_file, **params},
        "interval": interval,
        "inputs": {"setpoints": ["interventions"]},
        "outputs": {**{name: ["circuits", name] for name in modules},
                    "irreversible_state": ["circuits", "irreversible_state"]},
    }


def circuit_emitter():
    """A ``RAMEmitter`` recording the ``circuits`` and ``interventions`` subtrees and time."""
    return {
        "_type": "step",
        "address": "local:RAMEmitter",
        "config": {"emit": {"circuits": "node", "interventions": "node", "time": "float"}},
        "inputs": {"circuits": ["circuits"], "interventions": ["interventions"],
                   "time": ["global_time"]},
    }


def _setpoints(module, overrides, config):
    """The module's setpoint values: baselines updated from ``overrides`` (popped),
    each group validated with the same check the process applies at run time, so
    a bad parameter fails when the document is built."""
    values = {}
    for binding in module.bindings:
        group = {port: float(overrides.pop(port, default)) for port, default in binding.ports.items()}
        if binding.validate:
            binding.validate(group, config)
        values.update(group)
    return values


def _reject_unknown(overrides):
    if overrides:
        raise TypeError(f"unexpected parameters: {sorted(overrides)}")


def _multiplier_parameters(names, system):
    return {f"{name}_multiplier": {"type": "float", "default": 1.0,
                                   "description": f"Pulse {system} {name.replace('_', ' ')} multiplier (1.0 = unmodified)"}
            for name in names}


_INTERVAL = {"type": "float", "default": 1.0,
             "description": "Seconds per update; 0.02 (Pulse's timestep) resolves per-beat/per-breath "
                            "waveforms. A non-binary-exact interval can lose the final update of a run "
                            "to float time accumulation."}
_STATE_FILE = {"type": "string", "default": "StandardMale@0s.json",
               "description": "Stabilized Pulse patient state in <install>/bin/states (whole_body only)"}
_PATIENT_FILE = {"type": "string", "default": "StandardMale.json",
                 "description": "Patient in <install>/bin/patients (ventilation_mechanics only)"}


@composite_generator(
    name="pulse_cardiovascular",
    description="The Pulse cardiovascular circuit (with its renal and tissue branches) in the real "
                "whole-body engine: per-compartment pressures, volumes and flows plus hemodynamic "
                "vitals, driven by circuit resistance/compliance multipliers and a hemorrhage.",
    parameters={
        "model_type": {"type": "string", "default": "whole_body", "choices": ["whole_body"],
                       "description": "Pulse engine running the circuit"},
        "state_file": _STATE_FILE,
        "interval": _INTERVAL,
        **_multiplier_parameters(MULTIPLIERS, "cardiovascular"),
        "hemorrhage_compartment": {"type": "string", "default": "RightLeg",
                                   "choices": list(HEMORRHAGE_COMPARTMENTS),
                                   "description": "Hemorrhage site"},
        "hemorrhage_severity": {"type": "float", "default": 0.0,
                                "description": "Hemorrhage severity in [0, 1]; 0 = no bleed"},
    },
    core_extensions=[register_processes],
    default_n_steps=600,
    fidelity="real-bridge",
)
def pulse_cardiovascular(core=None, *, model_type="whole_body", state_file="StandardMale@0s.json",
                         interval=1.0, hemorrhage_compartment="RightLeg", **overrides):
    config = {"hemorrhage_compartment": hemorrhage_compartment}
    CARDIOVASCULAR.check_config(config)
    setpoints = _setpoints(CARDIOVASCULAR, overrides, config)
    _reject_unknown(overrides)
    return {
        "pulse": circuit_node(["cardiovascular"], model_type=model_type, state_file=state_file,
                              interval=interval, hemorrhage_compartment=hemorrhage_compartment),
        "interventions": {"cardiovascular": setpoints},
        "circuits": {},
        "emitter": circuit_emitter(),
    }


_RESPIRATORY_PARAMETERS = {
    "model_type": {"type": "string", "default": "ventilation_mechanics",
                   "choices": ["ventilation_mechanics", "whole_body"],
                   "description": "ventilation_mechanics = the airway circuit alone (no blood, no "
                                  "chemoreflex); whole_body = coupled to the rest of the body"},
    "patient_file": _PATIENT_FILE,
    "state_file": _STATE_FILE,
    "interval": _INTERVAL,
    **_multiplier_parameters(RESPIRATORY_MULTIPLIERS, "respiratory"),
    "intubation_type": {"type": "string", "default": "Tracheal", "choices": list(INTUBATION_TYPES),
                        "description": "Tube placement used when intubated = 1"},
}


@composite_generator(
    name="pulse_respiratory",
    description="The Pulse respiratory (airway) circuit, alone in the VentilationMechanics engine or "
                "coupled in the whole-body engine: breathing mechanics plus per-compartment lung and "
                "pleural pressures, volumes and flows, driven by resistance/compliance multipliers "
                "and intubation.",
    parameters={
        **_RESPIRATORY_PARAMETERS,
        "intubated": {"type": "float", "default": 0.0, "description": "1 = intubated, 0 = not"},
    },
    core_extensions=[register_processes],
    default_n_steps=120,
    fidelity="real-bridge",
)
def pulse_respiratory(core=None, *, model_type="ventilation_mechanics", patient_file="StandardMale.json",
                      state_file="StandardMale@0s.json", interval=1.0, intubation_type="Tracheal",
                      **overrides):
    config = {"intubation_type": intubation_type}
    RESPIRATORY.check_config(config)
    setpoints = _setpoints(RESPIRATORY, overrides, config)
    _reject_unknown(overrides)
    return {
        "pulse": circuit_node(["respiratory"], model_type=model_type, state_file=state_file,
                              patient_file=patient_file, interval=interval,
                              intubation_type=intubation_type),
        "interventions": {"respiratory": setpoints},
        "circuits": {},
        "emitter": circuit_emitter(),
    }


@composite_generator(
    name="pulse_mechanical_ventilation",
    description="A patient on a pressure-control mechanical ventilator in the real Pulse engine: the "
                "respiratory circuit combined with the ventilator circuit, emitting breathing "
                "mechanics, lung compartments and the ventilator's monitor values. Defaults follow "
                "Pulse's HowTo_VentilationMechanics (intubated; PC-AC 19/5 cmH2O, 12 bpm).",
    parameters={
        **_RESPIRATORY_PARAMETERS,
        "intubated": {"type": "float", "default": 1.0, "description": "1 = intubated (tube), 0 = mask"},
        "ventilator_mode": {"type": "string", "default": "AssistedControl", "choices": list(VENTILATOR_MODES),
                            "description": "Pressure-control mode"},
        **{port: {"type": "float", "default": (1.0 if port == "connected" else value),
                  "description": f"Ventilator {port.replace('_', ' ')}"}
           for port, value in VENTILATOR_BASELINE.items()},
    },
    core_extensions=[register_processes],
    default_n_steps=120,
    fidelity="real-bridge",
)
def pulse_mechanical_ventilation(core=None, *, model_type="ventilation_mechanics",
                                 patient_file="StandardMale.json", state_file="StandardMale@0s.json",
                                 interval=1.0, intubation_type="Tracheal",
                                 ventilator_mode="AssistedControl", **overrides):
    overrides.setdefault("intubated", 1.0)
    overrides.setdefault("connected", 1.0)
    config = {"intubation_type": intubation_type, "ventilator_mode": ventilator_mode}
    RESPIRATORY.check_config(config)
    MECHANICAL_VENTILATOR.check_config(config)
    respiratory = _setpoints(RESPIRATORY, overrides, config)
    ventilator = _setpoints(MECHANICAL_VENTILATOR, overrides, config)
    _reject_unknown(overrides)
    return {
        "pulse": circuit_node(["respiratory", "mechanical_ventilator"], model_type=model_type,
                              state_file=state_file, patient_file=patient_file, interval=interval,
                              **config),
        "interventions": {"respiratory": respiratory, "mechanical_ventilator": ventilator},
        "circuits": {},
        "emitter": circuit_emitter(),
    }
