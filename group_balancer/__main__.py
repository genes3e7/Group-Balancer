"""Main entry point for the Group Balancer application."""

import sys
from .cli import CLIHandler, CLIError
from .excel_reader import ExcelReader, ExcelDataError
from .group_optimizer import GroupOptimizer
from .result_formatter import ResultFormatter
from .excel_writer import ExcelWriter


def main():
    """Main entry point for the command-line application."""
    cli_handler = CLIHandler()
    
    try:
        # Parse command-line arguments
        args = cli_handler.parse_and_validate_args()
        
        # Initialize components
        excel_reader = ExcelReader()
        group_optimizer = GroupOptimizer()
        result_formatter = ResultFormatter()
        excel_writer = ExcelWriter()
        
        print(f"Loading participants from {args.excel_file}...")
        
        # Load participant data
        try:
            participants = excel_reader.load_participants(args.excel_file)
            print(f"Loaded {len(participants)} participants")
        except ExcelDataError as e:
            raise CLIError(f"Failed to load Excel data: {e}")
        
        # Validate group count against participant count
        cli_handler.validate_group_count_against_participants(args.group_count, participants)
        
        print(f"Creating {args.group_count} balanced groups...")
        
        # Optimize group assignments
        try:
            result = group_optimizer.optimize_groups(participants, args.group_count)
            print("Group optimization completed successfully")
        except Exception as e:
            raise CLIError(f"Group optimization failed: {e}")
        
        # Display console results
        print("\n" + "="*60)
        console_output = result_formatter.format_console_results(result)
        print(console_output)
        
        # Generate Excel output
        try:
            output_path = excel_writer.write_excel_output(result, args.output)
            print(f"\nExcel output saved to: {output_path}")
        except Exception as e:
            print(f"Warning: Failed to create Excel output: {e}", file=sys.stderr)
            print("Console output is still available above.", file=sys.stderr)
        
        return 0
        
    except CLIError as e:
        cli_handler.handle_cli_error(e)
        return 1
    except SystemExit as e:
        # Let help and version requests exit normally
        return e.code
    except KeyboardInterrupt:
        print("\nOperation cancelled by user.", file=sys.stderr)
        return 1
    except Exception as e:
        print(f"Unexpected error: {e}", file=sys.stderr)
        return 1


if __name__ == '__main__':
    sys.exit(main())