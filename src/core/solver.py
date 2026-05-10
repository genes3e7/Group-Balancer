"""Core optimization logic using Google OR-Tools.

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
    Participant,
    SolverConfig,
)
from src.core.tag_utils import canonicalize_tags


def apply_solver_tuning(solver_inst: cp_model.CpSolver) -> None:
    """Applies optimal CP-SAT parameters for group partitioning math.

    Args:
        solver_inst (cp_model.CpSolver): The OR-Tools solver instance to configure.
    """
    solver_inst.parameters.linearization_level = 0
    solver_inst.parameters.symmetry_level = 2


class SolutionPrinter(cp_model.CpSolverSolutionCallback):
    """Callback to log intermediate solutions found by the solver."""

    def __init__(self, start_time: float):
        """Initializes the printer with the solver start time.

        Args:
            start_time (float): Time the solver started execution.
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
        """Extracts unique characters as tags, ignoring whitespace and commas.

        Args:
            val (str): Raw string containing tags.

        Returns:
            set[str]: Set of unique character tags.
        """
        return canonicalize_tags(val)

    @classmethod
    def process_participants(
        cls, participants: list[Participant], priority: ConflictPriority
    ) -> tuple[dict[str, set[int]], dict[str, set[int]]]:
        """Generates grouper and separator sets with conflict resolution.

        Args:
            participants (list[Participant]): List of participants to process.
            priority (ConflictPriority): Priority to resolve overlapping tags.

        Returns:
            tuple[dict[str, set[int]], dict[str, set[int]]]: Mappings of tags to
                participant indices.
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
        """Returns score vectors for each dimension to be optimized.

        Args:
            participants (list[Participant]): List of participants.
            cfg (SolverConfig): Solver configuration.

        Returns:
            list[tuple[str, list[int], int]]: List of (name, scores, weight) tuples.
        """
        pass


class AdvancedScoring(ScoringStrategy):
    """Balances each score dimension independently with normalization."""

    def get_score_vectors(
        self, participants: list[Participant], cfg: SolverConfig
    ) -> list[tuple[str, list[int], int]]:
        """Generates normalized score vectors for each dimension.

        Args:
            participants (list[Participant]): List of participants.
            cfg (SolverConfig): Solver configuration.

        Returns:
            list[tuple[str, list[int], int]]: List of normalized score vectors.
        """
        num_p = len(participants)
        num_g = cfg.num_groups

        # Dynamic Precision Scaling:
        # Prevents L2 squared math from exceeding CP-SAT's 64-bit integer limit.
        max_w = max(cfg.score_weights.values()) if cfg.score_weights else 1.0
        max_w = max(1.0, max_w)

        # M / (G * W * N^4) is a safe lower bound for the resolution ratio.
        # We aim to keep total Balance Tier sum below 10^15.
        denom = num_g * max_w * (num_p**4)
        safe_ratio = 10**15 / denom
        max_r_per_p = math.sqrt(safe_ratio)

        # Clamp between 1.0 and 1000.0 (user's target precision)
        res_per_p = max(1.0, min(1000.0, max_r_per_p))
        norm_multiplier = int(res_per_p * num_p)

        vectors = []
        for col in sorted(cfg.score_weights.keys()):
            weight = cfg.score_weights[col]
            if weight == 0:
                continue

            raw_scores = [p.scores.get(col, 0.0) for p in participants]
            scaled_raw = [int(round(s * config.SCALE_FACTOR)) for s in raw_scores]
            raw_total = sum(abs(s) for s in scaled_raw)

            if raw_total == 0:
                raise ValueError(f"Score dimension '{col}' has weight but sum is 0.")

            scores = [int(round((s * norm_multiplier) / raw_total)) for s in scaled_raw]

            vectors.append((col, scores, int(max(1, round(weight)))))
        return vectors


class ConstraintBuilder:
    """Stateful builder for constructing the CP-SAT partition model."""

    def __init__(self, participants: list[Participant], cfg: SolverConfig):
        """Initializes the model builder.

        Args:
            participants (list[Participant]): List of participants.
            cfg (SolverConfig): Solver configuration.
        """
        self.participants = participants
        self.cfg = cfg
        self.num_people = len(participants)
        self.num_groups = cfg.num_groups
        self.model = cp_model.CpModel()
        self.x = {}  # (p_idx, g_idx) -> BoolVar
        self.objectives = []
        self._symmetry_broken = False

        if cfg.conflict_priority == ConflictPriority.SEPARATORS:
            self.sep_multiplier = config.TIER_HI_MULTIPLIER
            self.group_multiplier = config.TIER_LO_MULTIPLIER
        else:
            self.sep_multiplier = config.TIER_LO_MULTIPLIER
            self.group_multiplier = config.TIER_HI_MULTIPLIER

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
        """Adds bit-sliced penalties for separator violations.

        Args:
            separators (dict[str, set[int]]): Mapping of separator tags to
                participant indices.
        """
        total_p = self.num_people
        penalty = self.sep_multiplier

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

                self.objectives.append(overflow * penalty)

    def add_scoring_objectives(self, strategy: ScoringStrategy) -> None:
        """Builds objectives using Max-Min Fairness and L2 Balance.

        Args:
            strategy (ScoringStrategy): Scoring strategy to use.
        """
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

            abs_diffs = []
            for g in range(self.num_groups):
                self.model.Add(
                    g_sums[g]
                    == sum(self.x[(i, g)] * scores[i] for i in range(self.num_people))
                )

                # Cross-multiplication for exact fractional comparison
                target_product = total_score * self.cfg.group_capacities[g]
                t_min, t_max = theoretical_bounds[g]
                min_diff = t_min * self.num_people - target_product
                max_diff = t_max * self.num_people - target_product
                local_diff_bound = max(abs(min_diff), abs(max_diff))

                diff = self.model.NewIntVar(
                    -local_diff_bound, local_diff_bound, f"diff_{name}_{g}"
                )
                self.model.Add(diff == g_sums[g] * self.num_people - target_product)

                # Lexicographical Fairness Component (Tier 3)
                a_diff = self.model.NewIntVar(0, local_diff_bound, f"abs_{name}_{g}")
                self.model.AddAbsEquality(a_diff, diff)
                abs_diffs.append(a_diff)

                # L2 Squared Error (Tier 4)
                sq_diff = self.model.NewIntVar(0, local_diff_bound**2, f"sq_{name}_{g}")
                self.model.AddMultiplicationEquality(sq_diff, [diff, diff])

                self.objectives.append(
                    sq_diff * weight * config.TIER_BALANCE_MULTIPLIER
                )

            # Max-Min Fairness Tier
            max_dev = self.model.NewIntVar(0, 2**31 - 1, f"maxdev_{name}")
            self.model.AddMaxEquality(max_dev, abs_diffs)
            self.objectives.append(max_dev * weight * config.TIER_FAIRNESS_MULTIPLIER)

    def add_cohesion_penalties(self, groupers: dict[str, set[int]]) -> None:
        """Adds bit-sliced penalties for splitting grouper tags.

        Args:
            groupers (dict[str, set[int]]): Mapping of grouper tags to
                participant indices.
        """
        penalty_base = self.group_multiplier

        for tag in sorted(groupers.keys()):
            g_set = groupers[tag]
            if len(g_set) <= 1:
                continue

            sorted_g_set = sorted(g_set)
            for g in range(self.num_groups):
                used = self.model.NewBoolVar(f"used_{tag}_{g}")
                self.model.AddMaxEquality(used, [self.x[(i, g)] for i in sorted_g_set])

                penalty = int(penalty_base * self.cfg.grouper_weight)
                self.objectives.append(used * penalty)

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
        if not self.cfg.hints_by_fingerprint and not self.cfg.hints_by_index:
            return

        hinted_groups: dict[int, int] = {}
        for p_idx, p in enumerate(self.participants):
            group_id = None
            if self.cfg.hints_by_fingerprint:
                group_id = self.cfg.hints_by_fingerprint.get(p.fingerprint)
            if group_id is None and self.cfg.hints_by_index:
                if p.original_index is not None:
                    group_id = self.cfg.hints_by_index.get(p.original_index)

            if group_id is not None:
                try:
                    g_idx = int(group_id) - 1
                    if 0 <= g_idx < self.num_groups:
                        hinted_groups[p_idx] = g_idx
                    else:
                        logger.warning(
                            "Warm-start hint out of range for %s: %s",
                            p.name,
                            group_id,
                        )
                except (ValueError, TypeError):
                    logger.warning(
                        "Invalid warm-start hint type for %s: %s",
                        p.name,
                        group_id,
                    )
                    continue

        # Symmetry-aware hint mapping:
        # Prevents identical participants from drifting by consuming hints
        # in canonical order.
        identity_buckets: dict[tuple, list[int]] = {}
        for p_idx, p in enumerate(self.participants):
            sorted_scores = tuple(sorted(p.scores.items()))
            identity = (
                sorted_scores,
                tuple(sorted(TagProcessor.get_tags(p.groupers))),
                tuple(sorted(TagProcessor.get_tags(p.separators))),
            )
            identity_buckets.setdefault(identity, []).append(p_idx)

        sorted_bucket_keys = sorted(
            identity_buckets.keys(), key=lambda k: identity_buckets[k][0]
        )

        for identity in sorted_bucket_keys:
            indices = identity_buckets[identity]
            valid_hinted_g_idxs = sorted(
                hinted_groups[idx] for idx in indices if idx in hinted_groups
            )
            for p_idx, g_idx in zip(indices, valid_hinted_g_idxs, strict=False):
                self.model.AddHint(self.x[(p_idx, g_idx)], 1)

    def add_branching_strategy(self) -> None:
        """Guides the solver to decide on high-impact participants first."""
        impacts = []
        for i, p in enumerate(self.participants):
            total_abs_score = sum(abs(s) for s in p.scores.values())
            impacts.append((total_abs_score, i))

        sorted_indices = [idx for _, idx in sorted(impacts, reverse=True)]

        branching_vars = []
        for p_idx in sorted_indices:
            for g_idx in range(self.num_groups):
                branching_vars.append(self.x[(p_idx, g_idx)])

        self.model.AddDecisionStrategy(
            branching_vars,
            cp_model.CHOOSE_FIRST,
            cp_model.SELECT_MAX_VALUE,
        )

    def get_model(self) -> cp_model.CpModel:
        """Finalizes and returns the model with tiering and stable tie-breaker.

        Returns:
            cp_model.CpModel: The constructed CP-SAT model.
        """
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
    """Returns True for None and any pandas/NumPy scalar missing value.

    Args:
        value (object): Value to check.

    Returns:
        bool: True if the value is missing.
    """
    if value is None:
        return True
    try:
        return bool(pd.isna(value))
    except (TypeError, ValueError):
        return False


def _clean_tag_cell(value: object) -> str:
    """Coerces a raw tag cell to a string, treating NaN/None as empty.

    Args:
        value (object): Raw cell value.

    Returns:
        str: Coerced string value.
    """
    if _is_missing(value):
        return ""
    return str(value)


def _clean_score_cell(value: object) -> float:
    """Coerces a raw score cell to float, treating missing/blank as 0.0.

    Args:
        value (object): Raw cell value.

    Returns:
        float: Coerced float value.
    """
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
        participants_raw (list[dict]): Raw data records for participants.
        cfg (SolverConfig): Optimization settings and weights.

    Returns:
        tuple[list[dict], int, float]: Results, solver status, and elapsed time.
    """
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

    strategy = AdvancedScoring()
    builder.add_scoring_objectives(strategy)
    builder.add_cohesion_penalties(groupers)
    builder.add_participant_symmetry_breaking()
    builder.add_solution_hints()
    builder.add_branching_strategy()

    model = builder.get_model()

    solver_inst = cp_model.CpSolver()
    solver_inst.parameters.max_time_in_seconds = float(cfg.timeout_seconds)
    solver_inst.parameters.num_search_workers = 8
    solver_inst.parameters.interleave_search = False
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
