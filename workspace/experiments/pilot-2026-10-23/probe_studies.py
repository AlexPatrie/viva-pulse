"""Probes for agenda Task 1: severity curve and per-patient load check (real Pulse)."""
import json, sys, time
from pathlib import Path
from process_bigraph import Composite, gather_emitter_results
from viva_pulse.core import build_core
from viva_pulse.composites import pulse_hemorrhage, pulse_resuscitation

KEYS = ["mean_arterial_pressure_mmHg", "heart_rate_bpm", "blood_volume_mL",
        "total_hemorrhaged_volume_mL", "irreversible_state"]

def run(gen, duration, **params):
    core = build_core()
    sim = Composite({"state": gen(core, **params)}, core=core)
    t = time.time()
    sim.run(duration)
    rows = gather_emitter_results(sim)[("emitter",)]
    first, last = rows[0], rows[-1]
    return {"wall_s": round(time.time() - t, 1), "first": {k: first[k] for k in KEYS},
            "last": {k: last[k] for k in KEYS}, "t_end": last["time"],
            "irreversible_t": next((r["time"] for r in rows if r["irreversible_state"]), None)}

mode = sys.argv[1]
if mode == "severity":
    for sev in map(float, sys.argv[2:]):
        print(json.dumps({"severity": sev, **run(pulse_hemorrhage, 600, severity=sev)}), flush=True)
elif mode == "patients":
    states = sorted(p.name for p in Path(".pulse-build/install/bin/states").glob("*@0s.json"))
    for s in states:
        try:
            print(json.dumps({"state": s, **run(pulse_hemorrhage, float(sys.argv[2]), state_file=s)}), flush=True)
        except Exception as e:
            print(json.dumps({"state": s, "error": f"{type(e).__name__}: {e}"[:300]}), flush=True)
