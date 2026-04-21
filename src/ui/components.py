"""
Reusable UI components for the Streamlit application.

This module contains layout elements such as page configuration
and the progress/status header.
"""

import streamlit as st


def setup_page() -> None:
    """
    Configures the global Streamlit page settings.
    Sets the title, icon, and layout mode.
    """
    st.set_page_config(page_title="Group Balancer", page_icon="⚖️", layout="wide")


def render_page_header(step: int) -> None:
    """
    Renders the application header, description, and the progress steps bar.

    Args:
        step (int): The current step number (1, 2, or 3) to highlight.
    """
    st.markdown("""
    ### ⚖️ Group Balancer Tool
    **Optimizes team allocations based on individual scores and constraints.** Upload your participant data, configure the desired number of groups, and let the 
    Constraint Programming solver mathematically minimize the difference in group averages.
    """)

    with st.expander("ℹ️ How to use this tool", expanded=False):
        st.markdown("""
        **Goal:** Create balanced groups from a list of participants.
        
        1. **Upload Data or Edit Manually:** Use an Excel/CSV file with a `Name` column and at least one `Score` column (e.g., `Score1`, `Score2`). You can also add score columns manually via the UI.
        2. **Groupers & Separators (Categorical Constraints):**
           - Every **single character** in the Groupers or Separators cell is treated as an independent tag.
           - *Example:* A tag of `GSA` creates three separate rules (`G`, `S`, and `A`). Commas and spaces are completely ignored.
           - **Groupers:** Participants sharing a grouper character will be kept together.
           - **Separators:** Participants sharing a separator character will be spread apart into different groups (e.g., ensuring Leaders are distributed evenly).
        3. **Generate:** The algorithm will balance the dimensions simultaneously based on your assigned weights, prioritizing constraints based on your solver setup. For highly complex setups, increase the Max Runtime or use Simple Mode.
        """)

    st.markdown("---")

    st.markdown(
        f"""
    <style>
        .step-container {{ display: flex; justify-content: space-between; margin-bottom: 20px; }}
        .step {{ text-align: center; flex: 1; padding: 10px; border-bottom: 3px solid #ddd; color: #aaa; }}
        .active {{ border-bottom: 3px solid #ff4b4b; color: #ff4b4b; font-weight: bold; }}
        .completed {{ border-bottom: 3px solid #ff4b4b; color: #333; }}
        .stButton button {{ width: 100%; }}
    </style>
    <div class="step-container">
        <div class="step {"active" if step == 1 else "completed" if step > 1 else ""}">1. Upload Data</div>
        <div class="step {"active" if step == 2 else "completed" if step > 2 else ""}">2. Configure</div>
        <div class="step {"active" if step == 3 else "completed" if step > 3 else ""}">3. Results</div>
    </div>
    """,
        unsafe_allow_html=True,
    )
