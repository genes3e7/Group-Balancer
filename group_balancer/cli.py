"""Command-line interface for the Group Balancer application."""

import argparse
import sys
from typing import List, Optional
from pathlib import Path

from .models import Participant


class CLIError(Exception):
    """Exception raised for CLI-related errors."""
    pass


class ArgumentParser:
    """Handles command-line argument parsing and validation."""
    
    def __init__(self):
        self.parser = argparse.ArgumentParser(
            prog='group-balancer',
            description='Create balanced groups from participant data in Excel files.',
            formatter_class=argparse.RawDescriptionHelpFormatter,
            epilog="""
Examples:
  group-balancer 4 participants.xlsx    # Create 4 groups from participants.xlsx
  group-balancer 6 data.xlsx            # Create 6 groups from data.xlsx

The Excel file should have columns:
  - Column A: Participant names (use * suffix for advantage status)
  - Column B: Numeric scores
            """
        )
        
        self.parser.add_argument(
            'group_count',
            type=int,
            help='Number of groups to create (must be a positive integer)'
        )
        
        self.parser.add_argument(
            'excel_file',
            type=str,
            help='Path to Excel file containing participant data'
        )
        
        self.parser.add_argument(
            '--output', '-o',
            type=str,
            help='Output Excel file path (optional, defaults to timestamped filename)'
        )
    
    def parse_args(self, args: Optional[List[str]] = None) -> argparse.Namespace:
        """Parse command-line arguments with validation.
        
        Args:
            args: List of arguments to parse (defaults to sys.argv)
            
        Returns:
            Parsed arguments namespace
            
        Raises:
            CLIError: If arguments are invalid
            SystemExit: If help is requested (let it propagate)
        """
        try:
            parsed_args = self.parser.parse_args(args)
            
            # Validate group count
            if parsed_args.group_count <= 0:
                raise CLIError("Group count must be a positive integer")
            
            # Validate Excel file exists
            excel_path = Path(parsed_args.excel_file)
            if not excel_path.exists():
                raise CLIError(f"Excel file not found: {parsed_args.excel_file}")
            
            if not excel_path.suffix.lower() in ['.xlsx', '.xls']:
                raise CLIError(f"File must be an Excel file (.xlsx or .xls): {parsed_args.excel_file}")
            
            return parsed_args
            
        except argparse.ArgumentTypeError as e:
            raise CLIError(f"Invalid argument: {e}")
        except SystemExit as e:
            # If exit code is 0, it's likely help was requested, let it propagate
            if e.code == 0:
                raise
            # Otherwise, it's an error case
            raise CLIError("Invalid command-line arguments")
    
    def print_usage(self) -> None:
        """Print usage instructions."""
        self.parser.print_help()


class CLIHandler:
    """Main CLI handler that coordinates argument parsing and validation."""
    
    def __init__(self):
        self.arg_parser = ArgumentParser()
    
    def validate_group_count_against_participants(self, group_count: int, participants: List[Participant]) -> None:
        """Validate that group count is reasonable for the number of participants.
        
        Args:
            group_count: Requested number of groups
            participants: List of participants
            
        Raises:
            CLIError: If group count is invalid for the participant count
        """
        participant_count = len(participants)
        
        if group_count > participant_count:
            raise CLIError(
                f"Cannot create {group_count} groups with only {participant_count} participants. "
                f"Group count must not exceed participant count."
            )
        
        if participant_count < group_count * 2:
            print(f"Warning: Creating {group_count} groups with {participant_count} participants "
                  f"will result in very small groups (average {participant_count/group_count:.1f} per group).",
                  file=sys.stderr)
    
    def handle_cli_error(self, error: CLIError) -> None:
        """Handle CLI errors by printing error message and usage.
        
        Args:
            error: The CLI error that occurred
        """
        print(f"Error: {error}", file=sys.stderr)
        print("\nUsage:", file=sys.stderr)
        self.arg_parser.print_usage()
    
    def parse_and_validate_args(self, args: Optional[List[str]] = None) -> argparse.Namespace:
        """Parse and validate command-line arguments.
        
        Args:
            args: List of arguments to parse (defaults to sys.argv)
            
        Returns:
            Parsed and validated arguments
            
        Raises:
            CLIError: If arguments are invalid
        """
        return self.arg_parser.parse_args(args)