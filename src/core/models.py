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

    def __post_init__(self) -> None:
        """Sanitize inputs after initialization."""
        if not isinstance(self.name, str):
            object.__setattr__(self, "name", str(self.name))

        # Ensure scores are floats and immutable
        sanitized_scores = {k: float(v) for k, v in self.scores.items()}
        object.__setattr__(self, "scores", MappingProxyType(sanitized_scores))


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
    timeout_seconds: int = 60
    num_workers: int = 4

    def __post_init__(self) -> None:
        """Validate configuration parameters.

        Raises:
            ValueError: If configurations are logically inconsistent.
        """
        # Ensure deep immutability
        object.__setattr__(self, "group_capacities", tuple(self.group_capacities))
        object.__setattr__(
            self,
            "score_weights",
            MappingProxyType(dict(self.score_weights)),
        )

        if self.num_groups <= 0:
            msg = "Number of groups must be positive."
            raise ValueError(msg)
        if sum(self.group_capacities) <= 0:
            msg = "Total capacity must be positive."
            raise ValueError(msg)
        if len(self.group_capacities) != self.num_groups:
            msg = "Group capacities list length must match num_groups."
            raise ValueError(msg)
        if any(c < 0 for c in self.group_capacities):
            msg = "Group capacities cannot be negative."
            raise ValueError(msg)
