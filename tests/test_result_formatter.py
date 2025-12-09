"""Tests for the result formatter functionality."""

import pytest
from group_balancer.models import Participant, Group, GroupResult
from group_balancer.result_formatter import ResultFormatter


class TestResultFormatter:
    """Unit tests for the ResultFormatter class."""
    
    def test_format_empty_result(self):
        """Test formatting of empty results."""
        formatter = ResultFormatter()
        result = GroupResult(groups=[], score_variance=0.0, advantage_distribution=[])
        
        output = formatter.format_console_results(result)
        assert "No groups to display." in output
    
    def test_format_single_group_with_members(self):
        """Test formatting of a single group with members."""
        formatter = ResultFormatter()
        
        # Create participants
        p1 = Participant("Alice", "Alice", 85.0, False)
        p2 = Participant("Bob", "Bob*", 90.0, True)
        
        # Create group
        group = Group(id=0, members=[p1, p2])
        
        # Create result
        result = GroupResult(
            groups=[group],
            score_variance=6.25,
            advantage_distribution=[1]
        )
        
        output = formatter.format_console_results(result)
        
        # Check that all required elements are present
        assert "Group 1:" in output
        assert "Alice" in output
        assert "Bob*" in output
        assert "(Advantage)" in output
        assert "85.0" in output
        assert "90.0" in output
        assert "87.50" in output  # Average score
        assert "6.2500" in output  # Score variance
        assert "OVERALL STATISTICS" in output
    
    def test_format_multiple_groups(self):
        """Test formatting of multiple groups."""
        formatter = ResultFormatter()
        
        # Create participants
        p1 = Participant("Alice", "Alice", 85.0, False)
        p2 = Participant("Bob", "Bob*", 90.0, True)
        p3 = Participant("Charlie", "Charlie", 75.0, False)
        p4 = Participant("Diana", "Diana*", 95.0, True)
        
        # Create groups
        group1 = Group(id=0, members=[p1, p2])
        group2 = Group(id=1, members=[p3, p4])
        
        # Create result
        result = GroupResult(
            groups=[group1, group2],
            score_variance=25.0,
            advantage_distribution=[1, 1]
        )
        
        output = formatter.format_console_results(result)
        
        # Check group headers
        assert "Group 1:" in output
        assert "Group 2:" in output
        
        # Check all participants are listed
        assert "Alice" in output
        assert "Bob*" in output
        assert "Charlie" in output
        assert "Diana*" in output
        
        # Check advantage indicators
        assert output.count("(Advantage)") == 2
        
        # Check statistics
        assert "Total Participants: 4" in output
        assert "Total Groups: 2" in output
        assert "Advantaged Participants: 2" in output
    
    def test_format_summary_line(self):
        """Test the summary line formatting."""
        formatter = ResultFormatter()
        
        # Create a simple result
        p1 = Participant("Alice", "Alice", 85.0, False)
        group = Group(id=0, members=[p1])
        result = GroupResult(
            groups=[group],
            score_variance=0.0,
            advantage_distribution=[0]
        )
        
        summary = formatter.format_summary_line(result)
        assert "Created 1 groups with 1 participants" in summary
        assert "Score variance: 0.0000" in summary
    
    def test_format_group_brief(self):
        """Test the brief group formatting."""
        formatter = ResultFormatter()
        
        # Create a group with members
        p1 = Participant("Alice", "Alice", 85.0, False)
        p2 = Participant("Bob", "Bob*", 90.0, True)
        group = Group(id=0, members=[p1, p2])
        
        brief = formatter.format_group_brief(group)
        assert "Group 1:" in brief
        assert "2 members" in brief
        assert "1 advantaged" in brief
        assert "87.50" in brief  # Average score
    
    def test_format_empty_group(self):
        """Test formatting of empty groups."""
        formatter = ResultFormatter()
        
        group = Group(id=0, members=[])
        brief = formatter.format_group_brief(group)
        assert "Group 1: Empty" in brief