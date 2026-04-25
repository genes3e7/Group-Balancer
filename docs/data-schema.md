# 📊 Data Schema

The tool identifies constraints based on specific column headers in your uploaded file.

## 🔤 Participant Name
* **Column:** `Name`
* **Purpose:** Unique identifier for each participant.

## 🔢 Score Dimensions
* **Prefix:** `Score` (e.g., `Score1`, `Score_PT`, `Score_Technical`)
* **Purpose:** Numeric values used for balancing the average across groups.
* **Behavior:** Missing values are coerced to `0.0`.

## 🏷️ Categorical Constraints
* **Grouper (`Grp`):** Participants sharing the same symbol are **forced** into the same group.
* **Separator (`Sep`):** Participants sharing the same symbol are **distributed** as evenly as possible across groups.

---
*Note: You can use any characters for symbols (e.g., 'A', '1', '★').*
