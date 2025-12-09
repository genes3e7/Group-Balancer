# Group Balancer

**Group Balancer** is a robust Python CLI tool designed to organize participants into balanced groups based on numeric scores. It utilizes a multi-phase optimization algorithm to minimize score variance between groups while ensuring the fair distribution of "advantaged" or VIP participants.

It reads input from Excel, processes the data using statistical balancing logic, and outputs detailed results to both the console and a formatted Excel report.

## Features

  * **Score Optimization:** Minimizes the variance of average scores across groups to ensure fair competition or collaboration.
  * **Advantage Distribution:** Automatically detects "advantaged" participants (marked via syntax) and distributes them evenly across groups before balancing the remaining scores.
  * **Multi-Strategy Balancing:** Uses a combination of greedy assignment, round-robin, and iterative swapping algorithms to find the best possible mathematical balance.
  * **Excel Integration:**
      * Reads participant data from standard `.xlsx` files using `openpyxl`.
      * Generates comprehensive Excel reports with individual group sheets and a statistical summary.
  * **Detailed Metrics:** Profound insight into group composition, including standard deviation, size variance, and score distribution.

## Installation

### Prerequisites

  * Python 3.8+

### Setup

1.  Clone this repository:

    ```bash
    git clone https://github.com/yourusername/group-balancer.git
    cd group-balancer
    ```

2.  Install the dependencies using the requirements file:

    ```bash
    pip install -r requirements.txt
    ```

    [cite_start]*This installs core dependencies like `openpyxl` alongside testing utilities `pytest` and `hypothesis`[cite: 1].*

## Input Data Format

The application expects an Excel file (`.xlsx`) with data starting in **Row 2** (Row 1 is assumed to be headers).

  * **Column A (Name):** The name of the participant.
      * **Syntax:** Append an asterisk (`*`) to the end of a name to mark them as "Advantaged" (e.g., `John Doe*`). These participants are distributed first to ensure an even spread.
  * **Column B (Score):** A numeric value representing the participant's skill or rating.

**Example Input:**

| Name | Score |
| :--- | :--- |
| Alice Smith\* | 95.5 |
| Bob Jones | 88.0 |
| Charlie Brown | 72.5 |
| David Lee\* | 91.0 |

## Usage

Run the application from the command line by executing the directory as a package.

### Syntax

```bash
python -m group_balancer <number_of_groups> <path_to_excel_file> [options]
```

### Arguments

  * `number_of_groups`: (Integer) The number of groups you wish to create.
  * `path_to_excel_file`: The path to your input `.xlsx` file.

### Options

  * `-o`, `--output`: Specify a custom path for the output Excel file. If omitted, a timestamped file (e.g., `groups_20251209_120000.xlsx`) is created in the current directory.

### Examples

**Create 4 groups from a file named `participants.xlsx`:**

```bash
python -m group_balancer 4 participants.xlsx
```

**Create 6 groups and save to `results.xlsx`:**

```bash
python -m group_balancer 6 data.xlsx --output results.xlsx
```

## Development & Testing

This project utilizes a robust testing suite to ensure the balancing algorithms produce mathematically valid results.

  * [cite_start]**Pytest:** The primary test runner[cite: 1].
  * [cite_start]**Hypothesis:** Used for property-based testing[cite: 1]. This generates randomized inputs to verify that the algorithm handles edge cases (e.g., extreme scores, zero participants, impossible constraints) without crashing.

To run the tests, execute:

```bash
pytest
```

## How It Works

The `BalanceEngine` performs the organization in three phases:

1.  **Advantage Distribution:** Participants marked with `*` are isolated, sorted by score, and distributed across groups via a score-aware round-robin method. This prevents "stacking" strong players in a single group.
2.  **Score Balancing:** Remaining participants are assigned using multiple strategies (Greedy vs. Round-Robin). The engine compares these strategies and selects the one that produces the lowest initial score variance.
3.  **Local Optimization:** The engine performs an iterative "swap" pass. It looks for pairs of participants between different groups that, if swapped, would lower the overall global variance. This continues until the convergence threshold is met or maximum iterations are reached.

## Project Structure

  * `__main__.py`: Entry point for the CLI.
  * `cli.py`: Handles argument parsing and validation.
  * `group_optimizer.py`: Coordinator that runs the balance engine and validates results.
  * `balance_engine.py`: Core algorithm logic for sorting and swapping participants.
  * `models.py`: Data classes for `Participant`, `Group`, and `GroupResult`.
  * `excel_reader.py`: Logic for parsing input files and validating data types.
  * `excel_writer.py`: Generates the formatted Excel output.
  * `result_formatter.py`: Formats text for console output.
