"""Tests for the Group Optimizer component."""

import pytest
from hypothesis import given, strategies as st
from group_balancer.models import Participant, Group, GroupResult
from group_balancer.group_optimizer import GroupOptimizer


class TestGroupOptimizer:
    """Test cases for the Group Optimizer."""
    
    def test_basic_optimization(self):
        """Test basic optimization functionality."""
        optimizer = GroupOptimizer()
        
        participants = [
            Participant.from_raw_data("Alice", 85.0),
            Participant.from_raw_data("Bob", 75.0),
            Participant.from_raw_data("Charlie", 90.0),
            Participant.from_raw_data("Diana", 80.0),
        ]
        
        result = optimizer.optimize_groups(participants, 2)
        
        assert len(result.groups) == 2
        assert all(len(group.members) > 0 for group in result.groups)
        assert result.is_valid()
        
        # Check that all participants are assigned
        total_assigned = sum(len(group.members) for group in result.groups)
        assert total_assigned == len(participants)
    
    def test_optimization_with_advantages(self):
        """Test optimization with advantaged participants."""
        optimizer = GroupOptimizer()
        
        participants = [
            Participant.from_raw_data("Alice*", 85.0),
            Participant.from_raw_data("Bob", 75.0),
            Participant.from_raw_data("Charlie*", 90.0),
            Participant.from_raw_data("Diana", 80.0),
            Participant.from_raw_data("Eve", 70.0),
            Participant.from_raw_data("Frank", 95.0),
        ]
        
        result = optimizer.optimize_groups(participants, 3)
        
        assert len(result.groups) == 3
        assert result.is_valid()
        
        # Check advantage distribution
        advantage_counts = [group.advantage_count for group in result.groups]
        assert sum(advantage_counts) == 2  # Two advantaged participants
        assert max(advantage_counts) - min(advantage_counts) <= 1  # Fair distribution
    
    def test_input_validation(self):
        """Test input validation."""
        optimizer = GroupOptimizer()
        
        # Test empty participants
        with pytest.raises(ValueError, match="Cannot optimize groups with no participants"):
            optimizer.optimize_groups([], 2)
        
        # Test invalid group count
        participants = [Participant.from_raw_data("Alice", 85.0)]
        with pytest.raises(ValueError, match="Group count must be positive"):
            optimizer.optimize_groups(participants, 0)
        
        # Test more groups than participants
        with pytest.raises(ValueError, match="Cannot create .* groups with only .* participants"):
            optimizer.optimize_groups(participants, 2)
    
    def test_result_validation(self):
        """Test that results are properly validated."""
        optimizer = GroupOptimizer()
        
        participants = [
            Participant.from_raw_data("Alice", 85.0),
            Participant.from_raw_data("Bob", 75.0),
            Participant.from_raw_data("Charlie", 90.0),
            Participant.from_raw_data("Diana", 80.0),
        ]
        
        result = optimizer.optimize_groups(participants, 2)
        
        # Test the validation method directly
        assert optimizer._validate_result(result, participants, 2)
        
        # Test advantage distribution validation
        assert optimizer._validate_advantage_distribution(result)
    
    def test_quality_metrics(self):
        """Test quality score calculation and metrics."""
        optimizer = GroupOptimizer()
        
        participants = [
            Participant.from_raw_data("Alice", 85.0),
            Participant.from_raw_data("Bob", 75.0),
            Participant.from_raw_data("Charlie", 90.0),
            Participant.from_raw_data("Diana", 80.0),
        ]
        
        result = optimizer.optimize_groups(participants, 2)
        
        # Test quality score calculation
        quality_score = optimizer._calculate_quality_score(result)
        assert isinstance(quality_score, float)
        assert quality_score >= 0
        
        # Test optimization metrics
        metrics = optimizer.get_optimization_metrics(result)
        assert isinstance(metrics, dict)
        assert 'score_variance' in metrics
        assert 'group_count' in metrics
        assert 'total_participants' in metrics
        assert 'quality_score' in metrics
        
        assert metrics['group_count'] == 2
        assert metrics['total_participants'] == 4
    
    def test_enhancement_process(self):
        """Test result enhancement process."""
        optimizer = GroupOptimizer()
        
        participants = [
            Participant.from_raw_data("Alice", 85.0),
            Participant.from_raw_data("Bob", 75.0),
            Participant.from_raw_data("Charlie", 90.0),
            Participant.from_raw_data("Diana", 80.0),
            Participant.from_raw_data("Eve", 70.0),
            Participant.from_raw_data("Frank", 95.0),
        ]
        
        # Create a basic result
        result = optimizer.balance_engine.optimize_groups(participants, 3)
        
        # Enhance it
        enhanced_result = optimizer._enhance_result_quality(result, participants)
        
        assert len(enhanced_result.groups) == len(result.groups)
        assert enhanced_result.is_valid()
        
        # Enhanced result should have same or better quality
        original_quality = optimizer._calculate_quality_score(result)
        enhanced_quality = optimizer._calculate_quality_score(enhanced_result)
        assert enhanced_quality <= original_quality + 0.1  # Allow small tolerance
    
    def test_single_group_edge_case(self):
        """Test edge case with single group."""
        optimizer = GroupOptimizer()
        
        participants = [
            Participant.from_raw_data("Alice", 85.0),
            Participant.from_raw_data("Bob", 75.0),
        ]
        
        result = optimizer.optimize_groups(participants, 1)
        
        assert len(result.groups) == 1
        assert len(result.groups[0].members) == 2
        assert result.score_variance == 0.0  # Single group has no variance
        assert result.is_valid()
    
    def test_many_groups_edge_case(self):
        """Test edge case with many groups (one participant per group)."""
        optimizer = GroupOptimizer()
        
        participants = [
            Participant.from_raw_data("Alice", 85.0),
            Participant.from_raw_data("Bob", 75.0),
            Participant.from_raw_data("Charlie", 90.0),
        ]
        
        result = optimizer.optimize_groups(participants, 3)
        
        assert len(result.groups) == 3
        assert all(len(group.members) == 1 for group in result.groups)
        assert result.is_valid()
        
        # Check that all participants are assigned
        assigned_names = {member.name for group in result.groups for member in group.members}
        original_names = {p.name for p in participants}
        assert assigned_names == original_names