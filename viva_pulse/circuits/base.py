"""Declarative description of one Pulse circuit family as process-bigraph ports.

A ``CircuitModule`` names the Pulse data requests that become its output ports
and the Pulse actions that its setpoint input ports drive. It computes nothing:
``PulseCircuitProcess`` turns the selected modules into ports, requests and
actions against one real Pulse engine.

Pulse's Python package is importable only after ``ensure_pulse_importable()``,
so units and actions are resolved lazily, at engine-load time.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable

ENGINE_MODEL_TYPES = ("whole_body", "hemodynamics", "ventilation_mechanics")

# Top-level port names of PulseCircuitProcess that a module name must not shadow.
RESERVED_NAMES = frozenset({"setpoints", "irreversible_state"})


@dataclass(frozen=True)
class Request:
    """One Pulse data request, emitted at ``path`` inside its module's port tree.

    ``category`` is ``"physiology"``, ``"environment"``, ``"liquid_compartment"``,
    ``"gas_compartment"``, ``"thermal_compartment"`` or ``"mechanical_ventilator"``.
    ``unit`` is ``(unit class in pulse.cdm.scalars, unit attribute)``, or None for
    unitless. Compartment property names are Pulse's own spelling: ``Pressure``,
    ``Volume``, ``Inflow``, ``Outflow`` (``SEDataRequestTracker.cpp``), and
    ``Temperature``, ``Heat``, ``HeatTransferRateIn``, ``HeatTransferRateOut``
    for thermal compartments (``SEThermalCompartment.cpp``).
    """

    path: tuple[str, ...]
    category: str
    property: str
    unit: tuple[str, str] | None
    compartment: str | None = None

    def key(self) -> tuple:
        """Identity of the underlying Pulse request; equal keys share one request."""
        return (self.category, self.compartment, self.property, self.unit)

    def to_pulse(self):
        from pulse.cdm import scalars
        from pulse.cdm.engine import SEDataRequest

        unit = getattr(getattr(scalars, self.unit[0]), self.unit[1]) if self.unit else None
        if self.category == "physiology":
            return SEDataRequest.create_physiology_request(self.property, unit=unit)
        if self.category == "environment":
            return SEDataRequest.create_environment_request(self.property, unit=unit)
        if self.category == "liquid_compartment":
            return SEDataRequest.create_liquid_compartment_request(
                self.compartment, self.property, unit=unit)
        if self.category == "gas_compartment":
            return SEDataRequest.create_gas_compartment_request(
                self.compartment, self.property, unit=unit)
        if self.category == "thermal_compartment":
            return SEDataRequest.create_thermal_compartment_request(
                self.compartment, self.property, unit=unit)
        if self.category == "mechanical_ventilator":
            return SEDataRequest.create_mechanical_ventilator_request(self.property, unit=unit)
        raise ValueError(f"unsupported data request category {self.category!r}")


@dataclass(frozen=True)
class ActionBinding:
    """A group of setpoint ports forwarded to Pulse as one action.

    ``ports`` maps each port name to its baseline value (the value at which no
    action is needed). Whenever any port in the group changes, ``build`` is
    called with every port's current value plus the process config and returns
    the Pulse action to send. ``validate`` raises ``ValueError`` on bad values;
    ``check_transition(previous, values)`` raises ``ValueError`` on a change
    Pulse cannot make (e.g. one its Python API silently drops).
    """

    ports: dict[str, float]
    build: Callable[[dict[str, float], dict[str, Any]], Any]
    validate: Callable[[dict[str, float], dict[str, Any]], None] | None = None
    check_transition: Callable[[dict[str, float], dict[str, float]], None] | None = None


def validate_switch(port: str, value: float) -> None:
    """A 0/1 setpoint."""
    if value not in (0.0, 1.0):
        raise ValueError(f"{port} must be 0 or 1, got {value}")


@dataclass(frozen=True)
class CircuitModule:
    """One circuit family: its outputs, its setpoint bindings, its config params.

    ``model_types`` lists the Pulse engines (``ENGINE_MODEL_TYPES``) on which
    every request and action of this module is supported. ``params`` are
    ``config_schema`` entries that ``PulseCircuitProcess`` exposes, and
    ``check_config`` validates them, raising ``ValueError``. ``check_loaded``
    receives the module's readings (nested like its outputs) once the engine is
    loaded, and raises ``ValueError`` if the loaded state contradicts the
    module's setpoint baselines. ``airway_device`` names the module's 0/1
    setpoint that is 1 while its equipment occupies Pulse's airway: Pulse
    allows one airway device at a time and stalls when a second one connects.
    """

    name: str
    model_types: frozenset[str]
    outputs: tuple[Request, ...]
    bindings: tuple[ActionBinding, ...] = ()
    params: dict[str, dict[str, Any]] = field(default_factory=dict)
    check_config: Callable[[dict[str, Any]], None] | None = None
    check_loaded: Callable[[dict[str, Any]], None] | None = None
    airway_device: str | None = None

    def __post_init__(self):
        if self.name in RESERVED_NAMES:
            raise ValueError(f"circuit module name {self.name!r} is reserved")
        unknown = self.model_types - set(ENGINE_MODEL_TYPES)
        if unknown:
            raise ValueError(f"{self.name}: unknown model types {sorted(unknown)}")
        paths = [r.path for r in self.outputs]
        if len(set(paths)) != len(paths):
            raise ValueError(f"{self.name}: duplicate output paths")
        for a in paths:
            for b in paths:
                if a != b and b[: len(a)] == a:
                    raise ValueError(f"{self.name}: output path {a} is a prefix of {b}")
        ports = [p for b in self.bindings for p in b.ports]
        if len(set(ports)) != len(ports):
            raise ValueError(f"{self.name}: duplicate setpoint ports")
        if self.airway_device is not None and self.airway_device not in ports:
            raise ValueError(f"{self.name}: airway_device {self.airway_device!r} is not a setpoint port")
