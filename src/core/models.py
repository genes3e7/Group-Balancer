"""Data models for the Group Balancer.

Defines strong typing for participants, configurations, and optimization modes.
"""

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from enum import Enum
from types import MappingProxyType

from src.core import config


class OptimizationMode(str, Enum):
    """Available optimization topologies."""

    SIMPLE = "Simple"
    ADVANCED = "Advanced"


class ConflictPriority(str, Enum):
    """Priority for tag collisions."""

    GROUPERS = "Groupers"
    SEPARATORS = "Separators"


@dataclass(frozen=True)
class Participant:
    """Represents a single participant in the balancing process.

    Attributes:
        name: The participant's identifier.
        scores: Dictionary of score labels to their numeric values.
        groupers: Raw tag string for cohesion constraints.
        separators: Raw tag string for dispersion constraints.
        original_index: The zero-based index of the participant in input data.
    """

    name: str
    scores: Mapping[str, float]
    groupers: str = ""
    separators: str = ""
    original_index: int | None = None

    def __post_init__(self):
        """Sanitize inputs after initialization."""
        if not isinstance(self.name, str):
            object.__setattr__(self, "name", str(self.name))

        # Ensure scores are floats and immutable
        sanitized_scores = {k: float(v) for k, v in self.scores.items()}
        object.__setattr__(self, "scores", MappingProxyType(sanitized_scores))

    @property
    def fingerprint(self) -> str:
        """Returns a stable hash of the participant's identity."""
        import hashlib

        # Sort scores for stable hashing
        scores_str = ",".join(f"{k}:{v}" for k, v in sorted(self.scores.items()))
        # Canonicalize tags (order/whitespace insensitive)
        from src.core.solver import TagProcessor

        g_tags = sorted(TagProcessor.get_tags(self.groupers))
        s_tags = sorted(TagProcessor.get_tags(self.separators))
        raw = f"{self.name}|{scores_str}|{','.join(g_tags)}|{','.join(s_tags)}"
        return hashlib.md5(raw.encode(), usedforsecurity=False).hexdigest()


@dataclass(frozen=True)
class SolverConfig:
    """Configuration for the CP-SAT solver.

    Attributes:
        num_groups: Total number of groups to create.
        group_capacities: Exactly how many people per group.
        score_weights: Multipliers for each score dimension.
        opt_mode: Whether to balance dimensions individually or as a total.
        conflict_priority: Which constraint wins if tags overlap.
        grouper_weight: Internal penalty for splitting groupers.
        separator_weight: Internal penalty for clumping separators.
        strict_groupers: If True, cohesion tags are hard constraints.
        hints: Optional mapping of identity to group_id for warm starts.
        timeout_seconds: Maximum wall-clock time for search.
        num_workers: Number of parallel search threads.
    """

    num_groups: int
    group_capacities: Sequence[int]
    score_weights: Mapping[str, float]
    opt_mode: OptimizationMode = OptimizationMode.ADVANCED
    conflict_priority: ConflictPriority = ConflictPriority.GROUPERS
    grouper_weight: int = config.DEFAULT_GROUPER_WEIGHT
    separator_weight: int = config.DEFAULT_SEPARATOR_WEIGHT
    strict_groupers: bool = False
    hints: Mapping[str | int, int] | None = None
    timeout_seconds: int = 60
    num_workers: int = 4

    def __post_init__(self):
        """Validate configuration parameters.

        Raises:
            ValueError: If configurations are logically inconsistent.
        """
        # Ensure deep immutability
        object.__setattr__(self, "group_capacities", tuple(self.group_capacities))
        object.__setattr__(
            self, "score_weights", MappingProxyType(dict(self.score_weights))
        )
        if self.hints is not None:
            object.__setattr__(self, "hints", MappingProxyType(dict(self.hints)))

        self.validate_safety_bounds()

    def validate_safety_bounds(self) -> None:
        """Enforces architectural and performance safety limits.

        Raises:
            ValueError: If any parameter exceeds defined safety thresholds.
        """
        if self.num_groups <= 0:
            raise ValueError("Number of groups must be positive.")
        if self.num_groups > config.MAX_GROUPS:
            raise ValueError(f"Number of groups exceeds limit of {config.MAX_GROUPS}.")

        total_participants = sum(self.group_capacities)
        if total_participants <= 0:
            raise ValueError("Total capacity must be positive.")
        if total_participants > config.MAX_PARTICIPANTS:
            raise ValueError(
                f"Total participants ({total_participants}) exceeds "
                f"limit of {config.MAX_PARTICIPANTS}."
            )

        if len(self.group_capacities) != self.num_groups:
            raise ValueError("Group capacities list length must match num_groups.")
        if any(c < 0 for c in self.group_capacities):
            raise ValueError("Group capacities cannot be negative.")

        # Validate score weights
        if not self.score_weights:
            raise ValueError("At least one score weight must be provided.")

        has_positive_weight = False
        import math

        for col, weight in self.score_weights.items():
            if not math.isfinite(weight):
                raise ValueError(f"Score weight for {col} must be a finite number.")
            if weight < 0:
                raise ValueError(f"Score weight for {col} cannot be negative.")
            if weight > 0:
                has_positive_weight = True

        if not has_positive_weight:
            raise ValueError("At least one score weight must be positive.")

        # Validate penalty weights
        for name, weight in [
            ("grouper_weight", self.grouper_weight),
            ("separator_weight", self.separator_weight),
        ]:
            if not math.isfinite(weight):
                raise ValueError(f"{name} must be a finite number.")
            if weight < 0:
                raise ValueError(f"{name} cannot be negative.")
            if weight > 1_000_000:
                raise ValueError(f"{name} exceeds safe limit of 1,000,000.")
