"""Group Optimizer for the Group Balancer application.

This module provides the main optimization coordinator that integrates
advantage distribution and score balancing phases, validates results,
and implements optimization termination conditions.
"""

from typing import List, Optional, Tuple
import statistics
import time
from .models import Participant, Group, GroupResult
from .balance_engine import BalanceEngine


class GroupOptimizer:
    """Main optimization coordinator for creating balanced groups."""
    
    def __init__(self, max_iterations: int = 100, convergence_threshold: float = 0.001):
        """Initialize the Group Optimizer.
        
        Args:
            max_iterations: Maximum number of optimization iterations
            convergence_threshold: Minimum improvement threshold for convergence
        """
        self.balance_engine = BalanceEngine()
        self.max_iterations = max_iterations
        self.convergence_threshold = convergence_threshold
    
    def optimize_groups(self, participants: List[Participant], group_count: int) -> GroupResult:
        """Optimize group assignments with comprehensive validation and quality metrics.
        
        This is the main entry point that coordinates the optimization process,
        validates inputs, runs multiple optimization attempts, and selects the
        best result based on quality metrics.
        
        Args:
            participants: List of participants to distribute
            group_count: Number of groups to create
            
        Returns:
            GroupResult with optimized group assignments
            
        Raises:
            ValueError: If inputs are invalid
        """
        # Input validation
        self._validate_inputs(participants, group_count)
        
        # Run multiple optimization attempts to find the best solution
        best_result = None
        best_quality_score = float('inf')
        
        # Try multiple optimization runs with different strategies
        optimization_attempts = min(5, max(1, len(participants) // 10))
        
        for attempt in range(optimization_attempts):
            try:
                # Run optimization with the balance engine
                result = self.balance_engine.optimize_groups(participants, group_count)
                
                # Validate the result
                if not self._validate_result(result, participants, group_count):
                    continue
                
                # Calculate quality metrics
                quality_score = self._calculate_quality_score(result)
                
                # Keep the best result
                if quality_score < best_quality_score:
                    best_quality_score = quality_score
                    best_result = result
                    
            except Exception as e:
                # Log the error but continue with other attempts
                continue
        
        if best_result is None:
            raise RuntimeError("Failed to generate a valid group optimization result")
        
        # Final validation and quality enhancement
        enhanced_result = self._enhance_result_quality(best_result, participants)
        
        return enhanced_result
    
    def _validate_inputs(self, participants: List[Participant], group_count: int) -> None:
        """Validate input parameters for optimization.
        
        Args:
            participants: List of participants to validate
            group_count: Number of groups to validate
            
        Raises:
            ValueError: If inputs are invalid
        """
        if not participants:
            raise ValueError("Cannot optimize groups with no participants")
        
        if group_count <= 0:
            raise ValueError("Group count must be positive")
        
        if len(participants) < group_count:
            raise ValueError(f"Cannot create {group_count} groups with only {len(participants)} participants")
        
        # Validate participant data
        for i, participant in enumerate(participants):
            if not isinstance(participant.score, (int, float)):
                raise ValueError(f"Participant {i} has invalid score: {participant.score}")
            
            if not participant.name or not participant.name.strip():
                raise ValueError(f"Participant {i} has empty or invalid name")
    
    def _validate_result(self, result: GroupResult, participants: List[Participant], group_count: int) -> bool:
        """Validate that the optimization result meets all requirements.
        
        Args:
            result: The optimization result to validate
            participants: Original list of participants
            group_count: Expected number of groups
            
        Returns:
            True if result is valid, False otherwise
        """
        if not result or not result.groups:
            return False
        
        # Check correct number of groups
        if len(result.groups) != group_count:
            return False
        
        # Check that all groups have members (unless impossible)
        empty_groups = sum(1 for group in result.groups if not group.members)
        if empty_groups > 0 and len(participants) >= group_count:
            return False
        
        # Check that all participants are assigned exactly once
        assigned_participants = []
        for group in result.groups:
            assigned_participants.extend(group.members)
        
        if len(assigned_participants) != len(participants):
            return False
        
        # Check that no participant is assigned twice
        assigned_names = [p.name for p in assigned_participants]
        if len(set(assigned_names)) != len(assigned_names):
            return False
        
        # Check that all original participants are present
        original_names = {p.name for p in participants}
        result_names = {p.name for p in assigned_participants}
        if original_names != result_names:
            return False
        
        # Validate advantage distribution fairness
        if not self._validate_advantage_distribution(result):
            return False
        
        # Use the built-in validation method
        return result.is_valid()
    
    def _validate_advantage_distribution(self, result: GroupResult) -> bool:
        """Validate that advantaged participants are distributed fairly.
        
        Args:
            result: The optimization result to validate
            
        Returns:
            True if advantage distribution is fair, False otherwise
        """
        advantage_counts = [group.advantage_count for group in result.groups]
        
        if not advantage_counts:
            return True
        
        min_count = min(advantage_counts)
        max_count = max(advantage_counts)
        
        # The difference between max and min should be at most 1
        # This ensures fair distribution as specified in requirements
        return (max_count - min_count) <= 1
    
    def _calculate_quality_score(self, result: GroupResult) -> float:
        """Calculate a comprehensive quality score for the optimization result.
        
        Lower scores indicate better quality. The score combines multiple metrics:
        - Score variance (primary metric)
        - Group size balance
        - Advantage distribution fairness
        
        Args:
            result: The optimization result to score
            
        Returns:
            Quality score (lower is better)
        """
        # Primary metric: score variance
        score_variance = result.score_variance
        
        # Secondary metric: group size balance
        group_sizes = [len(group.members) for group in result.groups]
        size_variance = statistics.variance(group_sizes) if len(group_sizes) > 1 else 0.0
        
        # Tertiary metric: advantage distribution fairness
        advantage_counts = result.advantage_distribution
        advantage_variance = statistics.variance(advantage_counts) if len(advantage_counts) > 1 else 0.0
        
        # Combine metrics with weights
        quality_score = (
            score_variance * 1.0 +          # Primary weight
            size_variance * 0.1 +           # Secondary weight
            advantage_variance * 0.05       # Tertiary weight
        )
        
        return quality_score
    
    def _enhance_result_quality(self, result: GroupResult, participants: List[Participant]) -> GroupResult:
        """Enhance the quality of the optimization result through additional refinements.
        
        Args:
            result: The optimization result to enhance
            participants: Original list of participants
            
        Returns:
            Enhanced GroupResult
        """
        # Create a copy of the result for enhancement
        enhanced_groups = []
        for group in result.groups:
            enhanced_group = Group(id=group.id, members=group.members.copy())
            enhanced_groups.append(enhanced_group)
        
        # Apply additional local optimizations
        self._apply_final_optimizations(enhanced_groups)
        
        # Recalculate statistics
        enhanced_variance = self.balance_engine.calculate_score_variance(enhanced_groups)
        enhanced_distribution = [group.advantage_count for group in enhanced_groups]
        
        return GroupResult(
            groups=enhanced_groups,
            score_variance=enhanced_variance,
            advantage_distribution=enhanced_distribution
        )
    
    def _apply_final_optimizations(self, groups: List[Group]) -> None:
        """Apply final optimization passes to improve group balance.
        
        Args:
            groups: List of groups to optimize (modified in place)
        """
        # Apply multiple optimization passes
        for _ in range(3):  # Limited number of passes
            improved = self._try_cross_group_improvements(groups)
            if not improved:
                break  # No more improvements possible
    
    def _try_cross_group_improvements(self, groups: List[Group]) -> bool:
        """Try improvements across all groups.
        
        Args:
            groups: List of groups to improve
            
        Returns:
            True if any improvement was made
        """
        current_variance = self.balance_engine.calculate_score_variance(groups)
        
        # Try swapping participants between all pairs of groups
        for i in range(len(groups)):
            for j in range(i + 1, len(groups)):
                if self._try_beneficial_swap_between_groups(groups[i], groups[j]):
                    new_variance = self.balance_engine.calculate_score_variance(groups)
                    if new_variance < current_variance - self.convergence_threshold:
                        return True  # Improvement found
        
        return False
    
    def _try_beneficial_swap_between_groups(self, group1: Group, group2: Group) -> bool:
        """Try to find and execute a beneficial swap between two groups.
        
        Args:
            group1: First group
            group2: Second group
            
        Returns:
            True if a beneficial swap was made
        """
        if not group1.members or not group2.members:
            return False
        
        current_avg1 = group1.average_score
        current_avg2 = group2.average_score
        current_variance = statistics.variance([current_avg1, current_avg2])
        
        best_swap = None
        best_variance = current_variance
        
        # Try swapping each non-advantaged participant
        for p1 in group1.members:
            for p2 in group2.members:
                # Don't swap advantaged participants (they're strategically placed)
                if p1.has_advantage or p2.has_advantage:
                    continue
                
                # Calculate new averages after swap
                group1_total = sum(m.score for m in group1.members) - p1.score + p2.score
                group2_total = sum(m.score for m in group2.members) - p2.score + p1.score
                
                new_avg1 = group1_total / len(group1.members)
                new_avg2 = group2_total / len(group2.members)
                
                new_variance = statistics.variance([new_avg1, new_avg2])
                
                if new_variance < best_variance - self.convergence_threshold:
                    best_variance = new_variance
                    best_swap = (p1, p2)
        
        # Execute the best swap if found
        if best_swap:
            p1, p2 = best_swap
            group1.members.remove(p1)
            group2.members.remove(p2)
            group1.add_member(p2)
            group2.add_member(p1)
            return True
        
        return False
    
    def get_optimization_metrics(self, result: GroupResult) -> dict:
        """Get detailed optimization metrics for the result.
        
        Args:
            result: The optimization result to analyze
            
        Returns:
            Dictionary containing various optimization metrics
        """
        if not result or not result.groups:
            return {}
        
        # Basic statistics
        group_sizes = [len(group.members) for group in result.groups]
        group_averages = [group.average_score for group in result.groups if group.members]
        
        metrics = {
            'score_variance': result.score_variance,
            'group_count': len(result.groups),
            'total_participants': sum(group_sizes),
            'average_group_size': statistics.mean(group_sizes) if group_sizes else 0,
            'group_size_variance': statistics.variance(group_sizes) if len(group_sizes) > 1 else 0,
            'min_group_size': min(group_sizes) if group_sizes else 0,
            'max_group_size': max(group_sizes) if group_sizes else 0,
            'advantage_distribution': result.advantage_distribution,
            'advantage_distribution_variance': statistics.variance(result.advantage_distribution) if len(result.advantage_distribution) > 1 else 0,
            'quality_score': self._calculate_quality_score(result)
        }
        
        if group_averages:
            metrics.update({
                'min_group_average': min(group_averages),
                'max_group_average': max(group_averages),
                'overall_average': statistics.mean(group_averages),
                'group_average_range': max(group_averages) - min(group_averages)
            })
        
        return metrics