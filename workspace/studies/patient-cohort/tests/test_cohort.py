"""Pre-registered criteria for the hemorrhage patient cohort (see study.yaml)."""

from pathlib import Path

import numpy as np
import pytest
import yaml

BV = "vitals.blood_volume_mL"
HR = "vitals.heart_rate_bpm"
LOST = "vitals.total_hemorrhaged_volume_mL"
MAP = "vitals.mean_arterial_pressure_mmHg"
SPEC = yaml.safe_load((Path(__file__).parents[1] / "study.yaml").read_text())
PATIENTS = [entry["name"] for entry in SPEC["baseline"] + SPEC["variants"]]
DURATION_S = 600.0


def test_every_shipped_patient_ran(latest):
    assert len(PATIENTS) == 21
    missing = [p for p in PATIENTS if p not in latest]
    assert not missing, f"no completed run for {missing}"
    short = [p for p in PATIENTS if latest[p].time[-1] != DURATION_S]
    assert not short, f"runs that stopped before {DURATION_S} s: {short}"


@pytest.mark.parametrize("patient", PATIENTS)
def test_every_patient_bleeds_and_compensates(latest, patient):
    run = latest[patient]
    assert run.final(LOST) > 0.0
    assert run.final(BV) < run.initial(BV)
    assert run.final(HR) > run.initial(HR)
    assert run.final(MAP) < run.initial(MAP)


def test_smaller_patients_lose_a_larger_fraction(latest):
    runs = [latest[p] for p in PATIENTS]
    volume = np.array([run.initial(BV) for run in runs])
    fraction = np.array([run.final(LOST) / run.initial(BV) for run in runs])
    ranks = lambda values: values.argsort().argsort()
    rho = np.corrcoef(ranks(volume), ranks(fraction))[0, 1]
    assert rho <= -0.7, f"Spearman rho = {rho:.2f}"
