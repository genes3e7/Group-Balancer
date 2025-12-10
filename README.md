# Advanced Group Balancer

A high-performance, modular Python tool for mathematically perfect group distribution. It utilizes **Parallel Simulated Annealing** with live synchronization to minimize the standard deviation of group averages.

## Key Features

* **Dual Parallel Search:** Runs "Constrained" (Star separation) and "Unconstrained" (Pure math) optimization scenarios simultaneously across all CPU cores.
* **Live Dashboard:** Features a real-time progress bar displaying the best Standard Deviation found so far for both scenarios.
* **Graceful Shutdown:** Supports `Ctrl+C` to stop the search early and immediately save the best results found up to that moment.
* **Champion Logic:** Automatically cross-validates results. If the Constrained solution is mathematically superior to the Unconstrained one, it promotes it to the final output.
* **Paranoid Integrity:** Performs full recalculations of group scores on every modification to prevent floating-point drift, ensuring 100% accuracy.
* **Drag & Drop Input:** Easily run the script by dragging your Excel file into the terminal.

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
