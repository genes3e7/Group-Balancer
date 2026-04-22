"""
Core optimization logic using Google OR-Tools.

Refactored to use Builder and Strategy patterns for professional standards,
SRP, and Open/Closed principles.
"""

import math
import time
from abc import ABC, abstractmethod

from ortools.sat.python import cp_model

from src import logger
from src.core import config
from src.core.models import (
    ConflictPriority,
    OptimizationMode,
    Participant,
    SolverConfig,
)


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
        if not val or not isinstance(val, str):
            return set()
        return {c for c in val if not c.isspace() and c != ","}

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
            scores = [
                int(round(p.scores.get(col, 0.0) * config.SCALE_FACTOR))
                for p in participants
            ]
            weight_m = int(round(weight * 100))
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
            scores.append(int(round(total * config.SCALE_FACTOR)))
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
        for tag, s_set in separators.items():
            if not s_set or not tag.strip():
                continue

            n_tag = len(s_set)

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
                self.model.Add(sum(self.x[(i, g)] for i in s_set) <= limit)

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
            if diff_bound * weight_m > 2**60:
                scale_down = math.ceil((diff_bound * weight_m) / 2**60)
                logger.warning(
                    "Extreme score range in %s risking overflow. Scaling by %d.",
                    name,
                    scale_down,
                )
                scores = [int(round(s / scale_down)) for s in scores]
                total_score = sum(scores)
                min_sum = sum(s for s in scores if s < 0)
                max_sum = sum(s for s in scores if s > 0)
                diff_bound = max(1, (max_sum - min_sum) * self.num_people * 2)

            g_sums = [
                self.model.NewIntVar(min_sum, max_sum, f"sum_{name}_{g}")
                for g in range(self.num_groups)
            ]

            # Advanced Symmetry Breaking: Enforce ordering for identical capacity
            # groups on at most one canonical dimension. This prunes G! search
            # branches without over-constraining multi-dimensional weights.
            if weight_m > 0 and not getattr(self, "_symmetry_broken", False):
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
                diff = self.model.NewIntVar(-diff_bound, diff_bound, f"diff_{name}_{g}")
                self.model.Add(diff == g_sums[g] * self.num_people - target)

                abs_diff = self.model.NewIntVar(0, diff_bound, f"abs_{name}_{g}")
                self.model.AddAbsEquality(abs_diff, diff)

                w_diff = self.model.NewIntVar(0, diff_bound * weight_m, f"w_{name}_{g}")
                self.model.Add(w_diff == abs_diff * weight_m)
                self.objectives.append(w_diff)
                self.max_objective_bound += diff_bound * weight_m

    def add_cohesion_penalties(self, groupers: dict[str, set[int]]) -> None:
        """Adds penalties for splitting grouper tags.

        Args:
            groupers: Mapping of grouper tags to sets of participant indices.
        """
        # Prevent 64-bit integer overflow in CP-SAT.
        # Use a more conservative Big-M value. max_objective_bound is already scaled.
        # Ensure that (base_penalty * num_tags * num_groups) fits in 2^62.
        # Default to a safe large constant if no scoring objectives added yet.
        safe_max = 1 << 52  # Much more conservative than 1 << 60
        base_penalty = min(max(10000, self.max_objective_bound * 2), safe_max)

        for tag, g_set in groupers.items():
            if len(g_set) <= 1:
                continue
            for g in range(self.num_groups):
                used = self.model.NewBoolVar(f"used_{tag}_{g}")
                self.model.AddMaxEquality(used, [self.x[(i, g)] for i in g_set])

                # Incorporate SolverConfig.grouper_weight and clamp
                weight = self.cfg.grouper_weight
                cap_penalty = self.cfg.group_capacities[g] * 10
                # Final term must fit within objective sum.
                penalty = min((base_penalty + cap_penalty) * weight, safe_max)
                self.objectives.append(used * penalty)

    def get_model(self) -> cp_model.CpModel:
        """Finalizes and returns the model."""
        self.model.Minimize(sum(self.objectives))
        return self.model


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
    participants = [
        Participant(
            name=p.get(config.COL_NAME, "Unknown"),
            scores={
                str(k): float(v)
                for k, v in p.items()
                if str(k).startswith(config.SCORE_PREFIX)
            },
            groupers=str(p.get(config.COL_GROUPER, "")),
            separators=str(p.get(config.COL_SEPARATOR, "")),
            original_index=i,
        )
        for i, p in enumerate(participants_raw)
    ]

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

    model = builder.get_model()

    # Solver Execution
    solver_inst = cp_model.CpSolver()
    solver_inst.parameters.max_time_in_seconds = float(cfg.timeout_seconds)
    solver_inst.parameters.num_search_workers = cfg.num_workers

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
            }
            # Unpack MappingsProxyType for compatibility
            p_dict.update(dict(p.scores))
            results.append(p_dict)

    return results, status, elapsed
