"""Core optimization logic using Google OR-Tools.

Refactored to use Builder and Strategy patterns for professional standards,
SRP, and Open/Closed principles.
"""

import math
import time
from abc import ABC, abstractmethod
from typing import Any

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
    """Callback to log intermediate solutions found by the solver.

    Attributes:
        __start_time: Time when optimization started.
        __solution_count: Number of solutions found.
        __last_log_time: Last time progress was logged.
    """

    def __init__(self, start_time: float) -> None:
        """Initializes the solution printer.

        Args:
            start_time: The unix timestamp when the solver started.
        """
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
                f"Solver Progress: {self.__solution_count} solutions | "
                f"Objective: {obj} | Elapsed: {elapsed:.1f}s",
            )
            self.__last_log_time = current_time


class TagProcessor:
    """Handles tokenization and conflict resolution for constraint tags."""

    @staticmethod
    def get_tags(val: str) -> set[str]:
        """Extracts unique characters as tags, ignoring whitespace and commas.

        Args:
            val: The raw string containing tags.

        Returns:
            A set of unique tag characters.
        """
        if not val or not isinstance(val, str):
            return set()
        return {c for c in val if not c.isspace() and c != ","}

    @classmethod
    def process_participants(
        cls,
        participants: list[Participant],
        priority: ConflictPriority,
    ) -> tuple[dict[str, set[int]], dict[str, set[int]]]:
        """Generates grouper and separator sets with conflict resolution.

        Args:
            participants: List of participant objects.
            priority: Which tag type wins in case of conflict.

        Returns:
            A tuple containing (grouper_sets, separator_sets).
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

        # Conflict Resolution
        if priority == ConflictPriority.GROUPERS:
            for s_set in separators.values():
                for g_set in groupers.values():
                    overlap = s_set.intersection(g_set)
                    if len(overlap) > 1:
                        s_set.difference_update(overlap)
        else:
            for g_set in groupers.values():
                for s_set in separators.values():
                    overlap = g_set.intersection(s_set)
                    if len(overlap) > 1:
                        g_set.difference_update(overlap)

        return groupers, separators


class ScoringStrategy(ABC):
    """Abstract base for different optimization topologies."""

    @abstractmethod
    def get_score_vectors(
        self,
        participants: list[Participant],
        cfg: SolverConfig,
    ) -> list[tuple[str, list[int], int]]:
        """Returns (name, scores, weight_multiplier) for each dimension.

        Args:
            participants: List of participants.
            cfg: Solver configuration.

        Returns:
            List of tuples (dimension_name, score_list, weight).
        """


class AdvancedScoring(ScoringStrategy):
    """Balances each score dimension independently."""

    def get_score_vectors(
        self,
        participants: list[Participant],
        cfg: SolverConfig,
    ) -> list[tuple[str, list[int], int]]:
        """Returns score vectors for each dimension.

        Args:
            participants: List of participants.
            cfg: Solver configuration.

        Returns:
            List of tuples (dimension_name, score_list, weight).
        """
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
        self,
        participants: list[Participant],
        cfg: SolverConfig,
    ) -> list[tuple[str, list[int], int]]:
        """Returns a single score vector representing the weighted total.

        Args:
            participants: List of participants.
            cfg: Solver configuration.

        Returns:
            List containing one tuple (name, scores, weight).
        """
        scores = []
        for p in participants:
            total = sum(
                p.scores.get(c, 0.0) * cfg.score_weights.get(c, 1.0)
                for c in cfg.score_weights
            )
            scores.append(int(round(total * config.SCALE_FACTOR)))
        return [("simple_total", scores, 100)]


class ConstraintBuilder:
    """Stateful builder for constructing the CP-SAT partition model.

    Attributes:
        participants: List of participants to process.
        cfg: Optimization configuration.
        num_people: Total count of participants.
        num_groups: Total count of target groups.
        model: The CP-SAT model being built.
        x: Map of (participant_index, group_index) to CP-SAT Boolean variables.
        objectives: List of optimization terms to minimize.
        max_objective_bound: Theoretical maximum sum of all objective terms.
    """

    def __init__(self, participants: list[Participant], cfg: SolverConfig) -> None:
        """Initializes the builder.

        Args:
            participants: List of participant models.
            cfg: Solver configuration.
        """
        self.participants = participants
        self.cfg = cfg
        self.num_people = len(participants)
        self.num_groups = cfg.num_groups
        self.model = cp_model.CpModel()
        self.x: dict[tuple[int, int], cp_model.IntVar] = {}
        self.objectives: list[cp_model.IntVar] = []
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
                == self.cfg.group_capacities[g],
            )

    def add_pigeonhole_constraints(self, separators: dict[str, set[int]]) -> None:
        """Ensures separator tags are spread across groups.

        Args:
            separators: Mapping of separator tags to sets of participant indices.
        """
        for tag, s_set in separators.items():
            if not s_set or not tag.strip():
                continue
            limit = math.ceil(len(s_set) / self.num_groups)
            for g in range(self.num_groups):
                self.model.Add(sum(self.x[(i, g)] for i in s_set) <= limit)

    def add_scoring_objectives(self, strategy: ScoringStrategy) -> None:
        """Builds multi-objective minimization for group score variance.

        Args:
            strategy: The scoring strategy to use for vector generation.
        """
        vectors = strategy.get_score_vectors(self.participants, self.cfg)
        first_vec = True

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
                    f"Extreme score range in {name} risking overflow. "
                    f"Scaling down by {scale_down}.",
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

            # Symmetry breaking for equal-capacity groups
            if first_vec:
                for g1 in range(self.num_groups):
                    for g2 in range(g1 + 1, self.num_groups):
                        if (
                            self.cfg.group_capacities[g1]
                            == self.cfg.group_capacities[g2]
                        ):
                            self.model.Add(g_sums[g1] <= g_sums[g2])
                first_vec = False

            for g in range(self.num_groups):
                self.model.Add(
                    g_sums[g]
                    == sum(self.x[(i, g)] * scores[i] for i in range(self.num_people)),
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
        # Prevent 64-bit integer overflow in CP-SAT
        base_penalty = min(self.max_objective_bound * 10 + 1000, (1 << 60) - 1)

        for tag, g_set in groupers.items():
            if len(g_set) <= 1:
                continue
            for g in range(self.num_groups):
                used = self.model.NewBoolVar(f"used_{tag}_{g}")
                self.model.AddMaxEquality(used, [self.x[(i, g)] for i in g_set])
                # Small bias to keep large groups for complex tag sets
                cap_penalty = self.cfg.group_capacities[g] * 10
                self.objectives.append(used * (base_penalty + cap_penalty))

    def get_model(self) -> cp_model.CpModel:
        """Finalizes and returns the model.

        Returns:
            The configured CP-SAT model.
        """
        self.model.Minimize(sum(self.objectives))
        return self.model


def solve_with_ortools(
    participants_raw: list[dict[str, Any]],
    cfg: SolverConfig,
) -> tuple[list[dict[str, Any]], int, float]:
    """Primary entry point for the solver.

    Args:
        participants_raw: List of participant dictionaries.
        cfg: Solver configuration.

    Returns:
        Tuple: (grouped_participants, solver_status, elapsed_time)
    """
    # Convert raw dicts to Participant models
    participants = [
        Participant(
            name=p.get(config.COL_NAME, "Unknown"),
            scores={
                k: float(v) for k, v in p.items() if k.startswith(config.SCORE_PREFIX)
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
        participants,
        cfg.conflict_priority,
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
            p_dict.update(p.scores)
            results.append(p_dict)

    return results, status, elapsed
