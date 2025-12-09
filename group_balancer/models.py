"""Core data models for the Group Balancer application."""

from dataclasses import dataclass
from typing import List
import statistics


@dataclass
class Participant:
    """Represents a participant with name, score, and advantage status."""
    
    name: str
    original_name: str  # Preserves asterisk for display
    score: float
    has_advantage: bool
    
    @classmethod
    def from_raw_data(cls, name: str, score: float) -> 'Participant':
        """Create a Participant from raw data, parsing advantage status from name.
        
        Args:
            name: The participant's name, potentially with asterisk suffix
            score: The participant's numeric score
            
        Returns:
            Participant instance with parsed advantage status
        """
        has_advantage = name.endswith('*')
        clean_name = name.rstrip('*') if has_advantage else name
        
        return cls(
            name=clean_name,
            original_name=name,
            score=float(score),
            has_advantage=has_advantage
        )


@dataclass
class Group:
    """Represents a group of participants with calculated statistics."""
    
    id: int
    members: List[Participant]
    
    def __post_init__(self):
        """Initialize members list if not provided."""
        if self.members is None:
            self.members = []
    
    @property
    def average_score(self) -> float:
        """Calculate the average score of all members in the group."""
        if not self.members:
            return 0.0
        return sum(member.score for member in self.members) / len(self.members)
    
    @property
    def advantage_count(self) -> int:
        """Count the number of advantaged participants in the group."""
        return sum(1 for member in self.members if member.has_advantage)
    
    def add_member(self, participant: Participant) -> None:
        """Add a participant to this group."""
        self.members.append(participant)


@dataclass
class GroupResult:
    """Stores the results of group optimization."""
    
    groups: List[Group]
    score_variance: float
    advantage_distribution: List[int]
    
    def is_valid(self) -> bool:
        """Check if the group result is valid."""
        if not self.groups:
            return False
        
        # Check that all groups have members
        if any(len(group.members) == 0 for group in self.groups):
            return False
        
        # Check that advantage distribution matches actual counts
        actual_distribution = [group.advantage_count for group in self.groups]
        return actual_distribution == self.advantage_distribution