"""Standalone detector building blocks."""

from .hypotheses import PartitionScore, score_partition_agreement, search_orientation_and_phase
from .search import (
    FORWARD,
    ORIENTATIONS,
    REVERSE_COMPLEMENT,
    Calibration,
    DetectionResult,
    DetectorConfig,
    DetectorHypothesis,
    PartitionCache,
    calibrate_threshold,
    detect,
    detect_aligned,
    detection_rate,
    empirical_p_value,
    enumerate_search,
    standardized_agreement,
)

__all__ = [
    "FORWARD",
    "ORIENTATIONS",
    "REVERSE_COMPLEMENT",
    "Calibration",
    "DetectionResult",
    "DetectorConfig",
    "DetectorHypothesis",
    "PartitionCache",
    "PartitionScore",
    "calibrate_threshold",
    "detect",
    "detect_aligned",
    "detection_rate",
    "empirical_p_value",
    "enumerate_search",
    "score_partition_agreement",
    "search_orientation_and_phase",
    "standardized_agreement",
]
