"""Sampling-time watermark constructions."""

from .partition import (
    CoupledSample,
    keyed_balanced_partition,
    sample_categorical,
    sample_partition_coupling,
    select_group_maximal_coupling,
)

__all__ = [
    "CoupledSample",
    "keyed_balanced_partition",
    "sample_categorical",
    "sample_partition_coupling",
    "select_group_maximal_coupling",
]
