"""Reusable UI components for the Streamlit application.

This module contains layout elements such as page configuration
and the progress/status header.
"""

import streamlit as st


def setup_page() -> None:
    """Configures the global Streamlit page settings.

    Sets the title, icon, and layout mode.
    """
    st.set_page_config(page_title="Group Balancer", page_icon="⚖️", layout="wide")


def render_page_header(step: int) -> None:
    """Renders the application header, description, and the progress steps bar.

    Args:
        step (int): The current step number (1, 2, or 3) to highlight.
    """
    st.markdown("""
    ### ⚖️ Group Balancer Tool
    **Optimizes team allocations based on individual scores and constraints.**
    Upload your participant data, configure the desired number of groups,
    and let the Constraint Programming solver mathematically minimize
    the difference in group averages.
    """)

    with st.expander("ℹ️ How to use this tool", expanded=False):
        st.markdown("""
        **Goal:** Create balanced groups from a list of participants.

        1. **Upload Data or Edit Manually:** Use an Excel/CSV file with a `Name`
           column and at least one `Score` column (e.g., `Score1`, `Score2`).
           You can also add score columns manually via the UI.
        2. **Groupers & Separators (Categorical Constraints):**
           - Every **single character** is treated as an independent tag.
           - *Example:* A tag of `GSA` creates three separate rules (`G`, `S`,
             and `A`). Commas and spaces are completely ignored.
           - **Groupers:** Participants sharing a grouper character
             will be kept together.
           - **Separators:** Participants sharing a separator character will
             be spread apart into different groups (e.g., Leaders).
        3. **Generate:** The algorithm will balance the dimensions
           simultaneously based on your assigned weights, prioritizing
           constraints based on your solver setup.
        """)

    st.divider()

    # Progress steps using standard, safe Streamlit components
    cols = st.columns(3)
    labels = ["1. Upload Data", "2. Configure", "3. Results"]

    for i, col in enumerate(cols):
        target_step = i + 1
        label = labels[i]

        with col:
            if step == target_step:
                # Active step is Red (mimicking the #ff4b4b from CSS)
                st.markdown(f"### :red[{label}]")
                st.divider()  # Creates the underlined effect
            elif step > target_step:
                # Completed steps
                st.markdown(f"### {label}")
                st.write("")
            else:
                # Future steps
                st.markdown(f"### :gray[{label}]")
                st.write("")

    st.write("")  # Final padding
