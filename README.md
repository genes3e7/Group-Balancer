# Advanced Group Balancer

A high-performance Python tool for **mathematically optimal** group distribution. It utilizes **Google OR-Tools (CP-SAT)** to solve the partitioning problem deterministically, finding the absolute best possible balance of scores.

## Key Features

* **Exact Solver:** Uses the CP-SAT constraint solver to find the global minimum standard deviation. Unlike random search algorithms, this finds the mathematically best solution.
* **Deterministic Results:** Running the tool twice on the same data yields the exact same result every time.
* **Complex Constraints:**
    * **Size Balancing:** Automatically calculates the optimal mix of group sizes (e.g., separating 26 people into groups of 5 and 4) so the size difference is never more than 1.
    * **Star Separation:** Strictly enforces that "Star" (*) players are distributed as evenly as possible across teams.
* **High Precision:** Uses integer scaling (up to 5 decimal places) to prevent floating-point math errors from affecting the balance.
* **Drag & Drop Input:** Easily run the script by dragging your Excel file into the terminal.

## How It Works (Layman's Terms)

This tool moves away from "guessing" algorithms (like shuffling players until things look good) and uses **Constraint Programming**.

### 1. The "Sudoku" Approach (CP-SAT)
Imagine a Sudoku puzzle. You don't solve it by throwing random numbers at the grid; you solve it by logic ("If a 5 is here, a 5 cannot be there").
The **CP-SAT Solver** works similarly. We tell it the rules (everyone must be in a group, groups must be similar sizes, stars must be separated), and it uses advanced algebra to "prune" impossible combinations until only the best valid solution remains.

### 2. Balancing Unequal Groups
The hardest part of this problem is that groups often have different sizes (e.g., some have 4 members, some have 5).
* If a group has **4 members**, it needs a lower Total Score to have a "good average."
* If a group has **5 members**, it needs a higher Total Score to have that *same* average.

The solver calculates the **Exact Target Score** for every group size. It then assigns a "Penalty Cost" to every group based on how far its actual score deviates from that target.
* **The Goal:** Minimize the Total Penalty Cost.
* **The Result:** The mathematical variance is squashed to the absolute minimum possible.

### 3. Precision Scaling
Computers are bad at decimals (e.g., `0.1 + 0.2` often equals `0.30000000000000004`). To ensure perfect accuracy, this tool takes your scores (e.g., `95.5`) and multiplies them by **100,000** (becoming `9,550,000`). It solves the problem using whole integers, guaranteeing that no precision is lost during the complex balancing process.

## Prerequisites

* Python 3.13 - 3.13
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
4.  The solution is calculated typically in seconds.

## Project Structure

* `group_balancer.py`: Main entry point.
* `modules/`:
    * `solver.py`: The Google OR-Tools model definition and solver logic.
    * `data_loader.py`: File I/O and input sanitization.
    * `output_manager.py`: Excel reporting.
    * `config.py`: Global constants.

## License

**Copyright (c) 2025 Tan Eugene**

This project is licensed for **Personal Use Only**. Commercial usage is strictly prohibited. See the `LICENSE` file for details.
