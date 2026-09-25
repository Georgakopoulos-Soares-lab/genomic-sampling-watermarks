#!/usr/bin/env python3
"""Fail fast when a node cannot run the v2 FPR generation.

Import torch before touching the CUDA driver. Calling ``ctypes.CDLL("libcuda.so.1")``
and ``cuInit`` first breaks the later ``import torch`` on the shared gpu-a100-small
VMs with ``ImportError: cannot load module more than once per process`` from numpy's
extension. The runner itself only ever reaches CUDA through torch, so this check
follows the same order.
"""

from __future__ import annotations

import argparse
import os
import sys


def uvm_fault() -> str | None:
    """Return a message when /dev/nvidia-uvm is the reason CUDA is unusable."""
    try:
        os.close(os.open("/dev/nvidia-uvm", os.O_RDWR))
    except FileNotFoundError:
        return "/dev/nvidia-uvm does not exist: this is not a GPU node."
    except OSError as error:
        # EIO here means the UVM driver's global initialisation failed, which happens
        # when any GPU registered on the node failed to attach (as on c301-002). That
        # breaks CUDA for every process on the node, including the healthy GPUs.
        return (
            f"/dev/nvidia-uvm cannot be opened ({error}). A GPU on this node failed to "
            "attach, which breaks CUDA for every process; use another node."
        )
    return None


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--gpus", type=int, default=2, help="devices this job needs")
    args = parser.parse_args()

    import torch

    if not torch.cuda.is_available():
        sys.exit(f"FATAL: {uvm_fault() or 'torch reports no usable CUDA device on this node.'}")
    count = torch.cuda.device_count()
    if count < args.gpus:
        sys.exit(f"FATAL: need {args.gpus} usable A100(s), saw {count}.")
    names = [torch.cuda.get_device_name(index) for index in range(args.gpus)]
    # Enumeration alone can succeed on a node that cannot actually allocate.
    probe = torch.arange(1024, device="cuda", dtype=torch.float32)
    total = float(probe.sum().cpu())
    torch.cuda.synchronize()
    if total != 523776.0:
        sys.exit(f"FATAL: GPU probe returned {total}, expected 523776.0")
    print(f"preflight OK: {count} device(s) visible, using {names}", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
