"""Process-only Linux memory policy, separate from detector and threat logic."""
from __future__ import annotations

import os
import platform
from pathlib import Path


def prepare_jetson_memory(*, inherit_thp: bool = False) -> dict[str, object] | None:
    """Disable automatic THP for this Orin worker before loading the ML runtime.

    Other platforms are untouched. ``inherit_thp`` is for controlled comparisons;
    it observes the inherited flag and does not enable or disable anything.
    No sysfs, kernel-wide settings, clocks, or drivers are changed.
    """
    if platform.system() != "Linux":
        return None
    try:
        model = Path("/proc/device-tree/model").read_text()
    except OSError:
        return None
    if "Orin" not in model:
        return None
    import ctypes

    libc = ctypes.CDLL(None, use_errno=True)
    libc.prctl.argtypes = [ctypes.c_int, *([ctypes.c_ulong] * 4)]
    libc.prctl.restype = ctypes.c_int

    def call(operation: int, value: int = 0) -> int:
        result = libc.prctl(operation, value, 0, 0, 0)
        if result < 0:
            error = ctypes.get_errno()
            raise RuntimeError(f"Orin process THP policy failed: {os.strerror(error)}")
        return result

    before = call(42)  # PR_GET_THP_DISABLE, linux/prctl.h
    if not inherit_thp and before != 1:
        call(41, 1)  # PR_SET_THP_DISABLE; applies only to this process
    after = call(42)
    if not inherit_thp and after != 1:
        raise RuntimeError("Orin process THP disable was not confirmed")
    return {"scope": "current_process", "requested": "inherit" if inherit_thp else "disable_thp",
            "before": before, "after": after, "changed": before != after}
