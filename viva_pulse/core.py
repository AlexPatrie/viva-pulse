"""Core construction with viva-pulse's processes registered explicitly.

The dashboard and every ``studies/*/sims/run.py`` use ``build_core()`` so the
workspace's own processes resolve regardless of how the package was installed
(editable installs are not always found by ``allocate_core()`` discovery).
"""

from process_bigraph import allocate_core

from .processes import MapFluidController, PulseCircuitProcess, PulseProcess


def register_processes(core):
    core.register_link("PulseProcess", PulseProcess)
    core.register_link("PulseCircuitProcess", PulseCircuitProcess)
    core.register_link("MapFluidController", MapFluidController)
    return core


def build_core(core=None):
    if core is None:
        core = allocate_core()
    return register_processes(core)
