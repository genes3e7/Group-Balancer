"""
Core optimization logic using Google OR-Tools.

Refactored to use Builder and Strategy patterns for professional standards,
SRP, and Open/Closed principles.
"""

import math
import time
from abc import ABC, abstractmethod

import pandas as pd
from ortools.sat.python import cp_model

from src import logger
from src.core import config
from src.core.models import (
    ConflictPriority,
    OptimizationMode,
    Participant,
    SolverConfig,
)
from src.core.tag_utils import canonicalize_tags


def apply_solver_tuning(solver_inst: cp_model.CpSolver) -> None:
    """Applies optimal CP-SAT parameters for group partitioning math.

    Args:
        solver_inst: The OR-Tools solver instance to configure.
    """
    # Optimization: linearization_level=0 is often faster for partition math.
    # symmetry_level=2 enables aggressive internal symmetry breaking.
    solver_inst.parameters.linearization_level = 0
    solver_inst.parameters.symmetry_level = 2


class SolutionPrinter(cp_model.CpSolverSolutionCallback):
    """Callback to log intermediate solutions found by the solver."""

    def __init__(self, start_time: float):
        """Initializes the printer with the solver start time."""
        cp_model.CpSolverSolutionCallback.__init__(self)
        self.__start_time = start_time
        self.__solution_count = 0
        self.__last_log_time = 0.0

    def on_solution_callback(self) -> None:
        """Called by the solver when a new valid solution is found."""
        self.__solution_count += 1
        current_time = time.time()

        if current_time - self.__last_log_time >= 1.0:
            obj = self.ObjectiveValue()
            elapsed = current_time - self.__start_time
            logger.info(
                "Solver Progress: %d solutions | Objective: %d | Elapsed: %.1fs",
                self.__solution_count,
                obj,
                elapsed,
            )
            self.__last_log_time = current_time


class TagProcessor:
    """Handles tokenization and conflict resolution for constraint tags."""

    @staticmethod
    def get_tags(val: str) -> set[str]:
        """Extracts unique characters as tags, ignoring whitespace and commas."""
        return canonicalize_tags(val)

    @classmethod
    def process_participants(
        cls, participants: list[Participant], priority: ConflictPriority
    ) -> tuple[dict[str, set[int]], dict[str, set[int]]]:
        """Generates grouper and separator sets with conflict resolution.

        Args:
            participants: List of strongly-typed Participant models.
            priority: Logic to resolve tag collisions.

        Returns:
            Tuple of (grouper_sets, separator_sets).
        """
        groupers: dict[str, set[int]] = {}
        separators: dict[str, set[int]] = {}

        for i, p in enumerate(participants):
            g_tags = sorted(cls.get_tags(p.groupers))
            s_tags = sorted(cls.get_tags(p.separators))

            for tag in g_tags:
                groupers.setdefault(tag, set()).add(i)
            for tag in s_tags:
                separators.setdefault(tag, set()).add(i)

        # Conflict Resolution: Only resolve for the same tag key
        common_tags = sorted(set(groupers.keys()) & set(separators.keys()))

        for tag in common_tags:
            g_set = groupers[tag]
            s_set = separators[tag]
            overlap = s_set & g_set

            if len(overlap) > 1:
                if priority == ConflictPriority.GROUPERS:
                    s_set.difference_update(overlap)
                else:
                    g_set.difference_update(overlap)

        return groupers, separators


class ScoringStrategy(ABC):
    """Abstract base for different optimization topologies.

    Defines the interface for converting participant data and configuration into
    score vectors that the solver can minimize.
    """

    @abstractmethod
    def get_score_vectors(
        self, participants: list[Participant], cfg: SolverConfig
    ) -> list[tuple[str, list[int], int]]:
        """Returns score vectors for each dimension to be optimized.

        Args:
            participants: List of strongly-typed Participant models.
            cfg: The solver configuration parameters.

        Returns:
            A list of tuples, where each tuple contains:
                - str: The name of the dimension.
                - list[int]: The list of integer scores for each participant.
                - int: The weight multiplier for this dimension.
        """
        pass


class AdvancedScoring(ScoringStrategy):
    """Balances each score dimension independently with normalization.

    This strategy ensures that dimensions with vastly different magnitudes (e.g.,
    0.1 vs 100) are given equal priority in balancing when their user-defined
    weights are identical. It uses high-precision integer scaling to eliminate
    floating-point noise.
    """

    def get_score_vectors(
        self, participants: list[Participant], cfg: SolverConfig
    ) -> list[tuple[str, list[int], int]]:
        """Generates normalized score vectors for each dimension.

        Uses high-precision integer scaling (10^10) to map raw floats to a common
        magnitude, ensuring magnitude-insensitive balancing.

        Args:
            participants: List of strongly-typed Participant models.
            cfg: The solver configuration parameters.

        Returns:
            list[tuple[str, list[int], int]]: Normalized score vectors with weights.
        """
        vectors = []
        # Sort keys for deterministic objective addition order
        for col in sorted(cfg.score_weights.keys()):
            weight = cfg.score_weights[col]
            if weight == 0:
                continue

            # 1. Extract raw scores
            raw_scores = [p.scores.get(col, 0.0) for p in participants]
            # Use high precision integer scaling (10^10) to avoid float noise
            scaled_raw = [int(round(s * 10_000_000_000)) for s in raw_scores]
            raw_total = sum(abs(s) for s in scaled_raw)

            if raw_total == 0:
                continue

            # 2. Normalize and scale to common magnitude (e.g. 10,000,000 total)
            # Use integer math for normalization
            norm_multiplier = config.SCALE_FACTOR * 100
            scores = [
                int(round((s * norm_multiplier) / raw_total))
                for s in scaled_raw
            ]

            # 3. Scale by user weight with higher precision (100 -> 10,000)
            weight_m = int(max(1, round(weight * 10000)))
            vectors.append((col, scores, weight_m))
        return vectors


class SimpleScoring(ScoringStrategy):
    """Balances a single weighted total score with dimension normalization.

    Aggregates multiple dimensions into a single target vector while still
    performing normalization on each dimension individually to prevent
    magnitude domination.
    """

    def get_score_vectors(
        self, participants: list[Participant], cfg: SolverConfig
    ) -> list[tuple[str, list[int], int]]:
        """Generates a single pre-aggregated and normalized score vector.

        Normalizes each dimension BEFORE aggregation to ensure fairness across
        different numeric ranges.

        Args:
            participants: List of strongly-typed Participant models.
            cfg: The solver configuration parameters.

        Returns:
            list[tuple[str, list[int], int]]: A single aggregated score vector.
        """
        # To avoid magnitude domination, we must normalize each dimension
        # BEFORE aggregating into a single total score.
        total_normalized_scores = [0.0] * len(participants)

        for col in sorted(cfg.score_weights.keys()):
            weight = cfg.score_weights[col]
            if weight == 0:
                continue

            raw_scores = [p.scores.get(col, 0.0) for p in participants]
            # Use high precision integer scaling (10^10) to avoid float noise
            scaled_raw = [int(round(s * 10_000_000_000)) for s in raw_scores]
            raw_total = sum(abs(s) for s in scaled_raw)

            if raw_total == 0:
                continue

            # Scale each dimension so its relative contribution is exactly the user weight
            # Use high precision multiplier for aggregation
            norm_multiplier = config.SCALE_FACTOR * weight * 100
            for i, s in enumerate(scaled_raw):
                total_normalized_scores[i] += (s * norm_multiplier) / raw_total

        # Round to integers for CP-SAT
        final_scores = [int(round(s)) for s in total_normalized_scores]
        return [("simple_total", final_scores, 100)]


class ConstraintBuilder:
    """Stateful builder for constructing the CP-SAT partition model."""

    def __init__(self, participants: list[Participant], cfg: SolverConfig):
        """Initializes the model builder."""
        self.participants = participants
        self.cfg = cfg
        self.num_people = len(participants)
        self.num_groups = cfg.num_groups
        self.model = cp_model.CpModel()
        self.x = {}  # (p_idx, g_idx) -> BoolVar
        self.objectives = []
        self.max_objective_bound = 0
        self._symmetry_broken = False

    def build_variables(self) -> None:
        """Initializes assignment variables and basic partitioning constraints."""
        for i in range(self.num_people):
            for g in range(self.num_groups):
                self.x[(i, g)] = self.model.NewBoolVar(f"p{i}_g{g}")
            self.model.AddExactlyOne([self.x[(i, g)] for g in range(self.num_groups)])

        for g in range(self.num_groups):
            self.model.Add(
                sum(self.x[(i, g)] for i in range(self.num_people))
                == self.cfg.group_capacities[g]
            )

    def add_pigeonhole_constraints(self, separators: dict[str, set[int]]) -> None:
        """Ensures separator tags are spread across groups proportionally.

        Calculates a dynamic upper bound for each group based on its relative
        capacity to ensure feasibility while maintaining dispersion.

        Args:
            separators: Mapping of separator tags to sets of participant indices.
        """
        total_p = self.num_people
        # Sort tags for determinism in constraint addition order
        for tag in sorted(separators.keys()):
            s_set = separators[tag]
            if not s_set:
                continue

            n_tag = len(s_set)
            # Sort participant indices for deterministic sum order
            sorted_s_set = sorted(s_set)

            for g in range(self.num_groups):
                cap_g = self.cfg.group_capacities[g]
                limit = min(cap_g, math.ceil((n_tag * cap_g) / total_p))
                self.model.Add(sum(self.x[(i, g)] for i in sorted_s_set) <= limit)

    def add_scoring_objectives(self, strategy: ScoringStrategy) -> None:
        """Builds multi-objective minimization for group score variance.

        Args:
            strategy: The scoring strategy to use for vector generation.
        """
        vectors = strategy.get_score_vectors(self.participants, self.cfg)

        # Performance optimization: Order by score vectors to break symmetry
        # more effectively than just a single dimension.
        for name, scores, weight_m in vectors:
            total_score = sum(scores)

            # Pre-calculate theoretical bounds for g_sums to tighten diff_bound
            # For capacity C, sum is between sum(bottom C) and sum(top C)
            sorted_scores = sorted(scores)
            g_sums = []
            theoretical_bounds = []

            for g in range(self.num_groups):
                cap = self.cfg.group_capacities[g]
                if cap == 0:
                    t_min = 0
                    t_max = 0
                else:
                    t_min = sum(sorted_scores[:cap])
                    t_max = sum(sorted_scores[-cap:])

                g_sums.append(self.model.NewIntVar(t_min, t_max, f"sum_{name}_{g}"))
                theoretical_bounds.append((t_min, t_max))

            # Advanced Symmetry Breaking: Enforce ordering for identical capacity
            # groups on at most one canonical dimension. This prunes G! search
            # branches without over-constraining multi-dimensional weights.
            if weight_m > 0 and not self._symmetry_broken:
                self._symmetry_broken = True
                for g1 in range(self.num_groups):
                    for g2 in range(g1 + 1, self.num_groups):
                        if (
                            self.cfg.group_capacities[g1]
                            == self.cfg.group_capacities[g2]
                        ):
                            self.model.Add(g_sums[g1] <= g_sums[g2])

            for g in range(self.num_groups):
                self.model.Add(
                    g_sums[g]
                    == sum(self.x[(i, g)] * scores[i] for i in range(self.num_people))
                )
                target = total_score * self.cfg.group_capacities[g]

                # Calculate tightest possible diff bound for this specific group
                # diff = g_sum * P - target
                t_min, t_max = theoretical_bounds[g]
                min_diff = t_min * self.num_people - target
                max_diff = t_max * self.num_people - target
                local_diff_bound = max(abs(min_diff), abs(max_diff))

                diff = self.model.NewIntVar(
                    -local_diff_bound, local_diff_bound, f"diff_{name}_{g}"
                )
                self.model.Add(diff == g_sums[g] * self.num_people - target)

                abs_diff = self.model.NewIntVar(0, local_diff_bound, f"abs_{name}_{g}")
                self.model.AddAbsEquality(abs_diff, diff)

                local_weighted_bound = local_diff_bound * weight_m
                self.max_objective_bound += local_weighted_bound

                if self.max_objective_bound > (1 << 60) - 1:
                    raise ValueError(
                        "Aggregate score objective exceeds CP-SAT safety bound."
                    )

                w_diff = self.model.NewIntVar(0, local_weighted_bound, f"w_{name}_{g}")
                self.model.Add(w_diff == abs_diff * weight_m)
                self.objectives.append(w_diff)

    def add_cohesion_penalties(self, groupers: dict[str, set[int]]) -> None:
        """Adds penalties for splitting grouper tags.

        Args:
            groupers: Mapping of grouper tags to sets of participant indices.
        """
        if self.cfg.strict_groupers:
            # Implement as hard constraints: all members of a tag must be in ONE group.
            # Sort tags for determinism in constraint addition order
            for tag in sorted(groupers.keys()):
                g_set = groupers[tag]
                if len(g_set) <= 1:
                    continue
                # Sort indices for deterministic constraint ordering
                sorted_g_set = sorted(g_set)
                # For each group g, if any member is in g, ALL members must be in g.
                for g in range(self.num_groups):
                    used = self.model.NewBoolVar(f"used_{tag}_{g}")
                    self.model.Add(
                        sum(self.x[(i, g)] for i in sorted_g_set) == len(g_set) * used
                    )
            return

        # Prevent 64-bit integer overflow in CP-SAT.
        # aggregate_cap (e.g. 1 << 60) must fit all objectives.
        aggregate_cap = 1 << 60
        # Count active tags deterministically
        active_tags = sum(
            1 for tag in sorted(groupers.keys()) if len(groupers[tag]) > 1
        )
        per_term_cap = aggregate_cap // max(1, active_tags * self.num_groups)
        base_penalty = min(self.max_objective_bound * 10 + 1000, per_term_cap)

        # Sort tags for determinism in constraint addition order
        for tag in sorted(groupers.keys()):
            g_set = groupers[tag]
            if len(g_set) <= 1:
                continue

            sorted_g_set = sorted(g_set)
            for g in range(self.num_groups):
                used = self.model.NewBoolVar(f"used_{tag}_{g}")
                self.model.AddMaxEquality(used, [self.x[(i, g)] for i in sorted_g_set])

                # Incorporate SolverConfig.grouper_weight and clamp per-term
                weight = self.cfg.grouper_weight
                cap_penalty = self.cfg.group_capacities[g] * 10
                raw_penalty = (base_penalty + cap_penalty) * weight
                penalty = min(raw_penalty, per_term_cap)

                if raw_penalty > per_term_cap:
                    logger.debug(
                        "Clamping cohesion penalty for tag %s (G%d): %d -> %d",
                        tag,
                        g,
                        raw_penalty,
                        per_term_cap,
                    )

                self.objectives.append(used * penalty)
                self.max_objective_bound += penalty

                if self.max_objective_bound > (1 << 60) - 1:
                    raise ValueError(
                        "Aggregate objective (cohesion) exceeds CP-SAT safety bound."
                    )

    def add_participant_symmetry_breaking(self) -> None:
        """Enforces ordering for identical participants to reduce search space.

        Identifies sets of participants with identical scores, groupers, and
        separators, then forces them to be assigned to groups in a non-decreasing
        index order. This prunes millions of redundant permutations.
        """
        identity_map: dict[tuple, list[int]] = {}

        for i, p in enumerate(self.participants):
            # Sort scores and tags for stable, order-insensitive hashing
            sorted_scores = tuple(sorted(p.scores.items()))
            identity = (
                sorted_scores,
                tuple(sorted(TagProcessor.get_tags(p.groupers))),
                tuple(sorted(TagProcessor.get_tags(p.separators))),
            )
            identity_map.setdefault(identity, []).append(i)

        # Sort identity buckets by the first index in each to ensure
        # absolute determinism regardless of dictionary iteration order.
        sorted_identities = sorted(identity_map.keys(), key=lambda k: identity_map[k][0])

        for identity in sorted_identities:
            indices = identity_map[identity]
            if len(indices) <= 1:
                continue

            # For identical participants, force non-decreasing group index
            # group_idx_i = sum(g * x[i, g])
            for k in range(len(indices) - 1):
                p1, p2 = indices[k], indices[k + 1]
                g_idx1 = sum(g * self.x[(p1, g)] for g in range(self.num_groups))
                g_idx2 = sum(g * self.x[(p2, g)] for g in range(self.num_groups))
                self.model.Add(g_idx1 <= g_idx2)

    def add_solution_hints(self) -> None:
        """Applies previous assignments as solver hints for warm starts.

        To ensure compatibility with symmetry-breaking ordering constraints,
        hints for identical participants are sorted by group ID before being
        applied. This preserves the feasible search space while establishing
        an immediate upper bound.
        """
        if not self.cfg.hints:
            return

        # 1. Collect all valid hints from configuration
        hinted_groups: dict[int, int] = {}
        for p_idx, p in enumerate(self.participants):
            group_id = None
            if p.fingerprint in self.cfg.hints:
                group_id = self.cfg.hints[p.fingerprint]
            elif p.original_index is not None and p.original_index in self.cfg.hints:
                group_id = self.cfg.hints[p.original_index]

            if group_id is not None:
                try:
                    g_idx = int(group_id) - 1
                    if 0 <= g_idx < self.num_groups:
                        hinted_groups[p_idx] = g_idx
                except (ValueError, TypeError):
                    continue

        # 2. Group participants by symmetry buckets (identical identity)
        symmetry_buckets: dict[tuple, list[int]] = {}
        for p_idx, p in enumerate(self.participants):
            sorted_scores = tuple(sorted(p.scores.items()))
            identity = (
                sorted_scores,
                tuple(sorted(TagProcessor.get_tags(p.groupers))),
                tuple(sorted(TagProcessor.get_tags(p.separators))),
            )
            symmetry_buckets.setdefault(identity, []).append(p_idx)

        # 3. Apply hints so identical participants follow ordering constraints
        # Sort buckets by the first index in each to ensure absolute determinism.
        sorted_bucket_keys = sorted(
            symmetry_buckets.keys(), key=lambda k: symmetry_buckets[k][0]
        )

        for identity in sorted_bucket_keys:
            indices = symmetry_buckets[identity]
            # Get all hinted group assignments for this bucket
            valid_hinted_g_idxs = sorted(
                hinted_groups[idx] for idx in indices if idx in hinted_groups
            )
            # Re-assign hinted group IDs in sorted order to this bucket
            for p_idx, g_idx in zip(indices, valid_hinted_g_idxs, strict=False):
                self.model.AddHint(self.x[(p_idx, g_idx)], 1)

    def get_model(self) -> cp_model.CpModel:
        """Finalizes and returns the model with tie-breaking."""
        # Main objective: minimize sum of weighted deviations and cohesion penalties
        main_objective = sum(self.objectives)

        # Tie-breaker: small penalty for high group indices to force canonical choice
        # when multiple equivalent optima exist. This ensures absolute determinism.
        # multiplier is 1 to keep it far below any real objective term.
        tie_breaker = sum(
            g * self.x[(i, g)]
            for i in range(self.num_people)
            for g in range(self.num_groups)
        )

        # Combine with huge multiplier for main objective
        # (1 << 30) is roughly 10^9, safe given our safety caps.
        self.model.Minimize(main_objective * 1000 + tie_breaker)
        return self.model


def _is_missing(value: object) -> bool:
    """Returns True for None and any pandas/NumPy scalar missing value."""
    if value is None:
        return True
    try:
        return bool(pd.isna(value))
    except (TypeError, ValueError):
        return False


def _clean_tag_cell(value: object) -> str:
    """Coerces a raw tag cell to a string, treating NaN/None as empty."""
    if _is_missing(value):
        return ""
    return str(value)


def _clean_score_cell(value: object) -> float:
    """Coerces a raw score cell to float, treating missing/blank as 0.0."""
    if _is_missing(value):
        return 0.0
    if isinstance(value, str) and not value.strip():
        return 0.0
    try:
        return float(value)
    except (TypeError, ValueError):
        return 0.0


def solve_with_ortools(
    participants_raw: list[dict], cfg: SolverConfig
) -> tuple[list[dict], int, float]:
    """Primary entry point for the solver.

    Args:
        participants_raw: List of dictionaries from input files.
        cfg: The solver configuration parameters.

    Returns:
        Tuple: (grouped_participants, solver_status, elapsed_time)
    """
    # Convert raw dicts to Participant models
    participants = []
    for i, p in enumerate(participants_raw):
        raw_name = p.get(config.COL_NAME)
        name = str(raw_name) if not _is_missing(raw_name) else f"P{i}"

        raw_idx = p.get("_original_index")
        orig_idx = int(raw_idx) if not _is_missing(raw_idx) else i

        participants.append(
            Participant(
                name=name,
                scores={
                    str(k): _clean_score_cell(v)
                    for k, v in p.items()
                    if str(k).startswith(config.SCORE_PREFIX)
                },
                groupers=_clean_tag_cell(p.get(config.COL_GROUPER)),
                separators=_clean_tag_cell(p.get(config.COL_SEPARATOR)),
                original_index=orig_idx,
            )
        )

    start_time = time.time()

    # Setup Builder and Strategy
    builder = ConstraintBuilder(participants, cfg)
    builder.build_variables()

    groupers, separators = TagProcessor.process_participants(
        participants, cfg.conflict_priority
    )
    builder.add_pigeonhole_constraints(separators)

    strategy = (
        AdvancedScoring()
        if cfg.opt_mode == OptimizationMode.ADVANCED
        else SimpleScoring()
    )
    builder.add_scoring_objectives(strategy)
    builder.add_cohesion_penalties(groupers)
    builder.add_participant_symmetry_breaking()
    builder.add_solution_hints()

    model = builder.get_model()

    # Solver Execution
    solver_inst = cp_model.CpSolver()
    solver_inst.parameters.max_time_in_seconds = float(cfg.timeout_seconds)
    # Force determinism by using a single search worker and fixed seed
    solver_inst.parameters.num_search_workers = 1
    solver_inst.parameters.random_seed = 42

    apply_solver_tuning(solver_inst)

    status = solver_inst.Solve(model, SolutionPrinter(start_time))
    elapsed = time.time() - start_time

    results = []
    if status in (cp_model.OPTIMAL, cp_model.FEASIBLE):
        # Format results back to list of dicts for UI compatibility
        for i, p in enumerate(participants):
            assigned_group = -1
            for g in range(cfg.num_groups):
                if solver_inst.Value(builder.x[(i, g)]) == 1:
                    assigned_group = g + 1
                    break

            p_dict = {
                config.COL_NAME: p.name,
                config.COL_GROUP: assigned_group,
                config.COL_GROUPER: p.groupers,
                config.COL_SEPARATOR: p.separators,
                "_original_index": p.original_index,
                "participant_fingerprint": p.fingerprint,
            }
            # Unpack MappingsProxyType for compatibility
            p_dict.update(dict(p.scores))
            results.append(p_dict)

    return results, status, elapsed
