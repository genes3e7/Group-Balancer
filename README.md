# Advanced Group Balancer

[![Streamlit App](https://static.streamlit.io/badges/streamlit_badge_black_white.svg)](https://group-balancer.streamlit.app)

A high-performance Web Application for **mathematically optimal** group distribution. This tool utilizes **Google OR-Tools (CP-SAT)** to solve the partitioning problem deterministically, finding the absolute best possible balance of scores directly in your browser.

## 🔗 Live Demo

**Access the tool here:** [group-balancer.streamlit.app](https://group-balancer.streamlit.app)

## Key Features

* **Exact Solver:** Uses the CP-SAT constraint solver to find the global minimum standard deviation. Unlike random search algorithms, this finds the mathematically best solution.
* **Web Interface:** Simple drag-and-drop Excel/CSV upload. No command line required.
* **Complex Constraints:**
    * **Size Balancing:** Automatically calculates the optimal mix of group sizes so the size difference is never more than 1.
    * **Star Separation:** Strictly enforces that "Star" (*) players are distributed as evenly as possible across teams.
* **High Precision:** Uses integer scaling (up to 5 decimal places) to prevent floating-point math errors.
* **Instant Export:** Download your results directly as a formatted Excel file.

## How It Works

This tool moves away from "guessing" algorithms (like shuffling players until things look good) and uses **Constraint Programming**.

### 1. The "Sudoku" Approach
Imagine a Sudoku puzzle. You don't solve it by throwing random numbers at the grid; you solve it by logic. The **CP-SAT Solver** works similarly. We tell it the rules (everyone must be in a group, groups must be balanced, stars must be separated), and it uses advanced algebra to "prune" impossible combinations until only the best valid solution remains.

### 2. Balancing Unequal Groups
If you have 26 people and want 6 groups, you inevitably have some groups of 4 and some of 5.
* Groups with **fewer members** need a lower Total Score to have a "good average."
* Groups with **more members** need a higher Total Score.

The solver calculates the **Exact Target Score** for every group size and minimizes the deviation from that target.

## Input Data Format

Prepare an Excel (`.xlsx`) or CSV file with the following headers:

| Name       | Score |
| :---       | :---  |
| Player A   | 88    |
| Player B* | 95    |
| Player C   | 40    |

* **Name:** Participant name. Add a `*` suffix (e.g., `Name*`) to mark "Star" participants who should be separated across groups.
* **Score:** The numerical value used for balancing.

## Local Installation & Usage

If you prefer to run the application locally instead of using the web version:

1.  **Clone the repository:**
    ```bash
    git clone https://github.com/genes3e7/group-balancer.git
    cd group-balancer
    ```

2.  **Install dependencies:**
    ```bash
    pip install -r requirements.txt
    ```

3.  **Run the App:**
    ```bash
    streamlit run app.py
    ```
    The application will open automatically in your web browser.

## License

**Copyright (c) 2025 Tan Eugene**

This project is licensed for **Personal Use Only**. Commercial usage is strictly prohibited without prior written consent. See the `LICENSE` file for details.
