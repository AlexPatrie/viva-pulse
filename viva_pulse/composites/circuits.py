"""Per-circuit composites driving the real Pulse engine.

Store layout:
- ``interventions/<module>/``: setpoints;
- ``circuits/<module>/``: the module's Pulse readings;
- ``circuits/irreversible_state``;
- a ``RAMEmitter`` step at ``emitter`` that emits both subtrees every update.
"""

from process_bigraph.composite_generator import composite_generator

from ..circuits.cardiovascular import CARDIOVASCULAR, HEMORRHAGE_COMPARTMENTS, MULTIPLIERS
from ..core import register_processes


def circuit_node(modules, *, model_type="whole_body", state_file="StandardMale@0s.json",
                 interval=1.0, **params):
    """A ``PulseCircuitProcess`` node wired to the standard store layout."""
    return {
        "_type": "process",
        "address": "local:PulseCircuitProcess",
        "config": {"model_type": model_type, "modules": list(modules),
                   "state_file": state_file, **params},
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


_MULTIPLIER_PARAMETERS = {
    f"{name}_multiplier": {"type": "float", "default": 1.0,
                           "description": f"Pulse cardiovascular {name.replace('_', ' ')} multiplier (1.0 = unmodified)"}
    for name in MULTIPLIERS
}


@composite_generator(
    name="pulse_cardiovascular",
    description="The Pulse cardiovascular circuit (with its renal and tissue branches) in the real "
                "whole-body engine: per-compartment pressures, volumes and flows plus hemodynamic "
                "vitals, driven by circuit resistance/compliance multipliers and a hemorrhage.",
    parameters={
        "model_type": {"type": "string", "default": "whole_body", "choices": ["whole_body"],
                       "description": "Pulse engine running the circuit"},
        "state_file": {"type": "string", "default": "StandardMale@0s.json",
                       "description": "Stabilized Pulse patient state in <install>/bin/states"},
        "interval": {"type": "float", "default": 1.0,
                     "description": "Seconds per update; 0.02 (Pulse's timestep) resolves per-beat "
                                    "waveforms. A non-binary-exact interval can lose the final "
                                    "update of a run to float time accumulation."},
        **_MULTIPLIER_PARAMETERS,
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
                         interval=1.0, hemorrhage_compartment="RightLeg", hemorrhage_severity=0.0,
                         **multipliers):
    setpoints = {f"{name}_multiplier": float(multipliers.pop(f"{name}_multiplier", 1.0))
                 for name in MULTIPLIERS}
    if multipliers:
        raise TypeError(f"unexpected parameters: {sorted(multipliers)}")
    setpoints["hemorrhage_severity"] = float(hemorrhage_severity)
    # Fail at document build time, with the same checks the process applies at run time.
    CARDIOVASCULAR.check_config({"hemorrhage_compartment": hemorrhage_compartment})
    for binding in CARDIOVASCULAR.bindings:
        binding.validate({port: setpoints[port] for port in binding.ports}, {})
    return {
        "pulse": circuit_node(["cardiovascular"], model_type=model_type, state_file=state_file,
                              interval=interval, hemorrhage_compartment=hemorrhage_compartment),
        "interventions": {"cardiovascular": setpoints},
        "circuits": {},
        "emitter": circuit_emitter(),
    }
