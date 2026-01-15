import streamlit as st


def setup_page():
    """Configures the Streamlit page settings."""
    st.set_page_config(page_title="Group Balancer", page_icon="⚖️", layout="wide")


def render_page_header(step: int) -> None:
    """
    Renders the progress bar and the app description.
    """
    # --- Site Description (Restored) ---
    st.markdown("""
    ### ⚖️ Group Balancer Tool
    **Optimizes team allocations based on individual scores and constraints.** Upload your participant data, configure the desired number of groups, and let the 
    Constraint Programming solver mathematically minimize the difference in group averages.
    """)

    # --- Instructions (Collapsible) ---
    with st.expander("ℹ️ How to use this tool", expanded=False):
        st.markdown("""
        **Goal:** Create balanced groups from a list of participants.
        
        1. **Upload Data:** Use an Excel or CSV file with `Name` and `Score` columns.
        2. **Star (*) Logic:** - If you want specific people to be distributed evenly across groups (e.g., senior leaders, experts), add a `*` to the end of their name in the input file.
           - *Example:* `John Doe*` will be treated as a "Star" player.
        3. **Generate:** The solver will mathematically minimize the score difference between groups.
        """)

    st.markdown("---")

    # --- Progress Bar ---
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
