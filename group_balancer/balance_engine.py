"""Balance Engine for the Group Balancer application.

This module implements the core balancing algorithm that distributes participants
into groups while minimizing score variance and ensuring fair distribution of
advantaged participants.
"""

from typing import List
import statistics
import math
from .models import Participant, Group, GroupResult


class BalanceEngine:
    """Core algorithm for creating balanced groups."""
    
    def optimize_groups(self, participants: List[Participant], group_count: int) -> GroupResult:
        """Optimize group assignments to minimize score variance.
        
        Args:
            participants: List of participants to distribute
            group_count: Number of groups to create
            
        Returns:
            GroupResult with optimized group assignments
        """
        if not participants:
            raise ValueError("Cannot optimize groups with no participants")
        
        if group_count <= 0:
            raise ValueError("Group count must be positive")
        
        if len(participants) < group_count:
            raise ValueError("Cannot create more groups than participants")
        
        # Create empty groups
        groups = [Group(id=i, members=[]) for i in range(group_count)]
        
        # Phase 1: Distribute advantaged participants
        self.distribute_advantaged(participants, groups)
        
        # Phase 2: Balance remaining participants by score
        self.balance_scores(participants, groups)
        
        # Calculate final statistics
        score_variance = self.calculate_score_variance(groups)
        advantage_distribution = [group.advantage_count for group in groups]
        
        return GroupResult(
            groups=groups,
            score_variance=score_variance,
            advantage_distribution=advantage_distribution
        )
    
    def distribute_advantaged(self, participants: List[Participant], groups: List[Group]) -> None:
        """Distribute advantaged participants across groups fairly.
        
        This method implements score-aware distribution to balance the impact
        of advantaged participants across groups.
        
        Args:
            participants: List of all participants
            groups: List of groups to distribute into (modified in place)
        """
        # Find advantaged participants
        advantaged = [p for p in participants if p.has_advantage]
        
        if not advantaged:
            return  # No advantaged participants to distribute
        
        # Sort advantaged participants by score (highest first)
        # This helps with score-aware distribution
        advantaged.sort(key=lambda p: p.score, reverse=True)
        
        # Calculate target distribution
        group_count = len(groups)
        base_count = len(advantaged) // group_count
        extra_count = len(advantaged) % group_count
        
        # Assign advantaged participants using a score-aware approach
        group_index = 0
        for i, participant in enumerate(advantaged):
            # Determine how many this group should get
            target_for_group = base_count + (1 if group_index < extra_count else 0)
            
            # If current group is full, move to next group
            if groups[group_index].advantage_count >= target_for_group:
                group_index = (group_index + 1) % group_count
            
            # Add participant to current group
            groups[group_index].add_member(participant)
            
            # Move to next group for better distribution
            group_index = (group_index + 1) % group_count
    
    def balance_scores(self, participants: List[Participant], groups: List[Group]) -> None:
        """Balance remaining participants to minimize score variance.
        
        Args:
            participants: List of all participants
            groups: List of groups with advantaged participants already assigned
        """
        # Find participants not yet assigned to any group
        assigned_participants = []
        for group in groups:
            assigned_participants.extend(group.members)
        
        # Use participant names to identify already assigned participants
        assigned_names = {p.name for p in assigned_participants}
        remaining = [p for p in participants if p.name not in assigned_names]
        
        if not remaining:
            return  # All participants already assigned
        
        # Try multiple approaches and pick the best one
        approaches = []
        
        # Approach 1: Greedy assignment with sorted participants
        groups_copy1 = [Group(id=g.id, members=g.members.copy()) for g in groups]
        remaining_sorted = sorted(remaining, key=lambda p: p.score, reverse=True)
        self._greedy_assignment(remaining_sorted, groups_copy1)
        self._local_optimization(groups_copy1)
        variance1 = self.calculate_score_variance(groups_copy1)
        approaches.append((variance1, groups_copy1))
        
        # Approach 2: Round-robin with original order then optimize
        groups_copy2 = [Group(id=g.id, members=g.members.copy()) for g in groups]
        self._round_robin_assignment(remaining, groups_copy2)
        self._local_optimization(groups_copy2)
        variance2 = self.calculate_score_variance(groups_copy2)
        approaches.append((variance2, groups_copy2))
        
        # Approach 3: Round-robin with sorted participants then optimize
        groups_copy3 = [Group(id=g.id, members=g.members.copy()) for g in groups]
        self._round_robin_assignment(remaining_sorted, groups_copy3)
        self._local_optimization(groups_copy3)
        variance3 = self.calculate_score_variance(groups_copy3)
        approaches.append((variance3, groups_copy3))
        
        # Use the best approach
        best_variance, best_groups = min(approaches, key=lambda x: x[0])
        
        # Copy the best result back to original groups
        for i, group in enumerate(groups):
            group.members = best_groups[i].members
    
    def _greedy_assignment(self, participants: List[Participant], groups: List[Group]) -> None:
        """Assign participants using greedy algorithm.
        
        Args:
            participants: Participants to assign (sorted by score)
            groups: Groups to assign to
        """
        # Calculate target group size for balanced distribution
        total_participants = len(participants) + sum(len(g.members) for g in groups)
        target_size = total_participants // len(groups)
        
        for participant in participants:
            # Find the best group to add this participant to
            best_group = self._find_best_group_for_participant(groups, participant, target_size)
            best_group.add_member(participant)
    
    def _find_best_group_for_participant(self, groups: List[Group], participant: Participant, target_size: int) -> Group:
        """Find the best group to add a participant to.
        
        Args:
            groups: Available groups
            participant: Participant to assign
            target_size: Target size for balanced groups
            
        Returns:
            Best group for this participant
        """
        # First, filter out groups that are already at or above target size
        # unless all groups are at target size
        available_groups = [g for g in groups if len(g.members) < target_size]
        if not available_groups:
            available_groups = groups  # All groups are at target, use all
        
        # If we have more groups than remaining participants, use simple round-robin
        total_remaining = sum(len(g.members) for g in groups) + 1  # +1 for current participant
        if len(groups) >= total_remaining:
            return min(available_groups, key=lambda g: len(g.members))
        
        # Use variance-based optimization among available groups
        best_group = None
        best_score = float('inf')
        
        for group in available_groups:
            # Calculate variance score
            variance_score = self._calculate_variance_after_addition(groups, group, participant)
            
            # Small size penalty to prefer smaller groups among available ones
            size_penalty = len(group.members) * 0.1
            
            composite_score = variance_score + size_penalty
            
            if composite_score < best_score:
                best_score = composite_score
                best_group = group
        
        # If no best group found, use the smallest available group
        if best_group is None:
            best_group = min(available_groups, key=lambda g: len(g.members))
        
        return best_group
    
    def _round_robin_assignment(self, participants: List[Participant], groups: List[Group]) -> None:
        """Assign participants using round-robin distribution.
        
        Args:
            participants: Participants to assign (in the order they should be assigned)
            groups: Groups to assign to
        """
        # Assign in round-robin fashion using the provided order
        for i, participant in enumerate(participants):
            group_index = i % len(groups)
            groups[group_index].add_member(participant)
    
    def _local_optimization(self, groups: List[Group]) -> None:
        """Perform local optimization by trying beneficial swaps.
        
        Args:
            groups: Groups to optimize
        """
        improved = True
        max_iterations = 50  # Prevent infinite loops
        iteration = 0
        
        while improved and iteration < max_iterations:
            improved = False
            iteration += 1
            
            # Try swapping participants between groups
            for i in range(len(groups)):
                for j in range(i + 1, len(groups)):
                    if self._try_beneficial_swap(groups[i], groups[j]):
                        improved = True
                        break  # Start over after any improvement
                if improved:
                    break
    
    def _try_beneficial_swap(self, group1: Group, group2: Group) -> bool:
        """Try to find a beneficial swap between two groups.
        
        Args:
            group1: First group
            group2: Second group
            
        Returns:
            True if a beneficial swap was made
        """
        if not group1.members or not group2.members:
            return False
        
        current_variance = self._calculate_two_group_variance(group1, group2)
        best_swap = None
        best_variance = current_variance
        
        # Try swapping each participant from group1 with each from group2
        for p1 in group1.members:
            for p2 in group2.members:
                # Don't swap advantaged participants (they're strategically placed)
                if p1.has_advantage or p2.has_advantage:
                    continue
                
                # Calculate what variance would be after swap
                # Temporarily calculate new averages
                group1_total = sum(m.score for m in group1.members) - p1.score + p2.score
                group2_total = sum(m.score for m in group2.members) - p2.score + p1.score
                
                group1_avg = group1_total / len(group1.members)
                group2_avg = group2_total / len(group2.members)
                
                new_variance = statistics.variance([group1_avg, group2_avg])
                
                if new_variance < best_variance - 0.001:  # Small threshold for numerical stability
                    best_variance = new_variance
                    best_swap = (p1, p2)
        
        # Perform the best swap if found
        if best_swap:
            p1, p2 = best_swap
            group1.members.remove(p1)
            group2.members.remove(p2)
            group1.add_member(p2)
            group2.add_member(p1)
            return True
        
        return False
    
    def _calculate_variance_after_addition(self, groups: List[Group], target_group: Group, participant: Participant) -> float:
        """Calculate what the overall variance would be after adding a participant to a group.
        
        Args:
            groups: All groups
            target_group: Group to add participant to
            participant: Participant to add
            
        Returns:
            Projected variance after addition
        """
        # Calculate current average of target group
        current_total = sum(m.score for m in target_group.members)
        current_count = len(target_group.members)
        
        # Calculate new average after addition
        new_total = current_total + participant.score
        new_count = current_count + 1
        new_average = new_total / new_count
        
        # Calculate variance with this new average, but only consider groups with members
        averages = []
        for group in groups:
            if group is target_group:
                averages.append(new_average)
            elif group.members:  # Only include groups that have members
                averages.append(group.average_score)
        
        # If we only have one group with members, prefer balanced distribution
        if len(averages) <= 1:
            # Return a penalty based on group size imbalance
            group_sizes = [len(g.members) + (1 if g is target_group else 0) for g in groups]
            size_variance = statistics.variance(group_sizes) if len(group_sizes) > 1 else 0.0
            return size_variance * 100  # Penalty for uneven distribution
        
        return statistics.variance(averages)
    
    def _calculate_two_group_variance(self, group1: Group, group2: Group) -> float:
        """Calculate variance between two groups.
        
        Args:
            group1: First group
            group2: Second group
            
        Returns:
            Variance between the two group averages
        """
        if not group1.members or not group2.members:
            return float('inf')  # Invalid state
        
        avg1 = group1.average_score
        avg2 = group2.average_score
        
        return statistics.variance([avg1, avg2])
    
    def calculate_score_variance(self, groups: List[Group]) -> float:
        """Calculate the variance of group average scores.
        
        Args:
            groups: List of groups
            
        Returns:
            Variance of group averages
        """
        if not groups:
            return 0.0
        
        # Only consider groups that have members
        averages = [group.average_score for group in groups if group.members]
        
        if len(averages) <= 1:
            return 0.0
        
        return statistics.variance(averages)