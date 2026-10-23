"""Process-bigraph bridge to the Kitware Pulse Physiology Engine."""

from __future__ import annotations

from typing import Any

from process_bigraph import Process, Step

from .runtime import ensure_pulse_importable

# Output port -> (Pulse physiology property, unit attribute on the scalar unit
# class named in the second slot, or None for unitless). Order is the
# data-request order, which is the order of PulseEngine.pull_data()[1:].
VITALS: dict[str, tuple[str, str | None, str | None]] = {
    "heart_rate_bpm": ("HeartRate", "FrequencyUnit", "Per_min"),
    "mean_arterial_pressure_mmHg": ("MeanArterialPressure", "PressureUnit", "mmHg"),
    "systolic_pressure_mmHg": ("SystolicArterialPressure", "PressureUnit", "mmHg"),
    "diastolic_pressure_mmHg": ("DiastolicArterialPressure", "PressureUnit", "mmHg"),
    "oxygen_saturation": ("OxygenSaturation", None, None),
    "respiration_rate_bpm": ("RespirationRate", "FrequencyUnit", "Per_min"),
    "cardiac_output_L_per_min": ("CardiacOutput", "VolumePerTimeUnit", "L_Per_min"),
    "blood_volume_mL": ("BloodVolume", "VolumeUnit", "mL"),
    "total_hemorrhaged_volume_mL": ("TotalHemorrhagedVolume", "VolumeUnit", "mL"),
}

HEMORRHAGE_COMPARTMENTS = (
    "Aorta", "Brain", "Muscle", "LargeIntestine", "LeftArm", "LeftKidney",
    "LeftLeg", "Liver", "RightArm", "RightKidney", "RightLeg", "Skin",
    "SmallIntestine", "Splanchnic", "Spleen", "VenaCava",
)


class PulseProcess(Process):
    """Time-stepped bridge to the real Pulse whole-body adult engine.

    The engine is loaded from a stabilized Pulse state file and advanced by
    ``interval`` seconds on every update. Interventions arrive as setpoints on
    the input ports and are forwarded to Pulse as patient actions only when
    their value changes.

    Inputs
    ------
    hemorrhage_severity : overwrite[float]
        Hemorrhage severity in [0, 1] at ``config.hemorrhage_compartment``;
        0 stops the bleed.
    iv_rate_mL_per_min : overwrite[float]
        Infusion rate of ``config.iv_compound`` (e.g. Saline, Blood); 0 stops it.

    Outputs
    -------
    Vital signs (see ``VITALS``) as ``float``. Pulse reports absolute values;
    ``initial_state()`` seeds each store with the loaded state's reading and
    every update emits ``current - previous``, so the store always equals
    Pulse's own value and composes additively with sibling writers.
    ``irreversible_state`` turns True once Pulse reports an irreversible
    state; the engine is not advanced after that, so the vitals stores keep
    the last reading Pulse produced.
    """

    config_schema = {
        "state_file": {"_type": "string", "_default": "StandardMale@0s.json"},
        "install_dir": {"_type": "string", "_default": ""},
        "hemorrhage_compartment": {"_type": "string", "_default": "RightLeg"},
        "iv_compound": {"_type": "string", "_default": "Saline"},
        "iv_bag_volume_L": {"_type": "float", "_default": 10.0},
    }

    def __init__(self, config=None, core=None):
        super().__init__(config=config, core=core)
        if self.config["hemorrhage_compartment"] not in HEMORRHAGE_COMPARTMENTS:
            raise ValueError(
                f"hemorrhage_compartment must be one of {HEMORRHAGE_COMPARTMENTS}, "
                f"got {self.config['hemorrhage_compartment']!r}"
            )
        self._engine = None
        self._alive = True
        self._applied: dict[str, float] = {"hemorrhage_severity": 0.0, "iv_rate_mL_per_min": 0.0}
        self._previous: dict[str, float] = {}

    def inputs(self):
        return {
            "hemorrhage_severity": "overwrite[float]",
            "iv_rate_mL_per_min": "overwrite[float]",
        }

    def outputs(self):
        ports: dict[str, Any] = {name: "float" for name in VITALS}
        ports["irreversible_state"] = "boolean"
        return ports

    def initial_state(self):
        return {
            "hemorrhage_severity": 0.0,
            "iv_rate_mL_per_min": 0.0,
            **self._previous_readings(),
            "irreversible_state": False,
        }

    # -- engine lifecycle -------------------------------------------------

    def _ensure_engine(self):
        if self._engine is not None:
            return self._engine
        bin_dir = ensure_pulse_importable(self.config["install_dir"])

        from pulse.cdm import scalars
        from pulse.cdm.engine import SEDataRequest, SEDataRequestManager
        from pulse.engine.PulseEngine import PulseEngine, eModelType

        requests = []
        for prop, unit_cls, unit_name in VITALS.values():
            unit = getattr(getattr(scalars, unit_cls), unit_name) if unit_cls and unit_name else None
            requests.append(SEDataRequest.create_physiology_request(prop, unit=unit))

        state_path = bin_dir / "states" / self.config["state_file"]
        if not state_path.is_file():
            raise FileNotFoundError(f"Pulse state file not found: {state_path}")

        engine = PulseEngine(eModelType.HumanAdultWholeBody, f"{bin_dir}/")
        engine.log_to_console(False)
        if not engine.serialize_from_file(str(state_path), SEDataRequestManager(requests)):
            raise RuntimeError(f"Pulse failed to load state {state_path}")
        # Populate pull_data() with the loaded state's values without advancing.
        engine.advance_time_s(0.0)
        self._engine = engine
        return engine

    def _read_vitals(self) -> dict[str, float]:
        values = self._ensure_engine().pull_data()
        return {name: float(v) for name, v in zip(VITALS, values[1:])}

    def _previous_readings(self) -> dict[str, float]:
        if not self._previous:
            self._previous = self._read_vitals()
        return dict(self._previous)

    def _apply_interventions(self, engine, state):
        from pulse.cdm.patient_actions import SEHemorrhage, SESubstanceCompoundInfusion
        from pulse.cdm.scalars import VolumePerTimeUnit, VolumeUnit

        severity = float(state["hemorrhage_severity"])
        if severity != self._applied["hemorrhage_severity"]:
            if not 0.0 <= severity <= 1.0:
                raise ValueError(f"hemorrhage_severity must be in [0, 1], got {severity}")
            action = SEHemorrhage()
            action.set_compartment(self.config["hemorrhage_compartment"])
            action.get_severity().set_value(severity)
            engine.process_action(action)
            self._applied["hemorrhage_severity"] = severity

        rate = float(state["iv_rate_mL_per_min"])
        if rate != self._applied["iv_rate_mL_per_min"]:
            if rate < 0.0:
                raise ValueError(f"iv_rate_mL_per_min must be >= 0, got {rate}")
            action = SESubstanceCompoundInfusion()
            action.set_compound(self.config["iv_compound"])
            action.get_rate().set_value(rate, VolumePerTimeUnit.mL_Per_min)
            action.get_bag_volume().set_value(self.config["iv_bag_volume_L"], VolumeUnit.L)
            engine.process_action(action)
            self._applied["iv_rate_mL_per_min"] = rate

    def update(self, state, interval):
        engine = self._ensure_engine()
        if not self._alive:
            return {}
        previous = self._previous_readings()
        self._apply_interventions(engine, state)
        if not engine.advance_time_s(float(interval)):
            self._alive = False
            return {"irreversible_state": True}
        current = self._read_vitals()
        self._previous = current
        return {name: current[name] - previous[name] for name in VITALS}


class MapFluidController(Step):
    """Proportional fluid-resuscitation controller on mean arterial pressure.

    Sets the IV infusion rate in proportion to how far MAP is below
    ``target_map_mmHg``, clipped to ``[0, max_rate_mL_per_min]``. It writes a
    setpoint, so its output port is ``overwrite[float]``.
    """

    config_schema = {
        "target_map_mmHg": {"_type": "float", "_default": 90.0},
        "gain_mL_per_min_per_mmHg": {"_type": "float", "_default": 25.0},
        "max_rate_mL_per_min": {"_type": "float", "_default": 250.0},
    }

    def inputs(self):
        return {"mean_arterial_pressure_mmHg": "float"}

    def outputs(self):
        return {"iv_rate_mL_per_min": "overwrite[float]"}

    def update(self, state, interval=None):
        deficit = self.config["target_map_mmHg"] - float(state["mean_arterial_pressure_mmHg"])
        rate = self.config["gain_mL_per_min_per_mmHg"] * deficit
        rate = min(max(rate, 0.0), self.config["max_rate_mL_per_min"])
        return {"iv_rate_mL_per_min": rate}
