"""Pre-registered criteria for the hemorrhage severity sweep (see study.yaml)."""

import pytest

BV = "vitals.blood_volume_mL"
HR = "vitals.heart_rate_bpm"
LOST = "vitals.total_hemorrhaged_volume_mL"
MAP = "vitals.mean_arterial_pressure_mmHg"
SEVERITIES = ["0.0", "0.2", "0.4", "0.6", "0.8", "1.0"]
DURATION_S = 600.0


@pytest.fixture(scope="module")
def grid(latest):
    missing = [s for s in SEVERITIES if f"severity-{s}" not in latest]
    assert not missing, f"no completed run for severities {missing}"
    runs = [latest[f"severity-{s}"] for s in SEVERITIES]
    for run in runs:
        assert run.time[-1] == DURATION_S, f"{run.label} ran to t={run.time[-1]}"
    return runs


def test_no_bleed_control_is_flat(grid):
    control = grid[0]
    assert control.final(LOST) < 1.0
    assert abs(control.final(MAP) - control.initial(MAP)) < 1.0
    assert abs(control.final(HR) - control.initial(HR)) < 1.0


def test_blood_loss_rises_with_severity(grid):
    lost = [run.final(LOST) for run in grid]
    assert all(a < b for a, b in zip(lost, lost[1:])), lost
    volume = [run.final(BV) for run in grid]
    assert all(a > b for a, b in zip(volume, volume[1:])), volume


def test_heart_rate_rises_with_severity(grid):
    rates = [run.final(HR) for run in grid[1:]]
    assert all(a < b for a, b in zip(rates, rates[1:])), rates


@pytest.mark.usefixtures("grid")
@pytest.mark.parametrize("severity", ["0.2", "0.4"])
def test_pressure_held_for_mild_bleeds(latest, severity):
    run = latest[f"severity-{severity}"]
    assert abs(run.final(MAP) - run.initial(MAP)) < 2.0


@pytest.mark.usefixtures("grid")
def test_pressure_falls_for_severe_bleeds(latest):
    severe, worst = latest["severity-0.8"], latest["severity-1.0"]
    assert severe.initial(MAP) - severe.final(MAP) >= 8.0
    assert worst.final(MAP) < severe.final(MAP)


@pytest.mark.usefixtures("grid")
def test_reproduces_reference_run(latest):
    # .build-progress.md reference: StandardMale, RightLeg 0.8, 600 s.
    run = latest["severity-0.8"]
    assert run.final(BV) == pytest.approx(3936, abs=5)
    assert run.final(MAP) == pytest.approx(84.1, abs=0.5)
