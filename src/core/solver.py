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
            g_tags = cls.get_tags(p.groupers)
            s_tags = cls.get_tags(p.separators)

            for tag in g_tags:
                groupers.setdefault(tag, set()).add(i)
            for tag in s_tags:
                separators.setdefault(tag, set()).add(i)

        # Conflict Resolution: Only resolve for the same tag key
        common_tags = set(groupers.keys()) & set(separators.keys())

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
    """Abstract base for different optimization topologies."""

    @abstractmethod
    def get_score_vectors(
        self, participants: list[Participant], cfg: SolverConfig
    ) -> list[tuple[str, list[int], int]]:
        """Returns (name, scores, weight_multiplier) for each dimension."""
        pass


class AdvancedScoring(ScoringStrategy):
    """Balances each score dimension independently."""

    def get_score_vectors(
        self, participants: list[Participant], cfg: SolverConfig
    ) -> list[tuple[str, list[int], int]]:
        """Generates independent score vectors for each weight mapping."""
        vectors = []
        for col, weight in cfg.score_weights.items():
            if weight == 0:
                continue

            scores = [
                round(p.scores.get(col, 0.0) * config.SCALE_FACTOR)
                for p in participants
            ]
            # Ensure tiny positive weights are not rounded to 0
            if weight > 0:
                weight_m = max(1, round(weight * 100))
            else:
                weight_m = round(weight * 100)
            vectors.append((col, scores, weight_m))
        return vectors


class SimpleScoring(ScoringStrategy):
    """Balances a single weighted total score."""

    def get_score_vectors(
        self, participants: list[Participant], cfg: SolverConfig
    ) -> list[tuple[str, list[int], int]]:
        """Generates a single pre-aggregated score vector."""
        scores = []
        for p in participants:
            total = sum(
                p.scores.get(c, 0.0) * cfg.score_weights.get(c, 1.0)
                for c in cfg.score_weights
            )
            scores.append(round(total * config.SCALE_FACTOR))
        return [("simple_total", scores, 100)]


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
            sorted_s_set = sorted(s_set)

            for g in range(self.num_groups):
                cap_g = self.cfg.group_capacities[g]
                # To ensure feasibility: Sum of limits across all groups >= n_tag.
                # Proportional share: (n_tag * group_cap) / total_cap.
                # Baseline: ceil(proportional_share).
                # For uniform groups, this equals ceil(n_tag / G).
                # For non-uniform, it scales with group size.
                limit = min(cap_g, math.ceil((n_tag * cap_g) / total_p))

                # If the sum of these tight limits might be < n_tag due to rounding,
                # we'd have infeasibility. However, sum(ceil(p_i)) >= sum(p_i) = n_tag.
                # So math.ceil((n_tag * cap_g) / total_p) is the tightest feasible
                # limit.
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
            min_sum, max_sum = (
                sum(s for s in scores if s < 0),
                sum(s for s in scores if s > 0),
            )

            if min_sum == 0 and max_sum == 0:
                continue

            diff_bound = max(1, (max_sum - min_sum) * self.num_people * 2)
            weighted_bound = diff_bound * weight_m

            if weighted_bound > 2**60:
                extra_scale = math.ceil(weighted_bound / 2**60)
                logger.warning(
                    "Extreme score range in %s risking overflow. Scaling by %d.",
                    name,
                    extra_scale,
                )
                scores = [round(s / extra_scale) for s in scores]
                total_score = sum(scores)
                min_sum = sum(s for s in scores if s < 0)
                max_sum = sum(s for s in scores if s > 0)
                diff_bound = max(1, (max_sum - min_sum) * self.num_people * 2)
                weighted_bound = diff_bound * weight_m

                if weighted_bound > 2**60:
                    raise ValueError(
                        f"Score range for {name} is too extreme even after scaling."
                    )

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
                w_diff = self.model.NewIntVar(0, local_weighted_bound, f"w_{name}_{g}")
                self.model.Add(w_diff == abs_diff * weight_m)
                self.objectives.append(w_diff)
                self.max_objective_bound += local_weighted_bound

    def add_cohesion_penalties(self, groupers: dict[str, set[int]]) -> None:
        """Adds penalties for splitting grouper tags.

        Args:
            groupers: Mapping of grouper tags to sets of participant indices.
        """
        if self.cfg.strict_groupers:
            # Implement as hard constraints: all members of a tag must be in ONE group.
            for tag, g_set in groupers.items():
                if len(g_set) <= 1:
                    continue
                # For each group g, if any member is in g, ALL members must be in g.
                # Simplest way: sum(x[i, g] for i in g_set) == len(g_set) * used_g
                for g in range(self.num_groups):
                    used = self.model.NewBoolVar(f"used_{tag}_{g}")
                    self.model.Add(
                        sum(self.x[(i, g)] for i in g_set) == len(g_set) * used
                    )
            return

        # Prevent 64-bit integer overflow in CP-SAT.
        # aggregate_cap (e.g. 1 << 60) must fit all objectives.
        aggregate_cap = 1 << 60
        active_tags = sum(1 for g_set in groupers.values() if len(g_set) > 1)
        per_term_cap = aggregate_cap // max(1, active_tags * self.num_groups)
        base_penalty = min(self.max_objective_bound * 10 + 1000, per_term_cap)

        for tag, g_set in groupers.items():
            if len(g_set) <= 1:
                continue
            for g in range(self.num_groups):
                used = self.model.NewBoolVar(f"used_{tag}_{g}")
                self.model.AddMaxEquality(used, [self.x[(i, g)] for i in g_set])

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

        for _, indices in identity_map.items():
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
        for indices in symmetry_buckets.values():
            # Get all hinted group assignments for this bucket
            valid_hinted_g_idxs = sorted(
                hinted_groups[idx] for idx in indices if idx in hinted_groups
            )
            # Re-assign hinted group IDs in sorted order to this bucket
            for p_idx, g_idx in zip(indices, valid_hinted_g_idxs, strict=False):
                self.model.AddHint(self.x[(p_idx, g_idx)], 1)

    def get_model(self) -> cp_model.CpModel:
        """Finalizes and returns the model."""
        self.model.Minimize(sum(self.objectives))
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
