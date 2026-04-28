"""Isolated unit tests for the solver's internal components."""

import time
from unittest.mock import MagicMock, patch

from src.core import solver
from src.core.models import ConflictPriority, Participant


def test_tag_processor_extraction():
    """Test raw character extraction."""
    assert solver.TagProcessor.get_tags("ABC") == {"A", "B", "C"}
    assert solver.TagProcessor.get_tags("A, B C") == {"A", "B", "C"}
    assert solver.TagProcessor.get_tags("") == set()
    assert solver.TagProcessor.get_tags(None) == set()
    assert solver.TagProcessor.get_tags(123) == set()


def test_solution_printer_logging():
    """Test SolutionPrinter logging intervals."""
    with patch("src.logger.info") as mock_logger:
        printer = solver.SolutionPrinter(start_time=time.time())
        printer.ObjectiveValue = MagicMock(return_value=100.0)

        # First call should log (last_log_time is 0)
        printer.on_solution_callback()
        assert mock_logger.call_count == 1

        # Second immediate call should not log (interval < 1s)
        printer.on_solution_callback()
        assert mock_logger.call_count == 1

        # Call after 1.1s should log
        with patch("time.time", return_value=time.time() + 2.0):
            printer.on_solution_callback()
            assert mock_logger.call_count == 2


def test_tag_processor_conflict_groupers():
    """Test grouper priority conflict resolution."""
    p = [
        Participant(name="A", scores={}, groupers="X", separators="X"),
        Participant(name="B", scores={}, groupers="X", separators="X"),
    ]
    g, s = solver.TagProcessor.process_participants(p, ConflictPriority.GROUPERS)

    # X should be in g, removed from s
    assert g["X"] == {0, 1}
    assert s.get("X", set()) == set()


def test_tag_processor_conflict_separators():
    """Test separator priority conflict resolution."""
    p = [
        Participant(name="A", scores={}, groupers="X", separators="X"),
        Participant(name="B", scores={}, groupers="X", separators="X"),
    ]
    g, s = solver.TagProcessor.process_participants(p, ConflictPriority.SEPARATORS)

    # X should be in s, removed from g
    assert s["X"] == {0, 1}
    assert g.get("X", set()) == set()
