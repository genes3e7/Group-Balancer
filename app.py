import streamlit as st
import pandas as pd
import numpy as np
import math
import io
import logging
from ortools.sat.python import cp_model

# ==========================================
# LOGGING SETUP
# ==========================================
logging.basicConfig(level=logging.ERROR)
logger = logging.getLogger(__name__)

# ==========================================
# CONFIGURATION & CONSTANTS
# ==========================================
COL_NAME = "Name"
COL_SCORE = "Score"
ADVANTAGE_CHAR = "*"
SCALE_FACTOR = 100000
SOLVER_TIMEOUT = 10  # Reduced for web interactivity
SHEET_WITH_CONSTRAINT = "With_Star_Constraint"
# Renamed to reflect that this sheet holds the winner of the champion logic
SHEET_BEST_RESULT = "Best_Balanced_Solution"


# ==========================================
# SOLVER MODULE
# ==========================================
def solve_with_ortools(participants: list[dict], num_groups: int, respect_stars: bool):
    """
    Solves the partitioning problem using Google OR-Tools.
    """
    # FIX: Validation for empty list or invalid group count
    if not participants or num_groups < 1:
        return [], False

    model = cp_model.CpModel()

    # 1. Data Preparation
    num_people = len(participants)
    scores = [int(round(float(p[COL_SCORE]) * SCALE_FACTOR)) for p in participants]
    total_score = sum(scores)

    stars = [
        i
        for i, p in enumerate(participants)
        if str(p[COL_NAME]).endswith(ADVANTAGE_CHAR)
    ]

    # 2. Group Size Pre-calculation
    base_size = num_people // num_groups
    remainder = num_people % num_groups
    group_sizes_map = {}
    for g in range(num_groups):
        group_sizes_map[g] = base_size + 1 if g < remainder else base_size

    # 3. Decision Variables
    x = {}
    for i in range(num_people):
        for g in range(num_groups):
            x[(i, g)] = model.NewBoolVar(f"assign_p{i}_g{g}")

    # 4. Constraints
    # A: Everyone in exactly one group
    for i in range(num_people):
        model.Add(sum(x[(i, g)] for g in range(num_groups)) == 1)

    # B: Group sizes
    for g in range(num_groups):
        model.Add(sum(x[(i, g)] for i in range(num_people)) == group_sizes_map[g])

    # C: Star Separation
    if respect_stars and stars:
        max_stars_per_group = math.ceil(len(stars) / num_groups)
        for g in range(num_groups):
            model.Add(sum(x[(i, g)] for i in stars) <= max_stars_per_group)

    # 5. Objective: Minimize deviation
    abs_diffs = []
    max_domain_val = total_score * num_people  # Prevent overflow

    for g in range(num_groups):
        g_sum = model.NewIntVar(0, total_score, f"sum_group_{g}")
        model.Add(g_sum == sum(x[(i, g)] * scores[i] for i in range(num_people)))

        target_val = total_score * group_sizes_map[g]
        actual_val = model.NewIntVar(0, max_domain_val, f"actual_val_{g}")
        model.Add(actual_val == g_sum * num_people)

        diff = model.NewIntVar(-max_domain_val, max_domain_val, f"diff_{g}")
        model.Add(diff == actual_val - target_val)

        abs_diff = model.NewIntVar(0, max_domain_val, f"abs_diff_{g}")
        model.AddAbsEquality(abs_diff, diff)
        abs_diffs.append(abs_diff)

    model.Minimize(sum(abs_diffs))

    # 6. Solve
    solver = cp_model.CpSolver()
    solver.parameters.max_time_in_seconds = SOLVER_TIMEOUT
    status = solver.Solve(model)

    # 7. Reconstruct Results
    if status in (cp_model.OPTIMAL, cp_model.FEASIBLE):
        result_groups = []
        for g in range(num_groups):
            result_groups.append(
                {"id": g + 1, "members": [], "current_sum": 0.0, "avg": 0.0}
            )

        for i in range(num_people):
            for g in range(num_groups):
                if solver.Value(x[(i, g)]) == 1:
                    result_groups[g]["members"].append(participants[i])

        for g in result_groups:
            g_sum = sum(float(m[COL_SCORE]) for m in g["members"])
            count = len(g["members"])
            g["current_sum"] = g_sum
            g["avg"] = g_sum / count if count > 0 else 0.0

        return result_groups, True
    else:
        return [], False


# ==========================================
# EXCEL GENERATION
# ==========================================
def generate_excel_bytes(final_results: dict):
    """
    Writes the specific side-by-side format to an in-memory Excel file.
    """
    output = io.BytesIO()
    with pd.ExcelWriter(output, engine="openpyxl") as writer:
        for sheet_name, groups in final_results.items():
            if not groups:
                continue

            # --- 1. Prepare Main Grid Data ---
            s_groups = sorted(groups, key=lambda x: x["id"])
            rows = []

            for i in range(0, len(s_groups), 2):
                g1 = s_groups[i]
                g2 = s_groups[i + 1] if (i + 1) < len(s_groups) else None

                # Header Row
                rows.append(
                    {
                        "A": f"GROUP {g1['id']}",
                        "B": f"AVG: {g1['avg']:.2f}",
                        "C": "",
                        "D": f"GROUP {g2['id']}" if g2 else "",
                        "E": f"AVG: {g2['avg']:.2f}" if g2 else "",
                    }
                )
                # Sub-header Row
                rows.append(
                    {
                        "A": "Name",
                        "B": "Score",
                        "C": "",
                        "D": "Name" if g2 else "",
                        "E": "Score" if g2 else "",
                    }
                )

                # Member Rows
                len1 = len(g1["members"])
                len2 = len(g2["members"]) if g2 else 0
                max_len = max(len1, len2)

                for k in range(max_len):
                    m1 = g1["members"][k] if k < len1 else None
                    m2 = g2["members"][k] if g2 and k < len2 else None

                    rows.append(
                        {
                            "A": m1[COL_NAME] if m1 else "",
                            "B": m1[COL_SCORE] if m1 else "",
                            "C": "",
                            "D": m2[COL_NAME] if m2 else "",
                            "E": m2[COL_SCORE] if m2 else "",
                        }
                    )
                rows.append({})  # Spacer

            pd.DataFrame(rows).to_excel(
                writer, sheet_name=sheet_name, index=False, header=False, startcol=0
            )

            # --- 2. Calculate Statistics ---
            avgs = [g["avg"] for g in groups]
            if avgs:
                stats = [
                    {"Stat": "Lowest", "Val": min(avgs)},
                    {"Stat": "Highest", "Val": max(avgs)},
                    {"Stat": "Global Avg", "Val": np.mean(avgs)},
                    {"Stat": "StdDev", "Val": np.std(avgs)},
                ]
                pd.DataFrame(stats).to_excel(
                    writer, sheet_name=sheet_name, index=False, startcol=6
                )

    return output.getvalue()


# ==========================================
# STREAMLIT UI
# ==========================================
st.set_page_config(page_title="Group Balancer", page_icon="⚖️")
st.title("⚖️ Advanced Group Balancer")
st.markdown("""
Distribute participants into mathematically optimal groups using Google OR-Tools.
**Star (*)** participants are distributed evenly.
""")

uploaded_file = st.file_uploader("Upload Excel or CSV", type=["xlsx", "xls", "csv"])

if uploaded_file:
    try:
        # Load and clean data
        if uploaded_file.name.endswith(".csv"):
            df = pd.read_csv(uploaded_file)
        else:
            df = pd.read_excel(uploaded_file)

        # Normalize columns
        df.columns = df.columns.str.strip()

        if COL_NAME not in df.columns or COL_SCORE not in df.columns:
            st.error(f"File must contain columns: '{COL_NAME}' and '{COL_SCORE}'")
        else:
            # Clean types
            df[COL_NAME] = df[COL_NAME].astype(str).str.strip()
            df[COL_SCORE] = pd.to_numeric(df[COL_SCORE], errors="coerce").fillna(0)

            participants = df.to_dict("records")
            st.success(f"Loaded {len(participants)} participants.")

            with st.expander("View Data Preview"):
                st.dataframe(df.head())

            # 2. Settings
            # Limit max groups to number of participants to avoid error
            max_groups = len(participants) if len(participants) > 0 else 1
            num_groups = st.number_input(
                "Number of Groups", min_value=1, max_value=max_groups, value=2, step=1
            )

            # 3. Action
            if st.button("🚀 Generate Balanced Groups", type="primary"):
                with st.spinner("Solving mathematical model..."):
                    results = {}

                    # Scenario 1: Constrained
                    groups_c, found_c = solve_with_ortools(
                        participants, num_groups, respect_stars=True
                    )
                    if found_c:
                        results[SHEET_WITH_CONSTRAINT] = groups_c
                        std_c = np.std([g["avg"] for g in groups_c])
                    else:
                        std_c = float("inf")

                    # Scenario 2: Unconstrained
                    groups_u, found_u = solve_with_ortools(
                        participants, num_groups, respect_stars=False
                    )
                    if found_u:
                        std_u = np.std([g["avg"] for g in groups_u])

                        # Champion Logic:
                        # Sometimes the 'Constrained' logic inadvertently finds a better
                        # mathematical topology for size distribution than the 'Unconstrained'
                        # search path within the time limit. If Constrained is strictly better, use it.
                        # We save the winner into 'SHEET_BEST_RESULT'
                        if found_c and (std_c < std_u - 0.0001):
                            results[SHEET_BEST_RESULT] = groups_c
                        else:
                            results[SHEET_BEST_RESULT] = groups_u

                    # 4. Results & Export
                    if not results:
                        st.error(
                            "No solution found. Try reducing constraints or checking data."
                        )
                    else:
                        st.success("Optimization Complete!")

                        # Display Summary metrics
                        col1, col2 = st.columns(2)
                        if found_c:
                            col1.metric("StdDev (Strict Stars)", f"{std_c:.4f}")
                        if found_u:
                            col2.metric("StdDev (Best Possible)", f"{std_u:.4f}")

                        # Generate Excel
                        excel_data = generate_excel_bytes(results)

                        st.download_button(
                            label="📥 Download Excel Report",
                            data=excel_data,
                            file_name="balanced_groups.xlsx",
                            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                        )

                        # Visual Display of groups (Constrained)
                        if SHEET_WITH_CONSTRAINT in results:
                            st.subheader("Preview: Constrained Solution")
                            tabs = st.tabs(
                                [
                                    f"Group {g['id']}"
                                    for g in results[SHEET_WITH_CONSTRAINT]
                                ]
                            )
                            for i, tab in enumerate(tabs):
                                g = results[SHEET_WITH_CONSTRAINT][i]
                                with tab:
                                    st.write(f"**Average:** {g['avg']:.2f}")
                                    st.table(pd.DataFrame(g["members"]))

    except Exception as e:
        # FIX: Log full traceback for debugging, but keep UI message simple
        logger.exception("Error processing uploaded file")
        st.error(f"Error processing file: {e}")
