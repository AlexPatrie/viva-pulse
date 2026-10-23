import pytest
from process_bigraph import Composite, gather_emitter_results

from viva_pulse.core import build_core


@pytest.fixture
def run_composite():
    """Build a generator's document on a fresh core, run it, return (sim, rows)."""

    def _run(generator, duration, **params):
        core = build_core()
        sim = Composite({"state": generator(core, **params)}, core=core)
        sim.run(duration)
        return sim, gather_emitter_results(sim)[("emitter",)]

    return _run
