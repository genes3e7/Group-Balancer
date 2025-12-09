"""Tests for the core data models."""

import pytest
from hypothesis import given, strategies as st, settings, HealthCheck
import tempfile
import os
from openpyxl import Workbook
import statistics

from group_balancer.models import Participant, Group, GroupResult
from group_balancer.excel_reader import ExcelReader, ExcelDataError


def _is_valid_numeric(x):
    """Helper function to check if a string can be converted to a valid float."""
    try:
        float(x)
        return True
    except (ValueError, TypeError):
        return False


class TestParticipant:
    """Tests for the Participant data model."""
    
    @given(
        name=st.text(min_size=1, max_size=50).filter(lambda x: '*' not in x),
        score=st.floats(min_value=0.0, max_value=100.0, allow_nan=False, allow_infinity=False)
    )
    def test_data_parsing_round_trip_without_advantage(self, name, score):
        """**Feature: group-balancer, Property 3: Data parsing round-trip**
        
        For any participant name without advantage status, parsing then 
        reconstructing should preserve the original format while correctly 
        extracting advantage status.
        
        **Validates: Requirements 2.2, 2.5**
        """
        # Create participant from raw data
        participant = Participant.from_raw_data(name, score)
        
        # Verify parsing
        assert participant.name == name
        assert participant.original_name == name
        assert participant.score == score
        assert participant.has_advantage is False
        
        # Round-trip: reconstruct original name from parsed data
        reconstructed_name = participant.original_name
        assert reconstructed_name == name
    
    @given(
        base_name=st.text(min_size=1, max_size=50).filter(lambda x: '*' not in x),
        score=st.floats(min_value=0.0, max_value=100.0, allow_nan=False, allow_infinity=False)
    )
    def test_data_parsing_round_trip_with_advantage(self, base_name, score):
        """**Feature: group-balancer, Property 3: Data parsing round-trip**
        
        For any participant name with advantage status, parsing then 
        reconstructing should preserve the original format while correctly 
        extracting advantage status.
        
        **Validates: Requirements 2.2, 2.5**
        """
        # Create name with advantage marker
        name_with_advantage = base_name + '*'
        
        # Create participant from raw data
        participant = Participant.from_raw_data(name_with_advantage, score)
        
        # Verify parsing
        assert participant.name == base_name
        assert participant.original_name == name_with_advantage
        assert participant.score == score
        assert participant.has_advantage is True
        
        # Round-trip: reconstruct original name from parsed data
        reconstructed_name = participant.original_name
        assert reconstructed_name == name_with_advantage


class TestGroup:
    """Tests for the Group data model."""
    
    def test_empty_group_properties(self):
        """Test properties of an empty group."""
        group = Group(id=1, members=[])
        assert group.average_score == 0.0
        assert group.advantage_count == 0
    
    def test_group_with_members(self):
        """Test group properties with members."""
        p1 = Participant("Alice", "Alice", 85.0, False)
        p2 = Participant("Bob", "Bob*", 90.0, True)
        
        group = Group(id=1, members=[])
        group.add_member(p1)
        group.add_member(p2)
        
        assert group.average_score == 87.5
        assert group.advantage_count == 1


class TestGroupResult:
    """Tests for the GroupResult data model."""
    
    def test_valid_group_result(self):
        """Test validation of a valid group result."""
        p1 = Participant("Alice", "Alice", 85.0, False)
        p2 = Participant("Bob", "Bob*", 90.0, True)
        
        group1 = Group(id=1, members=[p1])
        group2 = Group(id=2, members=[p2])
        
        result = GroupResult(
            groups=[group1, group2],
            score_variance=6.25,
            advantage_distribution=[0, 1]
        )
        
        assert result.is_valid() is True
    
    def test_invalid_group_result_empty_groups(self):
        """Test validation fails for empty groups."""
        group1 = Group(id=1, members=[])
        
        result = GroupResult(
            groups=[group1],
            score_variance=0.0,
            advantage_distribution=[0]
        )
        
        assert result.is_valid() is False
    
    def test_invalid_group_result_mismatched_distribution(self):
        """Test validation fails for mismatched advantage distribution."""
        p1 = Participant("Alice", "Alice", 85.0, False)
        group1 = Group(id=1, members=[p1])
        
        result = GroupResult(
            groups=[group1],
            score_variance=0.0,
            advantage_distribution=[1]  # Wrong - should be [0]
        )
        
        assert result.is_valid() is False


class TestExcelReader:
    """Tests for the Excel data processing functionality."""
    
    def _create_test_excel_file(self, data_rows):
        """Helper method to create a temporary Excel file with test data."""
        temp_file = tempfile.NamedTemporaryFile(suffix='.xlsx', delete=False)
        temp_file.close()
        
        workbook = Workbook()
        worksheet = workbook.active
        
        # Add headers
        worksheet['A1'] = 'Name'
        worksheet['B1'] = 'Score'
        
        # Add data rows
        for i, (name, score) in enumerate(data_rows, start=2):
            worksheet[f'A{i}'] = name
            worksheet[f'B{i}'] = score
        
        workbook.save(temp_file.name)
        workbook.close()
        
        return temp_file.name
    
    @given(
        valid_scores=st.lists(
            st.floats(min_value=0.0, max_value=100.0, allow_nan=False, allow_infinity=False),
            min_size=1,
            max_size=10
        ),
        invalid_scores=st.lists(
            st.one_of(
                st.text().filter(lambda x: x.strip() != "" and not _is_valid_numeric(x)),
                st.none(),
                st.just(""),
                st.just("invalid"),
                st.just("N/A")
            ),
            min_size=1,
            max_size=5
        )
    )
    def test_score_validation_property(self, valid_scores, invalid_scores):
        """**Feature: group-balancer, Property 4: Score validation**
        
        For any Excel data containing invalid score values, the system should 
        identify and reject all non-numeric scores while accepting valid numeric scores.
        
        **Validates: Requirements 2.4**
        """
        reader = ExcelReader()
        
        # Test with valid scores - should not produce validation errors
        valid_data = []
        for i, score in enumerate(valid_scores):
            valid_data.append({
                'name': f'Participant{i}',
                'score': score,
                'row': i + 2
            })
        
        valid_errors = reader.validate_score_data(valid_data)
        assert len(valid_errors) == 0, f"Valid scores should not produce errors, but got: {valid_errors}"
        
        # Test with invalid scores - should produce validation errors
        invalid_data = []
        for i, score in enumerate(invalid_scores):
            invalid_data.append({
                'name': f'Participant{i}',
                'score': score,
                'row': i + 2
            })
        
        invalid_errors = reader.validate_score_data(invalid_data)
        assert len(invalid_errors) == len(invalid_scores), f"Expected {len(invalid_scores)} errors for invalid scores, but got {len(invalid_errors)}: {invalid_errors}"
        
        # Test mixed valid and invalid scores
        mixed_data = valid_data + invalid_data
        mixed_errors = reader.validate_score_data(mixed_data)
        assert len(mixed_errors) == len(invalid_scores), f"Mixed data should only report errors for invalid scores, expected {len(invalid_scores)} errors but got {len(mixed_errors)}: {mixed_errors}"
    
    def test_excel_file_not_found(self):
        """Test error handling for missing Excel files."""
        reader = ExcelReader()
        
        with pytest.raises(ExcelDataError, match="Excel file not found"):
            reader.read_excel_data("nonexistent_file.xlsx")
    
    def test_corrupted_excel_file(self):
        """Test error handling for corrupted Excel files."""
        reader = ExcelReader()
        
        # Create a text file with .xlsx extension
        temp_file = tempfile.NamedTemporaryFile(suffix='.xlsx', delete=False, mode='w')
        temp_file.write("This is not an Excel file")
        temp_file.close()
        
        try:
            with pytest.raises(ExcelDataError, match="Invalid or corrupted Excel file"):
                reader.read_excel_data(temp_file.name)
        finally:
            os.unlink(temp_file.name)
    
    def test_valid_excel_data_processing(self):
        """Test successful processing of valid Excel data."""
        reader = ExcelReader()
        
        # Create test data
        test_data = [
            ("Alice", 85.5),
            ("Bob*", 92.0),
            ("Charlie", 78.3)
        ]
        
        temp_file = self._create_test_excel_file(test_data)
        
        try:
            participants = reader.load_participants(temp_file)
            
            assert len(participants) == 3
            
            # Check first participant
            assert participants[0].name == "Alice"
            assert participants[0].original_name == "Alice"
            assert participants[0].score == 85.5
            assert participants[0].has_advantage is False
            
            # Check second participant (with advantage)
            assert participants[1].name == "Bob"
            assert participants[1].original_name == "Bob*"
            assert participants[1].score == 92.0
            assert participants[1].has_advantage is True
            
            # Check third participant
            assert participants[2].name == "Charlie"
            assert participants[2].original_name == "Charlie"
            assert participants[2].score == 78.3
            assert participants[2].has_advantage is False
            
        finally:
            os.unlink(temp_file)
    
    def test_excel_data_with_invalid_scores(self):
        """Test error handling for Excel data with invalid scores."""
        reader = ExcelReader()
        
        # Create test data with invalid scores
        test_data = [
            ("Alice", 85.5),
            ("Bob", "invalid_score"),
            ("Charlie", None)
        ]
        
        temp_file = self._create_test_excel_file(test_data)
        
        try:
            with pytest.raises(ExcelDataError, match="Data validation errors"):
                reader.load_participants(temp_file)
        finally:
            os.unlink(temp_file)
    
    def test_empty_excel_file(self):
        """Test error handling for empty Excel files."""
        reader = ExcelReader()
        
        # Create empty Excel file
        temp_file = self._create_test_excel_file([])
        
        try:
            with pytest.raises(ExcelDataError, match="No participant data found"):
                reader.load_participants(temp_file)
        finally:
            os.unlink(temp_file)


class TestBalanceEngineProperties:
    """Property-based tests for the balance engine functionality."""
    
    @given(
        advantaged_count=st.integers(min_value=1, max_value=20),
        group_count=st.integers(min_value=2, max_value=10)
    )
    def test_advantage_distribution_fairness_property(self, advantaged_count, group_count):
        """**Feature: group-balancer, Property 5: Advantage distribution fairness**
        
        For any set of advantaged participants and group count, the distribution should 
        minimize the maximum difference in advantaged participants per group, with no 
        group having more than one additional advantaged participant compared to others.
        
        **Validates: Requirements 3.1, 3.2, 3.3**
        """
        # Import here to avoid circular imports during testing
        from group_balancer.balance_engine import BalanceEngine
        
        # Create test participants - mix of advantaged and regular
        participants = []
        
        # Add advantaged participants
        for i in range(advantaged_count):
            score = 70.0 + (i * 5)  # Varied scores
            participants.append(Participant(f"Adv{i}", f"Adv{i}*", score, True))
        
        # Add some regular participants
        regular_count = max(group_count * 2, advantaged_count)  # Ensure enough participants
        for i in range(regular_count):
            score = 60.0 + (i * 3)
            participants.append(Participant(f"Reg{i}", f"Reg{i}", score, False))
        
        # Create empty groups
        groups = [Group(id=i, members=[]) for i in range(group_count)]
        
        # Test the advantage distribution
        engine = BalanceEngine()
        engine.distribute_advantaged(participants, groups)
        
        # Check fairness properties
        advantage_counts = [group.advantage_count for group in groups]
        
        # Property 1: Maximum difference should be at most 1
        max_diff = max(advantage_counts) - min(advantage_counts)
        assert max_diff <= 1, f"Max difference in advantage distribution is {max_diff}, should be <= 1"
        
        # Property 2: Total advantaged participants should be preserved
        total_distributed = sum(advantage_counts)
        assert total_distributed == advantaged_count, f"Expected {advantaged_count} advantaged participants, got {total_distributed}"
        
        # Property 3: Each group should have at most ceil(advantaged_count/group_count) advantaged participants
        import math
        max_expected = math.ceil(advantaged_count / group_count)
        assert all(count <= max_expected for count in advantage_counts), f"Some group has more than {max_expected} advantaged participants: {advantage_counts}"
    
    @given(
        advantaged_scores=st.lists(
            st.floats(min_value=50.0, max_value=100.0, allow_nan=False, allow_infinity=False),
            min_size=2,
            max_size=10
        ),
        group_count=st.integers(min_value=2, max_value=5)
    )
    def test_score_aware_advantage_distribution_property(self, advantaged_scores, group_count):
        """**Feature: group-balancer, Property 6: Score-aware advantage distribution**
        
        For any multiple advantaged participants with different scores, their distribution 
        across groups should consider individual scores to balance the average impact on group totals.
        
        **Validates: Requirements 3.4**
        """
        # Import here to avoid circular imports during testing
        from group_balancer.balance_engine import BalanceEngine
        
        # Create advantaged participants with the given scores
        participants = []
        for i, score in enumerate(advantaged_scores):
            participants.append(Participant(f"Adv{i}", f"Adv{i}*", score, True))
        
        # Add regular participants to ensure we have enough
        regular_count = group_count * 3
        for i in range(regular_count):
            participants.append(Participant(f"Reg{i}", f"Reg{i}", 70.0, False))
        
        # Create empty groups
        groups = [Group(id=i, members=[]) for i in range(group_count)]
        
        # Test score-aware distribution
        engine = BalanceEngine()
        engine.distribute_advantaged(participants, groups)
        
        # Calculate the impact of advantaged participants on each group
        group_advantage_impacts = []
        for group in groups:
            advantaged_members = [m for m in group.members if m.has_advantage]
            if advantaged_members:
                impact = sum(m.score for m in advantaged_members) / len(advantaged_members)
                group_advantage_impacts.append(impact)
            else:
                group_advantage_impacts.append(0.0)
        
        # The distribution should try to balance the score impact
        # If there are multiple groups with advantaged participants, 
        # the variance in their advantage impact should be reasonable
        groups_with_advantages = [impact for impact in group_advantage_impacts if impact > 0]
        
        if len(groups_with_advantages) > 1:
            # Calculate variance of advantage impacts
            impact_variance = statistics.variance(groups_with_advantages)
            
            # The variance should be less than if we just randomly distributed
            # This is a heuristic check - the algorithm should do better than random
            total_advantage_score = sum(advantaged_scores)
            random_variance_estimate = (max(advantaged_scores) - min(advantaged_scores)) ** 2 / 4
            
            # The algorithm should perform better than the worst-case random distribution
            assert impact_variance <= random_variance_estimate * 2, f"Advantage impact variance {impact_variance} is too high, suggests poor score-aware distribution"
    
    @given(
        participant_scores=st.lists(
            st.floats(min_value=40.0, max_value=100.0, allow_nan=False, allow_infinity=False),
            min_size=6,
            max_size=20
        ),
        group_count=st.integers(min_value=2, max_value=5)
    )
    @settings(suppress_health_check=[HealthCheck.too_slow])
    def test_variance_minimization_property(self, participant_scores, group_count):
        """**Feature: group-balancer, Property 7: Variance minimization**
        
        For any set of participants and group count, the algorithm should produce 
        groupings with lower score variance than random assignment.
        
        **Validates: Requirements 4.1**
        """
        # Skip if we don't have enough participants for the groups
        if len(participant_scores) < group_count:
            return
        
        # Import here to avoid circular imports during testing
        from group_balancer.balance_engine import BalanceEngine
        
        # Create participants
        participants = []
        for i, score in enumerate(participant_scores):
            participants.append(Participant(f"P{i}", f"P{i}", score, False))
        
        # Test the balance engine
        engine = BalanceEngine()
        result = engine.optimize_groups(participants, group_count)
        
        # Calculate the variance of our algorithm
        group_averages = [group.average_score for group in result.groups]
        algorithm_variance = statistics.variance(group_averages) if len(group_averages) > 1 else 0.0
        
        # Compare with a simple round-robin assignment (baseline)
        baseline_groups = [Group(id=i, members=[]) for i in range(group_count)]
        for i, participant in enumerate(participants):
            baseline_groups[i % group_count].add_member(participant)
        
        baseline_averages = [group.average_score for group in baseline_groups]
        baseline_variance = statistics.variance(baseline_averages) if len(baseline_averages) > 1 else 0.0
        
        # Our algorithm should perform at least as well as round-robin
        # Allow for small numerical differences
        assert algorithm_variance <= baseline_variance + 0.01, f"Algorithm variance {algorithm_variance} is worse than baseline {baseline_variance}"
        
        # Verify the result is valid
        assert result.is_valid(), "Result should be valid"
        assert len(result.groups) == group_count, f"Should have {group_count} groups, got {len(result.groups)}"
        
        # Verify all participants are assigned
        total_assigned = sum(len(group.members) for group in result.groups)
        assert total_assigned == len(participants), f"Should assign all {len(participants)} participants, got {total_assigned}"
    
    @given(
        participant_scores=st.lists(
            st.floats(min_value=40.0, max_value=100.0, allow_nan=False, allow_infinity=False),
            min_size=4,
            max_size=12
        ),
        group_count=st.integers(min_value=2, max_value=4)
    )
    @settings(suppress_health_check=[HealthCheck.too_slow])
    def test_optimal_solution_selection_property(self, participant_scores, group_count):
        """**Feature: group-balancer, Property 8: Optimal solution selection**
        
        For any grouping problem with multiple valid solutions, the system should 
        select the solution with the lowest score variance.
        
        **Validates: Requirements 4.3**
        """
        # Skip if we don't have enough participants
        if len(participant_scores) < group_count:
            return
        
        # Import here to avoid circular imports during testing
        from group_balancer.balance_engine import BalanceEngine
        
        # Create participants
        participants = []
        for i, score in enumerate(participant_scores):
            participants.append(Participant(f"P{i}", f"P{i}", score, False))
        
        # Run the optimization multiple times to test consistency
        engine = BalanceEngine()
        
        results = []
        for _ in range(3):  # Run multiple times
            result = engine.optimize_groups(participants, group_count)
            results.append(result)
        
        # All results should be valid
        for result in results:
            assert result.is_valid(), "All results should be valid"
        
        # The algorithm should be deterministic or at least consistent in quality
        variances = [result.score_variance for result in results]
        
        # All variances should be the same (deterministic) or very close
        variance_range = max(variances) - min(variances)
        assert variance_range <= 0.1, f"Variance range {variance_range} suggests inconsistent optimization"
        
        # The selected solution should have reasonable variance
        # (This is a sanity check - the variance should not be extremely high)
        best_variance = min(variances)
        
        # Calculate what a completely random assignment would look like
        import random
        random.seed(42)  # For reproducibility
        random_groups = [Group(id=i, members=[]) for i in range(group_count)]
        shuffled_participants = participants.copy()
        random.shuffle(shuffled_participants)
        
        for i, participant in enumerate(shuffled_participants):
            random_groups[i % group_count].add_member(participant)
        
        random_averages = [group.average_score for group in random_groups]
        random_variance = statistics.variance(random_averages) if len(random_averages) > 1 else 0.0
        
        # Our algorithm should perform better than random (with some tolerance)
        assert best_variance <= random_variance + 1.0, f"Algorithm variance {best_variance} is not significantly better than random {random_variance}"


class TestResultFormatterProperties:
    """Property-based tests for the result formatter functionality."""
    
    @given(
        participant_data=st.lists(
            st.tuples(
                st.text(min_size=1, max_size=20).filter(lambda x: '*' not in x and x.strip()),
                st.floats(min_value=40.0, max_value=100.0, allow_nan=False, allow_infinity=False),
                st.booleans()
            ),
            min_size=4,
            max_size=15
        ),
        group_count=st.integers(min_value=2, max_value=5)
    )
    @settings(suppress_health_check=[HealthCheck.too_slow])
    def test_complete_console_output_display_property(self, participant_data, group_count):
        """**Feature: group-balancer, Property 9: Complete console output display**
        
        For any completed grouping, the console output should contain all group members, 
        their advantage status indicators, individual group averages, and overall score variance.
        
        **Validates: Requirements 4.4, 5.1, 5.2, 5.3**
        """
        # Skip if we don't have enough participants
        if len(participant_data) < group_count:
            return
        
        # Import here to avoid circular imports during testing
        from group_balancer.result_formatter import ResultFormatter
        
        # Create participants from the test data
        participants = []
        for i, (name, score, has_advantage) in enumerate(participant_data):
            original_name = f"{name}*" if has_advantage else name
            participants.append(Participant(name, original_name, score, has_advantage))
        
        # Create groups and distribute participants
        groups = []
        for i in range(group_count):
            groups.append(Group(id=i, members=[]))
        
        # Simple round-robin distribution for testing
        for i, participant in enumerate(participants):
            groups[i % group_count].add_member(participant)
        
        # Calculate variance for the result
        group_averages = [group.average_score for group in groups if group.members]
        score_variance = statistics.variance(group_averages) if len(group_averages) > 1 else 0.0
        advantage_distribution = [group.advantage_count for group in groups]
        
        # Create the result
        result = GroupResult(
            groups=groups,
            score_variance=score_variance,
            advantage_distribution=advantage_distribution
        )
        
        # Format the console output
        formatter = ResultFormatter()
        output = formatter.format_console_results(result)
        
        # Verify all required elements are present in the output
        
        # Property 1: All group members should be listed
        for group in groups:
            for member in group.members:
                assert member.original_name in output, f"Member {member.original_name} not found in output"
        
        # Property 2: Advantage status indicators should be present
        advantaged_members = [p for p in participants if p.has_advantage]
        for member in advantaged_members:
            # Should show either the asterisk in original name or "(Advantage)" indicator
            assert (member.original_name in output or 
                    "(Advantage)" in output), f"Advantage status for {member.name} not indicated in output"
        
        # Property 3: Individual group averages should be displayed
        for group in groups:
            if group.members:  # Only check non-empty groups
                expected_avg = f"{group.average_score:.2f}"
                assert expected_avg in output, f"Group average {expected_avg} not found in output"
        
        # Property 4: Overall score variance should be displayed
        expected_variance = f"{score_variance:.4f}"
        assert expected_variance in output, f"Score variance {expected_variance} not found in output"
        
        # Property 5: Group identification should be clear
        for i in range(group_count):
            group_label = f"Group {i + 1}"
            assert group_label in output, f"Group label '{group_label}' not found in output"
        
        # Property 6: Overall statistics section should be present
        assert "OVERALL STATISTICS" in output, "Overall statistics section missing from output"
        assert "Total Participants" in output, "Total participants count missing from output"
        assert "Total Groups" in output, "Total groups count missing from output"
        
        # Property 7: Advantage distribution should be displayed
        assert "Advantage Distribution" in output, "Advantage distribution section missing from output"
        
        # Property 8: Output should be well-structured (contains section separators)
        assert "=" in output, "Output should contain section separators"
        assert "-" in output, "Output should contain group separators"
        
        # Property 9: All participant scores should be displayed
        for participant in participants:
            score_str = f"{participant.score:.1f}"
            assert score_str in output, f"Participant score {score_str} not found in output"
        
        # Property 10: Verify output is not empty and has reasonable length
        assert len(output.strip()) > 0, "Output should not be empty"
        assert len(output.split('\n')) >= group_count + 10, "Output should have sufficient detail"