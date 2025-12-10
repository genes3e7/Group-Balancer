# Advanced Group Balancer

A high-performance, modular Python tool for mathematically perfect group distribution. It utilizes **Parallel Simulated Annealing** with live synchronization to minimize the standard deviation of group averages.

## Key Features

* **Dual Parallel Search:** Runs "Constrained" (Star separation) and "Unconstrained" (Pure math) optimization scenarios simultaneously across all CPU cores.
* **Live Dashboard:** Features a real-time progress bar displaying the best Standard Deviation found so far for both scenarios.
* **Graceful Shutdown:** Supports `Ctrl+C` to stop the search early and immediately save the best results found up to that moment.
* **Champion Logic:** Automatically cross-validates results. If the Constrained solution is mathematically superior to the Unconstrained one, it promotes it to the final output.
* **Paranoid Integrity:** Performs full recalculations of group scores on every modification to prevent floating-point drift, ensuring 100% accuracy.
* **Drag & Drop Input:** Easily run the script by dragging your Excel file into the terminal.

## Algorithms & Logic

This tool employs a sophisticated stochastic optimization engine to solve the **Multi-Way Number Partitioning Problem**, which is NP-Hard.

### 1. Simulated Annealing (The Core Solver)
Instead of a simple greedy approach, the script uses Simulated Annealing to avoid getting stuck in "local optima" (sub-optimal solutions that look good only in the short term).
* **Heat Phase:** At high "temperatures," the algorithm accepts "bad" moves (moves that temporarily worsen the balance). This allows the system to escape local valleys and explore the global solution space.
* **Cooling Phase:** As the "temperature" drops, the algorithm becomes stricter, only accepting improvements. This polishes the rough grouping into a perfect mathematical shape.
* **Cyclic Reheating:** If the solution stagnates, the system automatically "reheats," scrambling the groups slightly to restart the search from a new vantage point.

### 2. Topology Mutation (The Move Set)
The algorithm doesn't just swap players; it dynamically alters the group structure using two distinct move types:
* **Swap (80% probability):** Exchanges two members between different groups. This balances scores without changing group sizes.
* **Transfer (20% probability):** Moves a member from a larger group to a smaller group (or vice versa), respecting the size constraint (difference ≤ 1). This is crucial for finding the optimal "Topology" (e.g., deciding whether the highest scorer should be in a group of 4 or a group of 5).

### 3. Parallel "Race" Architecture
The script splits your CPU cores into two teams:
* **Team A (Constrained):** Optimizes for score balance while strictly enforcing that "Star" (*) players never share a group (unless mathematically impossible).
* **Team B (Unconstrained):** Optimizes purely for score balance, ignoring labels.

These teams run in parallel, sharing their best findings in real-time. If Team A finds a solution that is mathematically better than Team B's best effort, the system automatically promotes the Constrained solution to be the final Unconstrained output.

## Prerequisites

* Python 3.8+
* Dependencies:
    ```bash
    pip install -r requirements.txt
    ```

## Input Data Format

Create an Excel (`.xlsx`) or CSV file with the following columns:

| Name       | Score |
| :---       | :---  |
| Player A   | 88    |
| Player B* | 95    |
| Player C   | 40    |

* **Name:** Participant name. Add a `*` suffix (e.g., `Name*`) to mark "Star" participants who should be separated across groups.
* **Score:** The numerical value used for balancing.

## Usage

1.  Run the main script:
    ```bash
    python group_balancer.py
    ```
2.  **Drag and drop** your input file into the console window when prompted.
3.  Enter the desired number of groups.
4.  The script will run for the duration configured in `modules/config.py` (Default: 1 Hour).
    * **To stop early:** Press `Ctrl+C`. The script will safely finalize and save the current best solution.

## Configuration

You can adjust settings in `modules/config.py`:
* `SEARCH_DURATION`: Time in seconds to run the optimizer (Default: 3600s).

## Project Structure

* `group_balancer.py`: Main entry point.
* `modules/`:
    * `algorithms.py`: Core Simulated Annealing and Hill Climbing logic.
    * `parallel_engine.py`: Multiprocessing orchestration and shared memory management.
    * `data_loader.py`: File I/O and input sanitization.
    * `output_manager.py`: Excel reporting.
    * `config.py`: Global constants.
