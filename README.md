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

### 1. Focused Smart Swap
To optimize performance, the algorithm avoids checking every possible group combination. Instead, it employs a **Focused Heuristic**:
* It sorts groups by average score.
* It strictly targets the **Top 3 Highest Scoring Groups** against the **Bottom 3 Lowest Scoring Groups**.
* This prioritizes fixing the "Outliers" (the widest gaps) first, avoiding wasted cycles on middle groups that are already near the average.

### 2. Topology Mutation (Transfers)
To avoid getting stuck in a local optimum (where scores are balanced but group sizes are suboptimal), the algorithm uses **Simulated Annealing** to perform "Transfers":
* It randomly moves a member from a larger group to a smaller group.
* It probabilistically accepts "worse" states temporarily to explore different group size configurations (Topology).
* This allows the system to discover if a specific 4-person/5-person split yields a better standard deviation than the current setup.

### 3. Parallel "Race" Architecture
The script splits your CPU cores into two teams:
* **Team A (Constrained):** Optimizes for score balance while strictly enforcing that "Star" (*) players never share a group (unless mathematically impossible).
* **Team B (Unconstrained):** Optimizes purely for score balance, ignoring labels.

## Prerequisites

* Python 3.8+
* Dependencies:
    ```bash
    pip install -r requirements.txt
    ```

## Usage

1.  Run the main script:
    ```bash
    python group_balancer.py
    ```
2.  **Drag and drop** your input file into the console window.
3.  Enter the desired number of groups.
4.  The script runs for the duration configured in `modules/config.py` (Default: 15 mins).
    * **To stop early:** Press `Ctrl+C`. The script will safely finalize and save the current best solution.

## Configuration

You can adjust settings in `modules/config.py`:
* `SEARCH_DURATION`: Time in seconds to run the optimizer (Default: 900s).

## Project Structure

* `group_balancer.py`: Main entry point.
* `modules/`:
    * `algorithms.py`: Core logic (Smart Swap & Annealing).
    * `parallel_engine.py`: Multiprocessing orchestration.
    * `data_loader.py`: File I/O.
    * `output_manager.py`: Excel reporting.
    * `config.py`: Global constants.
