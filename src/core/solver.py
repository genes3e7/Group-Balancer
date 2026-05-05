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
        """Generates grouper and separator sets with conflict resolution."""
        groupers: dict[str, set[int]] = {}
        separators: dict[str, set[int]] = {}

        for i, p in enumerate(participants):
            g_tags = sorted(cls.get_tags(p.groupers))
            s_tags = sorted(cls.get_tags(p.separators))

            for tag in g_tags:
                groupers.setdefault(tag, set()).add(i)
            for tag in s_tags:
                separators.setdefault(tag, set()).add(i)

        common_tags = sorted(set(groupers.keys()) & set(separators.keys()))

        for tag in common_tags:
            overlap = separators[tag] & groupers[tag]
            if len(overlap) > 1:
                if priority == ConflictPriority.GROUPERS:
                    separators[tag].difference_update(overlap)
                else:
                    groupers[tag].difference_update(overlap)

        return groupers, separators


class ScoringStrategy(ABC):
    """Abstract base for different optimization topologies."""

    @abstractmethod
    def get_score_vectors(
        self, participants: list[Participant], cfg: SolverConfig
    ) -> list[tuple[str, list[int], int]]:
        """Returns score vectors for each dimension to be optimized."""
        pass


class AdvancedScoring(ScoringStrategy):
    """Balances each score dimension independently with normalization."""

    def get_score_vectors(
        self, participants: list[Participant], cfg: SolverConfig
    ) -> list[tuple[str, list[int], int]]:
        """Generates normalized score vectors for each dimension."""
        vectors = []
        for col in sorted(cfg.score_weights.keys()):
            weight = cfg.score_weights[col]
            if weight == 0:
                continue

            raw_scores = [p.scores.get(col, 0.0) for p in participants]
            scaled_raw = [int(round(s * 10_000_000_000)) for s in raw_scores]
            raw_total = sum(abs(s) for s in scaled_raw)

            if raw_total == 0:
                raise ValueError(f"Score dimension '{col}' has weight but sum is 0.")

            # Fixed personal resolution (10,000 units = 0.0001)
            norm_multiplier = 10_000 * len(participants)
            scores = [int(round((s * norm_multiplier) / raw_total)) for s in scaled_raw]

            vectors.append((col, scores, int(max(1, round(weight)))))
        return vectors


class SimpleScoring(ScoringStrategy):
    """Balances a single weighted total score with dimension normalization."""

    def get_score_vectors(
        self, participants: list[Participant], cfg: SolverConfig
    ) -> list[tuple[str, list[int], int]]:
        """Generates a single pre-aggregated and normalized score vector."""
        total_normalized_scores = [0.0] * len(participants)

        for col in sorted(cfg.score_weights.keys()):
            weight = cfg.score_weights[col]
            if weight == 0:
                continue

            raw_scores = [p.scores.get(col, 0.0) for p in participants]
            scaled_raw = [int(round(s * 10_000_000_000)) for s in raw_scores]
            raw_total = sum(abs(s) for s in scaled_raw)

            if raw_total == 0:
                raise ValueError(f"Score dimension '{col}' has weight but sum is 0.")

            norm_multiplier = 10_000 * weight * len(participants)
            for i, s in enumerate(scaled_raw):
                total_normalized_scores[i] += (s * norm_multiplier) / raw_total

        final_scores = [int(round(s)) for s in total_normalized_scores]
        return [("simple_total", final_scores, 1)]


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

    def add_separator_penalties(self, separators: dict[str, set[int]]) -> None:
        """Adds Tier 1 penalties ($10^14$) for separator violations."""
        total_p = self.num_people
        for tag in sorted(separators.keys()):
            s_set = separators[tag]
            if not s_set:
                continue

            n_tag = len(s_set)
            sorted_s_set = sorted(s_set)

            for g in range(self.num_groups):
                cap_g = self.cfg.group_capacities[g]
                limit = math.ceil((n_tag * cap_g) / total_p)

                count = sum(self.x[(i, g)] for i in sorted_s_set)
                overflow = self.model.NewIntVar(0, n_tag, f"overflow_{tag}_{g}")
                self.model.Add(overflow >= count - limit)

                # Tier 1 Penalty: 100,000,000,000,000 ($10^14$) per violation.
                penalty = 100_000_000_000_000
                self.objectives.append(overflow * penalty)
                self.max_objective_bound += n_tag * penalty

    def add_scoring_objectives(self, strategy: ScoringStrategy) -> None:
        """Builds Tier 3 objectives using L2 (Squared Error) minimization."""
        vectors = strategy.get_score_vectors(self.participants, self.cfg)

        for name, scores, weight in vectors:
            total_score = sum(scores)
            sorted_scores = sorted(scores)
            g_sums = []
            theoretical_bounds = []

            for g in range(self.num_groups):
                cap = self.cfg.group_capacities[g]
                t_min = sum(sorted_scores[:cap]) if cap > 0 else 0
                t_max = sum(sorted_scores[-cap:]) if cap > 0 else 0
                g_sums.append(self.model.NewIntVar(t_min, t_max, f"sum_{name}_{g}"))
                theoretical_bounds.append((t_min, t_max))

            if weight > 0 and not self._symmetry_broken:
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

                target_product = total_score * self.cfg.group_capacities[g]
                t_min, t_max = theoretical_bounds[g]
                min_diff = t_min * self.num_people - target_product
                max_diff = t_max * self.num_people - target_product
                local_diff_bound = max(abs(min_diff), abs(max_diff))

                diff = self.model.NewIntVar(
                    -local_diff_bound, local_diff_bound, f"diff_{name}_{g}"
                )
                self.model.Add(diff == g_sums[g] * self.num_people - target_product)

                # L2 Squared Error for peak Standard Deviation reduction
                sq_diff = self.model.NewIntVar(0, local_diff_bound**2, f"sq_{name}_{g}")
                self.model.AddMultiplicationEquality(sq_diff, [diff, diff])

                # Combine with user weight
                w_sq_diff = self.model.NewIntVar(
                    0, (local_diff_bound**2) * weight, f"wsq_{name}_{g}"
                )
                self.model.Add(w_sq_diff == sq_diff * weight)

                self.objectives.append(w_sq_diff)
                self.max_objective_bound += (local_diff_bound**2) * weight

                if self.max_objective_bound > (1 << 62) - 1:
                    raise ValueError("Objective aggregate exceeds safety bound.")

    def add_cohesion_penalties(self, groupers: dict[str, set[int]]) -> None:
        """Adds Tier 2 penalties ($10^11$) for splitting grouper tags."""
        if self.cfg.strict_groupers:
            for tag in sorted(groupers.keys()):
                g_set = groupers[tag]
                if len(g_set) <= 1:
                    continue
                sorted_g_set = sorted(g_set)
                for g in range(self.num_groups):
                    used = self.model.NewBoolVar(f"used_{tag}_{g}")
                    self.model.Add(
                        sum(self.x[(i, g)] for i in sorted_g_set) == len(g_set) * used
                    )
            return

        for tag in sorted(groupers.keys()):
            g_set = groupers[tag]
            if len(g_set) <= 1:
                continue

            sorted_g_set = sorted(g_set)
            for g in range(self.num_groups):
                used = self.model.NewBoolVar(f"used_{tag}_{g}")
                self.model.AddMaxEquality(used, [self.x[(i, g)] for i in sorted_g_set])

                # Tier 2 Penalty: 100,000,000,000 ($10^11$) per split.
                weight = self.cfg.grouper_weight
                penalty = int(100_000_000_000 * weight)

                self.objectives.append(used * penalty)
                self.max_objective_bound += penalty

                if self.max_objective_bound > (1 << 62) - 1:
                    raise ValueError("Objective aggregate exceeds safety bound.")

    def add_participant_symmetry_breaking(self) -> None:
        """Enforces ordering for identical participants."""
        identity_map: dict[tuple, list[int]] = {}

        for i, p in enumerate(self.participants):
            sorted_scores = tuple(sorted(p.scores.items()))
            identity = (
                sorted_scores,
                tuple(sorted(TagProcessor.get_tags(p.groupers))),
                tuple(sorted(TagProcessor.get_tags(p.separators))),
            )
            identity_map.setdefault(identity, []).append(i)

        sorted_identities = sorted(
            identity_map.keys(), key=lambda k: identity_map[k][0]
        )

        for identity in sorted_identities:
            indices = identity_map[identity]
            if len(indices) <= 1:
                continue

            for k in range(len(indices) - 1):
                p1, p2 = indices[k], indices[k + 1]
                g_idx1 = sum(g * self.x[(p1, g)] for g in range(self.num_groups))
                g_idx2 = sum(g * self.x[(p2, g)] for g in range(self.num_groups))
                self.model.Add(g_idx1 <= g_idx2)

    def add_solution_hints(self) -> None:
        """Applies previous assignments as solver hints for warm starts."""
        if not self.cfg.hints:
            return

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

        symmetry_buckets: dict[tuple, list[int]] = {}
        for p_idx, p in enumerate(self.participants):
            sorted_scores = tuple(sorted(p.scores.items()))
            identity = (
                sorted_scores,
                tuple(sorted(TagProcessor.get_tags(p.groupers))),
                tuple(sorted(TagProcessor.get_tags(p.separators))),
            )
            symmetry_buckets.setdefault(identity, []).append(p_idx)

        sorted_bucket_keys = sorted(
            symmetry_buckets.keys(), key=lambda k: symmetry_buckets[k][0]
        )

        for identity in sorted_bucket_keys:
            indices = symmetry_buckets[identity]
            valid_hinted_g_idxs = sorted(
                hinted_groups[idx] for idx in indices if idx in hinted_groups
            )
            for p_idx, g_idx in zip(indices, valid_hinted_g_idxs, strict=False):
                self.model.AddHint(self.x[(p_idx, g_idx)], 1)

    def add_branching_strategy(self) -> None:
        """Guides the solver to decide on high-impact participants first.

        Orders decision variables so that participants with the largest absolute
        score magnitudes are assigned to groups earlier in the search tree. This
        prunes high-variance branches faster and accelerates optimality proof.
        """
        # Calculate impact metric: sum of absolute scores across all dimensions
        impacts = []
        for i, p in enumerate(self.participants):
            total_abs_score = sum(abs(s) for s in p.scores.values())
            impacts.append((total_abs_score, i))

        # Sort indices by descending impact
        sorted_indices = [idx for _, idx in sorted(impacts, reverse=True)]

        # Decision variables: self.x[(p_idx, g_idx)]
        # Priority: Participants with highest score impact
        branching_vars = []
        for p_idx in sorted_indices:
            for g_idx in range(self.num_groups):
                branching_vars.append(self.x[(p_idx, g_idx)])

        # Apply strategy: Choose high-impact variables first
        self.model.AddDecisionStrategy(
            branching_vars,
            cp_model.CHOOSE_FIRST,
            cp_model.SELECT_MAX_VALUE,  # Try "assigned" (1) before "not" (0)
        )

    def get_model(self) -> cp_model.CpModel:
        """Finalizes and returns the model with tiering and stable tie-breaker."""
        main_objective = sum(self.objectives)

        # Lexicographic tie-breaker ($10^0$)
        tie_breaker = sum(
            g
            * (p.original_index if p.original_index is not None else i)
            * self.x[(i, g)]
            for i, p in enumerate(self.participants)
            for g in range(self.num_groups)
        )

        self.model.Minimize(main_objective + tie_breaker)
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
    """Primary entry point for the solver."""
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
    builder = ConstraintBuilder(participants, cfg)
    builder.build_variables()

    groupers, separators = TagProcessor.process_participants(
        participants, cfg.conflict_priority
    )
    builder.add_separator_penalties(separators)

    strategy = (
        AdvancedScoring()
        if cfg.opt_mode == OptimizationMode.ADVANCED
        else SimpleScoring()
    )
    builder.add_scoring_objectives(strategy)
    builder.add_cohesion_penalties(groupers)
    builder.add_participant_symmetry_breaking()
    builder.add_solution_hints()
    builder.add_branching_strategy()

    model = builder.get_model()

    solver_inst = cp_model.CpSolver()
    solver_inst.parameters.max_time_in_seconds = float(cfg.timeout_seconds)
    # Enable deterministic multi-core search
    solver_inst.parameters.num_search_workers = 8
    solver_inst.parameters.interleave_search = True
    solver_inst.parameters.random_seed = 42

    apply_solver_tuning(solver_inst)

    status = solver_inst.Solve(model, SolutionPrinter(start_time))
    elapsed = time.time() - start_time

    results = []
    if status in (cp_model.OPTIMAL, cp_model.FEASIBLE):
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
            p_dict.update(dict(p.scores))
            results.append(p_dict)

    return results, status, elapsed
