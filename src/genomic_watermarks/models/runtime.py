"""Apple-local runtime selection without importing PyTorch at package import time."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True, slots=True)
class TorchRuntime:
    device: str
    dtype_name: str
    torch_dtype: Any


def choose_device(
    requested: str,
    *,
    mps_available: bool,
    allow_cpu_fallback: bool,
) -> str:
    """Resolve ``auto``, ``mps``, or ``cpu`` under the laptop hardware contract."""

    if requested not in {"auto", "mps", "cpu"}:
        raise ValueError("device must be auto, mps, or cpu")
    if requested == "cpu":
        return "cpu"
    if mps_available:
        return "mps"
    if allow_cpu_fallback:
        return "cpu"
    raise RuntimeError("MPS was requested but is unavailable and CPU fallback is disabled")


def resolve_torch_runtime(
    requested: str = "auto",
    *,
    allow_cpu_fallback: bool = True,
    dtype: str = "auto",
) -> TorchRuntime:
    """Import PyTorch lazily and choose a local inference device/dtype."""

    try:
        import torch
    except ImportError as error:
        raise RuntimeError(
            "model-backed work requires the optional 'models' dependencies"
        ) from error

    device = choose_device(
        requested,
        mps_available=bool(torch.backends.mps.is_available()),
        allow_cpu_fallback=allow_cpu_fallback,
    )
    if dtype == "auto":
        dtype = "bfloat16" if device == "mps" else "float32"
    supported = {
        "bfloat16": torch.bfloat16,
        "float16": torch.float16,
        "float32": torch.float32,
    }
    if dtype not in supported:
        raise ValueError(f"unsupported dtype: {dtype}")
    return TorchRuntime(device=device, dtype_name=dtype, torch_dtype=supported[dtype])
