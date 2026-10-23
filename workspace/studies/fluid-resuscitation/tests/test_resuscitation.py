"""Pre-registered criteria for the fluid resuscitation comparison (see study.yaml)."""

import pytest

BV = "vitals.blood_volume_mL"
IV = "interventions.iv_rate_mL_per_min"
MAP = "vitals.mean_arterial_pressure_mmHg"
ARMS = ["untreated", "saline-map-90", "blood-map-90"]
TREATED = ARMS[1:]
DURATION_S = 600.0


@pytest.fixture(scope="module")
def arms(latest):
    missing = [arm for arm in ARMS if arm not in latest]
    assert not missing, f"no completed run for arms {missing}"
    for arm in ARMS:
        assert latest[arm].time[-1] == DURATION_S, f"{arm} ran to t={latest[arm].time[-1]}"
    return latest


def test_untreated_arm_reproduces_reference(arms):
    # .build-progress.md reference: StandardMale, RightLeg 0.8, 600 s.
    untreated = arms["untreated"]
    assert untreated.final(BV) == pytest.approx(3936, abs=5)
    assert untreated.final(MAP) == pytest.approx(84.1, abs=0.5)
    assert untreated.observable(IV).max() == 0.0


@pytest.mark.parametrize("arm", TREATED)
def test_controller_engages_in_treated_arms(arms, arm):
    assert arms[arm].observable(IV).max() > 0.0


@pytest.mark.parametrize("arm", TREATED)
def test_treated_arms_preserve_blood_volume(arms, arm):
    assert arms[arm].final(BV) > arms["untreated"].final(BV)


@pytest.mark.parametrize("arm", TREATED)
def test_treated_arms_preserve_pressure(arms, arm):
    assert arms[arm].final(MAP) > arms["untreated"].final(MAP)
