"""Thermal circuit module: Pulse's internal and external temperature circuits.

Pulse solves body heat as one circuit: the internal circuit (core and skin)
joined to the external one (clothing, enclosure, ambient air, plus the
applied-temperature node). Diagrams: ``engine/docs/Images/Energy/internalThermal.png``
and ``engine/docs/Images/Environment/EnvironmentCircuit.png``. The circuit
couples to the cardiovascular one through skin blood flow, and the nervous
model drives shivering and sweating, so it runs on the WholeBody engine only.

Readings:

- ``energy``: core and skin temperature, sweat rate and total metabolic rate
  (``SEEnergySystem``).
- ``heat_loss``: the environment's heat-loss rates and transfer coefficients
  (``SEEnvironment``). A negative loss is a net gain, e.g. under active
  heating or in air warmer than the skin.
- ``environment``: the environmental conditions Pulse is using, read back from
  the engine, so a setpoint change is visible once applied.
- ``compartments``: temperature-circuit compartments. Temperature for the
  seven with a physical temperature; stored heat only for ``internal_core``
  and ``internal_skin``, the only ones for which Pulse returns it; heat flow in
  and out for those seven plus ``active``, the applied-temperature node. Pulse
  reads ``active``'s temperature as 0 K while no temperature is applied, so it
  is not exposed. Neither are the reference nodes: ``ExternalGround`` reads
  0 K (absolute zero) and ``InternalGround`` returns NaN.

Thermal changes are slow. From the StandardMale state, skin temperature moves
within minutes, but core temperature takes tens of minutes. The loaded state
is not thermally settled: unperturbed, skin temperature drifts from 32.4 to
30.0 °C over 30 minutes while core temperature rises by 0.06 °C. Compare
interventions against an unperturbed run, not against t = 0.

Setpoints:

- ``environment`` group: ambient and mean radiant temperature, the
  temperature of the air breathed, relative humidity, air velocity and
  clothing resistance. Pulse keeps the breathed-air temperature separate
  (``RespirationAmbientTemperature`` drives respiration heat loss) and does
  not follow the ambient temperature, so set both for a change of air. They are
  sent as one ``SEChangeEnvironmentalConditions``, which Pulse merges into the
  current conditions (merge type Append); the atmosphere and ambient gases
  are left alone. The baselines are Pulse's ``environments/Standard.json``,
  which every shipped state file uses. The group is always sent whole, so a
  state whose environment differs from the baselines would be silently reset on
  the first change; such a state fails the load instead (``check_loaded``).
- ``thermal_application`` group: active heating and cooling power, each with
  the fraction of skin area it covers, plus an applied temperature (on/off,
  temperature, area fraction). Pulse replaces the whole application on every
  action, so the group is always sent complete. Pulse applies
  ``power * area_fraction`` as net heat, so with fraction 1.0 the power is the
  heat delivered. The applied temperature is a temperature source on the
  clothing node set to ``applied * fraction + ambient * (1 - fraction)``
  (``EnvironmentModel.cpp``). Zero power and the applied temperature off
  together remove the application.
"""

from __future__ import annotations

from typing import Any

from .base import ActionBinding, CircuitModule, Request, validate_switch

_C = ("TemperatureUnit", "C")
_W = ("PowerUnit", "W")
_kJ = ("EnergyUnit", "kJ")
_g_per_min = ("MassPerTimeUnit", "g_Per_min")
_W_per_m2_K = ("HeatConductancePerAreaUnit", "W_Per_m2_K")
_m_per_s = ("LengthPerTimeUnit", "m_Per_s")
_clo = ("HeatResistanceAreaUnit", "clo")
_mmHg = ("PressureUnit", "mmHg")

# port -> (SEEnergySystem property, unit)
_ENERGY = {
    "core_temperature_C": ("CoreTemperature", _C),
    "skin_temperature_C": ("SkinTemperature", _C),
    "sweat_rate_g_per_min": ("SweatRate", _g_per_min),
    "total_metabolic_rate_W": ("TotalMetabolicRate", _W),
}

# port -> (SEEnvironment property, unit). Pulse spells "Tranfer" this way.
_HEAT_LOSS = {
    "skin_W": ("SkinHeatLoss", _W),
    "convective_W": ("ConvectiveHeatLoss", _W),
    "radiative_W": ("RadiativeHeatLoss", _W),
    "evaporative_W": ("EvaporativeHeatLoss", _W),
    "respiration_W": ("RespirationHeatLoss", _W),
    "convective_coefficient_W_per_m2_K": ("ConvectiveHeatTranferCoefficient", _W_per_m2_K),
    "radiative_coefficient_W_per_m2_K": ("RadiativeHeatTranferCoefficient", _W_per_m2_K),
    "evaporative_coefficient_W_per_m2_K": ("EvaporativeHeatTranferCoefficient", _W_per_m2_K),
}

# port -> (SEEnvironmentalConditions property, read through the environment request, unit)
_CONDITIONS = {
    "ambient_temperature_C": ("AmbientTemperature", _C),
    "mean_radiant_temperature_C": ("MeanRadiantTemperature", _C),
    "respiration_ambient_temperature_C": ("RespirationAmbientTemperature", _C),
    "relative_humidity": ("RelativeHumidity", None),
    "air_velocity_m_per_s": ("AirVelocity", _m_per_s),
    "clothing_resistance_clo": ("ClothingResistance", _clo),
    "atmospheric_pressure_mmHg": ("AtmosphericPressure", _mmHg),
}

# store name -> Pulse thermal compartment (engine/PulseEngine.h TemperatureCompartment)
_COMPARTMENTS = {
    "internal_core": "InternalCore",
    "internal_skin": "InternalSkin",
    "external_core": "ExternalCore",
    "external_skin": "ExternalSkin",
    "clothing": "Clothing",
    "enclosure": "Enclosure",
    "ambient": "Ambient",
}
_HEAT_COMPARTMENTS = ("internal_core", "internal_skin")
_ACTIVE = ("active", "Active")

ENVIRONMENT_BASELINE = {
    "ambient_temperature_C": 22.0,
    "mean_radiant_temperature_C": 22.0,
    "respiration_ambient_temperature_C": 22.0,
    "relative_humidity": 0.6,
    "air_velocity_m_per_s": 0.1,
    "clothing_resistance_clo": 0.5,
}

THERMAL_APPLICATION_BASELINE = {
    "active_heating_W": 0.0,
    "active_heating_area_fraction": 1.0,
    "active_cooling_W": 0.0,
    "active_cooling_area_fraction": 1.0,
    "applied_temperature_on": 0.0,
    "applied_temperature_C": 22.0,
    "applied_temperature_area_fraction": 1.0,
}

_ABSOLUTE_ZERO_C = -273.15


def _thermal_outputs() -> tuple[Request, ...]:
    requests = [Request(("energy", port), "physiology", prop, unit)
                for port, (prop, unit) in _ENERGY.items()]
    requests += [Request(("heat_loss", port), "environment", prop, unit)
                 for port, (prop, unit) in _HEAT_LOSS.items()]
    requests += [Request(("environment", port), "environment", f"EnvironmentalConditions-{prop}", unit)
                 for port, (prop, unit) in _CONDITIONS.items()]
    for name, compartment in (*_COMPARTMENTS.items(), _ACTIVE):
        if name != "active":
            requests.append(Request(("compartments", name, "temperature_C"), "thermal_compartment",
                                    "Temperature", _C, compartment=compartment))
        if name in _HEAT_COMPARTMENTS:
            requests.append(Request(("compartments", name, "heat_kJ"), "thermal_compartment",
                                    "Heat", _kJ, compartment=compartment))
        requests.append(Request(("compartments", name, "heat_in_W"), "thermal_compartment",
                                "HeatTransferRateIn", _W, compartment=compartment))
        requests.append(Request(("compartments", name, "heat_out_W"), "thermal_compartment",
                                "HeatTransferRateOut", _W, compartment=compartment))
    return tuple(requests)


def _check_temperature(port: str, value: float) -> None:
    if not value > _ABSOLUTE_ZERO_C:
        raise ValueError(f"{port} must be above absolute zero ({_ABSOLUTE_ZERO_C} C), got {value}")


def _check_fraction(port: str, value: float) -> None:
    if not 0.0 < value <= 1.0:
        raise ValueError(f"{port} must be in (0, 1], got {value}")


def _validate_environment(values: dict[str, float], config: dict[str, Any]) -> None:
    _check_temperature("ambient_temperature_C", values["ambient_temperature_C"])
    _check_temperature("mean_radiant_temperature_C", values["mean_radiant_temperature_C"])
    _check_temperature("respiration_ambient_temperature_C", values["respiration_ambient_temperature_C"])
    if not 0.0 <= values["relative_humidity"] <= 1.0:
        raise ValueError(f"relative_humidity must be in [0, 1], got {values['relative_humidity']}")
    for port in ("air_velocity_m_per_s", "clothing_resistance_clo"):
        if not values[port] >= 0.0:
            raise ValueError(f"{port} must be >= 0, got {values[port]}")


def _build_environment(values: dict[str, float], config: dict[str, Any]):
    from pulse.cdm.environment_actions import SEChangeEnvironmentalConditions
    from pulse.cdm.scalars import HeatResistanceAreaUnit, LengthPerTimeUnit, TemperatureUnit

    action = SEChangeEnvironmentalConditions()
    conditions = action.get_environmental_conditions()
    conditions.get_ambient_temperature().set_value(values["ambient_temperature_C"], TemperatureUnit.C)
    conditions.get_mean_radiant_temperature().set_value(values["mean_radiant_temperature_C"], TemperatureUnit.C)
    conditions.get_respiration_ambient_temperature().set_value(
        values["respiration_ambient_temperature_C"], TemperatureUnit.C)
    conditions.get_relative_humidity().set_value(values["relative_humidity"])
    conditions.get_air_velocity().set_value(values["air_velocity_m_per_s"], LengthPerTimeUnit.m_Per_s)
    conditions.get_clothing_resistance().set_value(values["clothing_resistance_clo"], HeatResistanceAreaUnit.clo)
    return action


def _validate_thermal_application(values: dict[str, float], config: dict[str, Any]) -> None:
    for port in ("active_heating_W", "active_cooling_W"):
        if not values[port] >= 0.0:
            raise ValueError(f"{port} must be >= 0, got {values[port]}")
    for port in ("active_heating_area_fraction", "active_cooling_area_fraction",
                 "applied_temperature_area_fraction"):
        _check_fraction(port, values[port])
    validate_switch("applied_temperature_on", values["applied_temperature_on"])
    _check_temperature("applied_temperature_C", values["applied_temperature_C"])


def _build_thermal_application(values: dict[str, float], config: dict[str, Any]):
    from pulse.cdm.enums import eSwitch
    from pulse.cdm.environment_actions import SEThermalApplication
    from pulse.cdm.scalars import PowerUnit, TemperatureUnit

    action = SEThermalApplication()
    for part, prefix in ((action.get_active_heating(), "active_heating"),
                         (action.get_active_cooling(), "active_cooling")):
        part.get_power().set_value(values[f"{prefix}_W"], PowerUnit.W)
        part.get_surface_area_fraction().set_value(values[f"{prefix}_area_fraction"])
    applied = action.get_applied_temperature()
    applied.set_state(eSwitch.On if values["applied_temperature_on"] == 1.0 else eSwitch.Off)
    applied.get_temperature().set_value(values["applied_temperature_C"], TemperatureUnit.C)
    applied.get_surface_area_fraction().set_value(values["applied_temperature_area_fraction"])
    return action


def _check_loaded_environment(readings: dict[str, Any]) -> None:
    loaded = readings["environment"]
    mismatched = {port: loaded[port] for port, value in ENVIRONMENT_BASELINE.items()
                  if abs(loaded[port] - value) > 1e-9}
    if mismatched:
        raise ValueError(
            f"the loaded state's environment differs from the thermal module's baselines "
            f"(Pulse's Standard.json) at {mismatched}; the first environment change would "
            f"silently reset them to {ENVIRONMENT_BASELINE}")


THERMAL = CircuitModule(
    name="thermal",
    model_types=frozenset({"whole_body"}),
    outputs=_thermal_outputs(),
    bindings=(
        ActionBinding(ports=dict(ENVIRONMENT_BASELINE),
                      build=_build_environment, validate=_validate_environment),
        ActionBinding(ports=dict(THERMAL_APPLICATION_BASELINE),
                      build=_build_thermal_application, validate=_validate_thermal_application),
    ),
    check_loaded=_check_loaded_environment,
)
