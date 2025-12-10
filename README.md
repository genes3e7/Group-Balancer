# Advanced Group Balancer

A high-performance Python script designed to distribute participants into balanced groups based on numerical scores. It utilizes **Parallel Simulated Annealing** to minimize the standard deviation of group averages, ensuring the mathematically optimal distribution.

## Features

* **Dual Mode Optimization:** Generates two sets of groups:
    1.  **With Constraints:** Separates "Star" (*) participants across groups as much as possible.
    2.  **No Constraints:** Finds the absolute mathematical best balance (Pure Score Optimization).
* **Champion vs. Challenger Logic:** Automatically compares the constrained result against the unconstrained result to ensure the final "No Constraint" output is mathematically superior.
* **Paranoid Integrity Mode:** Performs full score recalculations after every internal swap to prevent floating-point drift and ensure 100% accuracy.
* **Parallel Processing:** Utilizes all available CPU cores to check millions of combinations in seconds.
* **Topology Unlocked:** Capable of swapping members *and* transferring members between groups (changing group sizes) to find perfect balance.

## Prerequisites

* Python 3.8 or higher

## Installation

1.  Clone this repository or download the script.
2.  Install the required dependencies:

```bash
pip install -r requirements.txt
```
