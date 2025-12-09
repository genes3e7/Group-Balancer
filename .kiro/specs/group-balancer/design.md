# Group Balancer Design Document

## Overview

The Group Balancer is a Python command-line application that solves a multi-objective optimization problem: distributing participants into balanced groups while considering both score averages and advantage status distribution. The system uses a greedy algorithm with backtracking to find optimal group assignments that minimize score variance while ensuring fair distribution of advantaged participants.

## Architecture

The system follows a modular architecture with clear separation of concerns:

```
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│   CLI Handler   │───▶│  Data Processor │───▶│ Group Optimizer │
└─────────────────┘    └─────────────────┘    └─────────────────┘
         │                       │                       │
         ▼                       ▼                       ▼
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│ Argument Parser │    │  Excel Reader   │    │ Balance Engine  │
└─────────────────┘    └─────────────────┘    └─────────────────┘
                                │                       │
                                ▼                       ▼
                       ┌─────────────────┐    ┌─────────────────┐
                       │ Data Validator  │    │ Result Formatter│
                       └─────────────────┘    └─────────────────┘
                                                        │
                                                        ▼
                                               ┌─────────────────┐
                                               │  Excel Writer   │
                                               └─────────────────┘
```

## Components and Interfaces

### CLI Handler
- **Purpose**: Entry point for the application, handles command-line arguments
- **Interface**: `main(args: List[str]) -> None`
- **Dependencies**: Argument Parser, Data Processor, Group Optimizer

### Data Processor
- **Purpose**: Manages data loading, validation, and participant parsing
- **Interface**: 
  - `load_participants(file_path: str) -> List[Participant]`
  - `validate_data(participants: List[Participant], group_count: int) -> bool`
- **Dependencies**: Excel Reader, Data Validator

### Group Optimizer
- **Purpose**: Core algorithm for creating balanced groups
- **Interface**:
  - `optimize_groups(participants: List[Participant], group_count: int) -> GroupResult`
  - `calculate_balance_score(groups: List[Group]) -> float`
- **Dependencies**: Balance Engine

### Excel Reader
- **Purpose**: Handles XLSX file parsing and data extraction
- **Interface**: `read_excel_data(file_path: str) -> List[Dict[str, Any]]`

### Balance Engine
- **Purpose**: Implements the core balancing algorithm
- **Interface**:
  - `distribute_advantaged(participants: List[Participant], groups: List[Group]) -> None`
  - `balance_scores(participants: List[Participant], groups: List[Group]) -> None`

### Result Formatter
- **Purpose**: Handles console output formatting and display
- **Interface**: `format_console_results(result: GroupResult) -> str`

### Excel Writer
- **Purpose**: Creates Excel output files with detailed group information and statistics
- **Interface**: 
  - `write_excel_output(result: GroupResult, output_path: str) -> None`
  - `create_summary_statistics(participants: List[Participant]) -> Dict[str, float]`
- **Dependencies**: openpyxl library

## Data Models

### Participant
```python
@dataclass
class Participant:
    name: str
    original_name: str  # Preserves asterisk for display
    score: float
    has_advantage: bool
    
    @classmethod
    def from_raw_data(cls, name: str, score: float) -> 'Participant'
```

### Group
```python
@dataclass
class Group:
    id: int
    members: List[Participant]
    
    @property
    def average_score(self) -> float
    
    @property
    def advantage_count(self) -> int
    
    def add_member(self, participant: Participant) -> None
```

### GroupResult
```python
@dataclass
class GroupResult:
    groups: List[Group]
    score_variance: float
    advantage_distribution: List[int]
    
    def is_valid(self) -> bool
```

## Correctness Properties

*A property is a characteristic or behavior that should hold true across all valid executions of a system-essentially, a formal statement about what the system should do. Properties serve as the bridge between human-readable specifications and machine-verifiable correctness guarantees.*

Based on the prework analysis, the following properties ensure system correctness:

**Property 1: Group count consistency**
*For any* valid group count argument, the system should create exactly that number of groups
**Validates: Requirements 1.1**

**Property 2: Invalid input rejection**
*For any* invalid group count input (non-positive integers, non-numeric values), the system should reject the input and display an appropriate error message
**Validates: Requirements 1.2**

**Property 3: Data parsing round-trip**
*For any* participant name with or without advantage status, parsing then reconstructing the name should preserve the original format while correctly extracting advantage status
**Validates: Requirements 2.2, 2.5**

**Property 4: Score validation**
*For any* Excel data containing invalid score values, the system should identify and reject all non-numeric scores while accepting valid numeric scores
**Validates: Requirements 2.4**

**Property 5: Advantage distribution fairness**
*For any* set of advantaged participants and group count, the distribution should minimize the maximum difference in advantaged participants per group, with no group having more than one additional advantaged participant compared to others
**Validates: Requirements 3.1, 3.2, 3.3**

**Property 6: Score-aware advantage distribution**
*For any* multiple advantaged participants with different scores, their distribution across groups should consider individual scores to balance the average impact on group totals
**Validates: Requirements 3.4**

**Property 7: Variance minimization**
*For any* set of participants and group count, the algorithm should produce groupings with lower score variance than random assignment
**Validates: Requirements 4.1**

**Property 8: Optimal solution selection**
*For any* grouping problem with multiple valid solutions, the system should select the solution with the lowest score variance
**Validates: Requirements 4.3**

**Property 9: Complete console output display**
*For any* completed grouping, the console output should contain all group members, their advantage status indicators, individual group averages, and overall score variance
**Validates: Requirements 4.4, 5.1, 5.2, 5.3**

**Property 10: Excel output completeness**
*For any* completed grouping, the Excel output should contain all groups with member names, individual scores, and a summary sheet with highest score, lowest score, average, median, and standard deviation
**Validates: Requirements 5.5, 5.6, 5.7**

## Error Handling

The system implements comprehensive error handling across all components:

### Input Validation Errors
- Invalid command-line arguments (non-positive integers, missing arguments)
- File access errors (missing files, permission issues)
- Data format errors (corrupted Excel files, invalid data types)

### Processing Errors
- Insufficient participants for requested group count
- Invalid score data that cannot be converted to numeric values
- Memory constraints for large datasets

### Algorithm Errors
- Convergence failures in optimization algorithm
- Mathematical errors in variance calculations

Each error type includes specific error messages and graceful degradation strategies.

## Testing Strategy

The Group Balancer employs a dual testing approach combining unit tests and property-based tests to ensure comprehensive correctness validation.

### Unit Testing Approach
Unit tests verify specific examples, edge cases, and integration points:
- Command-line argument parsing with various input formats
- Excel file reading with sample data files
- Algorithm behavior with known input/output pairs
- Error handling with specific invalid inputs
- Output formatting with predetermined data sets

### Property-Based Testing Approach
Property-based tests verify universal properties across all valid inputs using **Hypothesis** for Python:
- Each property-based test runs a minimum of 100 iterations with randomly generated inputs
- Tests validate correctness properties that should hold regardless of specific input values
- Generators create realistic test data including participant lists, scores, and group counts
- Each property-based test includes a comment explicitly referencing the design document property using format: **Feature: group-balancer, Property {number}: {property_text}**

### Test Implementation Requirements
- Each correctness property must be implemented by a single property-based test
- Property-based tests are tagged with comments linking to design document properties
- Unit tests complement property tests by covering specific scenarios and edge cases
- Both test types are essential for comprehensive validation

## Algorithm Design

### Core Balancing Algorithm

The system uses a two-phase optimization approach:

1. **Advantage Distribution Phase**: Distributes advantaged participants across groups using a score-aware greedy algorithm
2. **Score Balancing Phase**: Optimizes remaining participant assignments to minimize group average variance

### Optimization Strategy

The algorithm employs a greedy approach with local optimization:
- Initial assignment based on sorted scores
- Iterative improvement through participant swapping
- Termination when no beneficial swaps remain

### Complexity Analysis
- Time Complexity: O(n² × g) where n = participants, g = groups
- Space Complexity: O(n + g) for storing participants and groups
- Suitable for typical use cases (hundreds of participants, dozens of groups)

## Implementation Considerations

### Dependencies
- **openpyxl**: Excel file reading and parsing
- **hypothesis**: Property-based testing framework
- **pytest**: Unit testing framework
- **dataclasses**: Data model definitions (Python 3.7+)

### Performance Optimizations
- Lazy loading of Excel data
- Efficient variance calculation using incremental updates
- Early termination conditions for optimization loops

### Excel Output Format
The Excel output file contains multiple sheets:

**Group Sheets**: One sheet per group containing:
- Column A: Participant names (with advantage indicators)
- Column B: Individual scores
- Column C: Group average (repeated for all rows)

**Summary Sheet**: Overall statistics including:
- Highest Score: Maximum score across all participants
- lowest Score: Minimum score across all participants  
- Average: Mean score of all participants
- Median: Middle value when scores are sorted
- Standard Deviation: Measure of score distribution spread

**File Naming**: Output files use format `groups_YYYYMMDD_HHMMSS.xlsx`

### Extensibility Points
- Pluggable scoring algorithms
- Configurable optimization parameters
- Support for additional data sources beyond Excel
- Customizable Excel output templates