"""Result formatter for console output display.

This module provides functionality to format group optimization results
for console display, including group listings, member information,
advantage status indicators, and statistical summaries.
"""

from typing import List
import statistics
from .models import GroupResult, Group, Participant


class ResultFormatter:
    """Handles console output formatting and display for group optimization results."""
    
    def __init__(self):
        """Initialize the result formatter."""
        pass
    
    def format_console_results(self, result: GroupResult) -> str:
        """Format group optimization results for console display.
        
        Args:
            result: The GroupResult containing optimized group assignments
            
        Returns:
            Formatted string ready for console output
        """
        if not result or not result.groups:
            return "No groups to display."
        
        output_lines = []
        
        # Add header
        output_lines.append("=" * 60)
        output_lines.append("GROUP BALANCER RESULTS")
        output_lines.append("=" * 60)
        output_lines.append("")
        
        # Format each group
        for group in result.groups:
            group_section = self._format_group(group)
            output_lines.extend(group_section)
            output_lines.append("")  # Empty line between groups
        
        # Add overall statistics
        stats_section = self._format_overall_statistics(result)
        output_lines.extend(stats_section)
        
        return "\n".join(output_lines)
    
    def _format_group(self, group: Group) -> List[str]:
        """Format a single group for display.
        
        Args:
            group: The Group to format
            
        Returns:
            List of formatted lines for the group
        """
        lines = []
        
        # Group header
        lines.append(f"Group {group.id + 1}:")
        lines.append("-" * 20)
        
        if not group.members:
            lines.append("  (No members)")
            lines.append(f"  Average Score: 0.0")
            return lines
        
        # List members with advantage indicators
        for member in group.members:
            member_line = f"  {member.original_name}"
            if member.has_advantage:
                member_line += " (Advantage)"
            member_line += f" - Score: {member.score:.1f}"
            lines.append(member_line)
        
        # Group statistics
        lines.append(f"  Average Score: {group.average_score:.2f}")
        lines.append(f"  Members: {len(group.members)}")
        lines.append(f"  Advantaged Members: {group.advantage_count}")
        
        return lines
    
    def _format_overall_statistics(self, result: GroupResult) -> List[str]:
        """Format overall statistics for the optimization result.
        
        Args:
            result: The GroupResult to analyze
            
        Returns:
            List of formatted lines for overall statistics
        """
        lines = []
        
        lines.append("=" * 60)
        lines.append("OVERALL STATISTICS")
        lines.append("=" * 60)
        
        # Basic counts
        total_participants = sum(len(group.members) for group in result.groups)
        total_advantaged = sum(group.advantage_count for group in result.groups)
        
        lines.append(f"Total Participants: {total_participants}")
        lines.append(f"Total Groups: {len(result.groups)}")
        lines.append(f"Advantaged Participants: {total_advantaged}")
        lines.append("")
        
        # Group size statistics
        group_sizes = [len(group.members) for group in result.groups]
        if group_sizes:
            lines.append("Group Size Distribution:")
            lines.append(f"  Minimum: {min(group_sizes)}")
            lines.append(f"  Maximum: {max(group_sizes)}")
            lines.append(f"  Average: {statistics.mean(group_sizes):.1f}")
            lines.append("")
        
        # Score statistics
        group_averages = [group.average_score for group in result.groups if group.members]
        if group_averages:
            lines.append("Group Average Scores:")
            lines.append(f"  Highest: {max(group_averages):.2f}")
            lines.append(f"  Lowest: {min(group_averages):.2f}")
            lines.append(f"  Overall Average: {statistics.mean(group_averages):.2f}")
            lines.append(f"  Score Variance: {result.score_variance:.4f}")
            lines.append("")
        
        # Advantage distribution
        lines.append("Advantage Distribution:")
        for i, count in enumerate(result.advantage_distribution):
            lines.append(f"  Group {i + 1}: {count} advantaged participant(s)")
        
        # Distribution fairness indicator
        if result.advantage_distribution:
            min_adv = min(result.advantage_distribution)
            max_adv = max(result.advantage_distribution)
            fairness = "Fair" if (max_adv - min_adv) <= 1 else "Unbalanced"
            lines.append(f"  Distribution Fairness: {fairness}")
        
        return lines
    
    def format_summary_line(self, result: GroupResult) -> str:
        """Format a brief summary line for the results.
        
        Args:
            result: The GroupResult to summarize
            
        Returns:
            Single line summary string
        """
        if not result or not result.groups:
            return "No groups created."
        
        total_participants = sum(len(group.members) for group in result.groups)
        group_count = len(result.groups)
        
        return (f"Created {group_count} groups with {total_participants} participants. "
                f"Score variance: {result.score_variance:.4f}")
    
    def format_group_brief(self, group: Group) -> str:
        """Format a brief one-line summary of a group.
        
        Args:
            group: The Group to summarize
            
        Returns:
            Brief group summary string
        """
        if not group.members:
            return f"Group {group.id + 1}: Empty"
        
        member_count = len(group.members)
        advantage_count = group.advantage_count
        avg_score = group.average_score
        
        return (f"Group {group.id + 1}: {member_count} members, "
                f"{advantage_count} advantaged, avg: {avg_score:.2f}")