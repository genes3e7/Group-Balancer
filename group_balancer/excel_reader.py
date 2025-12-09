"""Excel data processing component for the Group Balancer application."""

import os
from typing import List, Dict, Any
from openpyxl import load_workbook
from openpyxl.utils.exceptions import InvalidFileException

from .models import Participant


class ExcelDataError(Exception):
    """Custom exception for Excel data processing errors."""
    pass


class ExcelReader:
    """Handles reading and processing Excel files containing participant data."""
    
    def __init__(self, name_column: str = 'A', score_column: str = 'B', start_row: int = 2):
        """Initialize Excel reader with column configuration.
        
        Args:
            name_column: Column letter for participant names (default: 'A')
            score_column: Column letter for scores (default: 'B') 
            start_row: First row containing data (default: 2, assuming headers in row 1)
        """
        self.name_column = name_column
        self.score_column = score_column
        self.start_row = start_row
    
    def read_excel_data(self, file_path: str) -> List[Dict[str, Any]]:
        """Read raw data from Excel file.
        
        Args:
            file_path: Path to the Excel file
            
        Returns:
            List of dictionaries containing raw participant data
            
        Raises:
            ExcelDataError: If file cannot be read or is corrupted
        """
        if not os.path.exists(file_path):
            raise ExcelDataError(f"Excel file not found: {file_path}")
        
        try:
            workbook = load_workbook(filename=file_path, read_only=True)
            worksheet = workbook.active
            
            raw_data = []
            row = self.start_row
            
            while True:
                name_cell = worksheet[f"{self.name_column}{row}"]
                score_cell = worksheet[f"{self.score_column}{row}"]
                
                # Stop if we hit an empty name cell
                if name_cell.value is None or str(name_cell.value).strip() == "":
                    break
                
                raw_data.append({
                    'name': str(name_cell.value).strip(),
                    'score': score_cell.value,
                    'row': row
                })
                
                row += 1
            
            workbook.close()
            return raw_data
            
        except (InvalidFileException, Exception) as e:
            # Handle both openpyxl InvalidFileException and other file format errors
            if "zip file" in str(e).lower() or "invalid" in str(e).lower() or "corrupt" in str(e).lower():
                raise ExcelDataError(f"Invalid or corrupted Excel file: {file_path}. Error: {str(e)}")
            elif isinstance(e, PermissionError):
                raise ExcelDataError(f"Permission denied accessing file: {file_path}. Error: {str(e)}")
            else:
                raise ExcelDataError(f"Unexpected error reading Excel file: {file_path}. Error: {str(e)}")
    
    def validate_score_data(self, raw_data: List[Dict[str, Any]]) -> List[str]:
        """Validate score fields and return list of validation errors.
        
        Args:
            raw_data: List of raw participant data dictionaries
            
        Returns:
            List of validation error messages (empty if all valid)
        """
        errors = []
        
        for item in raw_data:
            score_value = item['score']
            row_num = item['row']
            name = item['name']
            
            if score_value is None:
                errors.append(f"Row {row_num}: Missing score for participant '{name}'")
                continue
            
            # Try to convert to float
            try:
                float_score = float(score_value)
                # Check for reasonable score range (optional validation)
                if float_score < 0:
                    errors.append(f"Row {row_num}: Negative score ({float_score}) for participant '{name}'")
            except (ValueError, TypeError):
                errors.append(f"Row {row_num}: Invalid score '{score_value}' for participant '{name}' - must be a number")
        
        return errors
    
    def validate_participant_names(self, raw_data: List[Dict[str, Any]]) -> List[str]:
        """Validate participant names and return list of validation errors.
        
        Args:
            raw_data: List of raw participant data dictionaries
            
        Returns:
            List of validation error messages (empty if all valid)
        """
        errors = []
        seen_names = set()
        
        for item in raw_data:
            name = item['name']
            row_num = item['row']
            
            if not name or len(name.strip()) == 0:
                errors.append(f"Row {row_num}: Empty participant name")
                continue
            
            # Check for duplicate names (considering advantage status)
            clean_name = name.rstrip('*')
            if clean_name.lower() in seen_names:
                errors.append(f"Row {row_num}: Duplicate participant name '{clean_name}'")
            else:
                seen_names.add(clean_name.lower())
        
        return errors
    
    def load_participants(self, file_path: str) -> List[Participant]:
        """Load and validate participants from Excel file.
        
        Args:
            file_path: Path to the Excel file
            
        Returns:
            List of validated Participant objects
            
        Raises:
            ExcelDataError: If file cannot be read, is corrupted, or contains invalid data
        """
        # Read raw data
        raw_data = self.read_excel_data(file_path)
        
        if not raw_data:
            raise ExcelDataError("No participant data found in Excel file")
        
        # Validate data
        score_errors = self.validate_score_data(raw_data)
        name_errors = self.validate_participant_names(raw_data)
        
        all_errors = score_errors + name_errors
        if all_errors:
            error_message = "Data validation errors:\n" + "\n".join(all_errors)
            raise ExcelDataError(error_message)
        
        # Create Participant objects
        participants = []
        for item in raw_data:
            try:
                participant = Participant.from_raw_data(item['name'], float(item['score']))
                participants.append(participant)
            except Exception as e:
                raise ExcelDataError(f"Error creating participant from row {item['row']}: {str(e)}")
        
        return participants