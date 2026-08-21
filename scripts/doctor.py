#!/usr/bin/env python3
"""Report whether the local machine satisfies the repository execution contract."""

from __future__ import annotations

import importlib.util
import platform
import subprocess
import sys


def memory_gib() -> float | None:
    if platform.system() != "Darwin":
        return None
    try:
        value = subprocess.check_output(
            ["sysctl", "-n", "hw.memsize"], text=True, stderr=subprocess.DEVNULL
        ).strip()
        return int(value) / 2**30
    except (OSError, subprocess.SubprocessError, ValueError):
        return None


def main() -> int:
    print(f"python={platform.python_version()}")
    print(f"platform={platform.system()} {platform.machine()}")
    installed_memory = memory_gib()
    if installed_memory is not None:
        print(f"unified_memory_gib={installed_memory:.1f}")

    if importlib.util.find_spec("torch") is None:
        print("torch=not-installed (core smoke tests remain available)")
        print("mps=unknown")
        return 0

    import torch

    print(f"torch={torch.__version__}")
    built = bool(torch.backends.mps.is_built())
    available = bool(torch.backends.mps.is_available())
    print(f"mps_built={str(built).lower()}")
    print(f"mps_available={str(available).lower()}")
    if platform.system() == "Darwin" and not available:
        print("warning=MPS is unavailable; model-backed runs will use CPU and may be slow")
    return 0


if __name__ == "__main__":
    sys.exit(main())
