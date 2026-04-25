# ⚙️ Solver Mechanics

Group Balancer uses Google's **OR-Tools CP-SAT solver** to find the most balanced distribution.

## 🎯 The Objective Function
The solver minimizes the total **weighted absolute deviation** of the group averages from the global average for every score dimension.

$$TotalCost = \sum_{d \in Dimensions} W_d \times \sum_{g \in Groups} |Average_{d,g} - GlobalAverage_d|$$

## ⚖️ Conflict Resolution
When a participant has both `Sep` and `Grp` tags that conflict (mathematical infeasibility):
1. **Prioritize Groupers:** Separation constraints become "soft" and are penalized in the objective function if violated.
2. **Prioritize Separators:** Grouping constraints become "soft" and allow participants to be split if it ensures a perfect distribution of types.

## ⏱️ Performance
The solver is limited by a user-defined timeout. It will return the "Best Feasible" solution found within that time if an "Optimal" solution is not proven.
