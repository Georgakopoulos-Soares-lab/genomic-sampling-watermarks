"""Portable runtime selection without importing PyTorch at package import time."""

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
    cuda_available: bool = False,
    allow_cpu_fallback: bool,
) -> str:
    """Resolve an accelerator while preserving MPS as the ``auto`` priority."""

    if requested not in {"auto", "mps", "cuda", "cpu"}:
        raise ValueError("device must be auto, mps, cuda, or cpu")
    if requested == "cpu":
        return "cpu"
    if requested == "auto":
        if mps_available:
            return "mps"
        if cuda_available:
            return "cuda"
    elif requested == "mps" and mps_available:
        return "mps"
    elif requested == "cuda" and cuda_available:
        return "cuda"
    if allow_cpu_fallback:
        return "cpu"
    accelerator = "an accelerator" if requested == "auto" else requested.upper()
    raise RuntimeError(f"{accelerator} is unavailable and CPU fallback is disabled")


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
        cuda_available=bool(torch.cuda.is_available()),
        allow_cpu_fallback=allow_cpu_fallback,
    )
    if dtype == "auto":
        dtype = "bfloat16" if device in {"mps", "cuda"} else "float32"
    supported = {
        "bfloat16": torch.bfloat16,
        "float16": torch.float16,
        "float32": torch.float32,
    }
    if dtype not in supported:
        raise ValueError(f"unsupported dtype: {dtype}")
    return TorchRuntime(device=device, dtype_name=dtype, torch_dtype=supported[dtype])
