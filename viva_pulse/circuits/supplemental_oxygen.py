"""Supplemental oxygen module: a nasal cannula, simple mask or non-rebreather mask.

Pulse models each device as a small gas circuit combined with the respiratory
circuit (``CircuitManager::GetActiveRespiratoryCircuit``, airway modes
``NasalCannula``, ``SimpleMask`` and ``NonRebreatherMask``). It runs on the
WholeBody engine, which has the blood gases the readings report.

Readings (``oxygenation``): the inspired oxygen fraction and the arterial blood
gases, which is what supplemental oxygen changes. The devices' own gas
compartments are not exposed: Pulse returns NaN for some of them while the
device is off (the nasal cannula's pressure), and their volumes are constant.

Setpoints: one group, sent as ``SESupplementalOxygen``.

- ``oxygen_connected`` (0/1) with ``oxygen_flow_L_per_min``. The device type
  is config ``oxygen_device``. Disconnecting sends device ``None``, which
  Pulse treats as removal (``RespiratoryModel::SupplementalOxygen``).
- The supply is a wall connection (infinite volume). Pulse also models a
  finite bottle that runs down at the set flow, but the whole group is resent
  on every change, so each change would refill it. Bottle depletion is not
  exposed.
- Pulse allows one airway device at a time. Connecting oxygen while the
  mechanical ventilator is connected makes every advance fail ("Can only change
  airway mode from the Free mode, Disable other equipment first"). The module
  therefore declares ``oxygen_connected`` as its ``airway_device``, and
  ``PulseCircuitProcess`` rejects two connected devices, and a device
  connecting in the same update another one disconnects.
"""

from __future__ import annotations

import math
from typing import Any

from .base import ActionBinding, CircuitModule, Request, validate_switch

OXYGEN_DEVICES = ("NasalCannula", "SimpleMask", "NonRebreatherMask")

_mmHg = ("PressureUnit", "mmHg")

# port -> (physiology property, unit)
_OXYGENATION = {
    "fraction_inspired_oxygen": ("FractionOfInspiredOxygen", None),
    "oxygen_saturation": ("OxygenSaturation", None),
    "arterial_oxygen_pressure_mmHg": ("ArterialOxygenPressure", _mmHg),
    "arterial_carbon_dioxide_pressure_mmHg": ("ArterialCarbonDioxidePressure", _mmHg),
}

# Pulse's own default flow for a nasal cannula (RespiratoryModel::SupplementalOxygen).
OXYGEN_BASELINE = {
    "oxygen_connected": 0.0,
    "oxygen_flow_L_per_min": 3.5,
}


def _validate_oxygen(values: dict[str, float], config: dict[str, Any]) -> None:
    validate_switch("oxygen_connected", values["oxygen_connected"])
    flow = values["oxygen_flow_L_per_min"]
    if not (flow > 0.0 and math.isfinite(flow)):
        raise ValueError(f"oxygen_flow_L_per_min must be a finite value > 0, got {flow}")


def _build_oxygen(values: dict[str, float], config: dict[str, Any]):
    from pulse.cdm.patient_actions import SESupplementalOxygen, eDevice
    from pulse.cdm.scalars import VolumePerTimeUnit, VolumeUnit

    action = SESupplementalOxygen()
    connected = values["oxygen_connected"] == 1.0
    action.set_device(eDevice[config["oxygen_device"]] if connected else eDevice.NullDevice)
    # Pulse's Python is_valid() requires flow and volume even for device None.
    action.get_flow().set_value(values["oxygen_flow_L_per_min"], VolumePerTimeUnit.L_Per_min)
    action.get_volume().set_value(math.inf, VolumeUnit.L)
    return action


def _check_oxygen_config(config: dict[str, Any]) -> None:
    if config["oxygen_device"] not in OXYGEN_DEVICES:
        raise ValueError(f"oxygen_device must be one of {OXYGEN_DEVICES}, got {config['oxygen_device']!r}")


SUPPLEMENTAL_OXYGEN = CircuitModule(
    name="supplemental_oxygen",
    model_types=frozenset({"whole_body"}),
    outputs=tuple(Request(("oxygenation", port), "physiology", prop, unit)
                  for port, (prop, unit) in _OXYGENATION.items()),
    bindings=(
        ActionBinding(ports=dict(OXYGEN_BASELINE), build=_build_oxygen, validate=_validate_oxygen),
    ),
    params={"oxygen_device": {"_type": "string", "_default": "NasalCannula"}},
    check_config=_check_oxygen_config,
    airway_device="oxygen_connected",
)
