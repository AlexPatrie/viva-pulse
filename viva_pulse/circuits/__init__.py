"""Registry of Pulse circuit modules available to ``PulseCircuitProcess``."""

from .base import ENGINE_MODEL_TYPES, ActionBinding, CircuitModule, Request
from .cardiovascular import CARDIOVASCULAR
from .respiratory import MECHANICAL_VENTILATOR, RESPIRATORY

MODULES: dict[str, CircuitModule] = {
    m.name: m for m in (CARDIOVASCULAR, RESPIRATORY, MECHANICAL_VENTILATOR)
}

__all__ = ["ENGINE_MODEL_TYPES", "ActionBinding", "CircuitModule", "MODULES", "Request"]
