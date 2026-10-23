"""Locate and load a built Kitware Pulse install.

Pulse has no PyPI distribution: its Python API (the ``pulse`` package plus the
pybind11 ``PyPulse`` extension) is produced by the Pulse CMake superbuild with
``Pulse_PYTHON_API=ON``. This module finds that install and puts it on
``sys.path`` so ``pulse.engine.PulseEngine`` drives the real engine.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

ENV_VAR = "PULSE_INSTALL_DIR"

# Source-checkout default: the superbuild documented in README.md writes here.
_REPO_DEFAULT = Path(__file__).resolve().parents[1] / ".pulse-build" / "install"


class PulseNotFoundError(RuntimeError):
    """Raised when no usable Pulse install can be found."""


def resolve_install_dir(install_dir: str = "") -> Path:
    """Return the Pulse install prefix (the directory holding ``bin/`` and ``python/``).

    The first of these that is set is used, and it must be valid — an
    explicitly requested location never silently falls back to another one:
    the ``install_dir`` argument, the ``PULSE_INSTALL_DIR`` environment
    variable, then ``.pulse-build/install`` next to this package's source
    checkout.
    """
    if install_dir:
        candidate, source = install_dir, "install_dir config"
    elif os.environ.get(ENV_VAR):
        candidate, source = os.environ[ENV_VAR], f"${ENV_VAR}"
    else:
        candidate, source = str(_REPO_DEFAULT), "source-checkout default"
    prefix = Path(candidate).expanduser().resolve()
    if _is_pulse_install(prefix):
        return prefix
    raise PulseNotFoundError(
        f"No Pulse install at {prefix} (from {source}): expected bin/PyPulse*.so, "
        "bin/states/ and python/pulse/. Build Pulse with -DPulse_PYTHON_API=ON "
        f"against this Python and set {ENV_VAR} to its install prefix; see README.md."
    )


def _is_pulse_install(prefix: Path) -> bool:
    bin_dir = prefix / "bin"
    return (
        any(bin_dir.glob("PyPulse*"))
        and (bin_dir / "states").is_dir()
        and (prefix / "python" / "pulse").is_dir()
    )


def ensure_pulse_importable(install_dir: str = "") -> Path:
    """Put the Pulse install on ``sys.path`` and return its ``bin`` directory.

    ``bin`` holds ``PyPulse`` and is the engine's data root (states, substances,
    patients, configuration).
    """
    prefix = resolve_install_dir(install_dir)
    for path in (prefix / "bin", prefix / "python"):
        entry = str(path)
        if entry not in sys.path:
            sys.path.insert(0, entry)
    return prefix / "bin"
