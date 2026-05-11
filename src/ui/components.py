"""Reusable UI components for the Streamlit application.

This module contains layout elements such as page configuration
and the progress/status header, optimized for asynchronous rendering.
"""

import streamlit as st


def setup_page() -> None:
    """Configures the global Streamlit page settings."""
    st.set_page_config(page_title="Group Balancer", page_icon="⚖️", layout="wide")


def render_header_description() -> None:
    """Renders the top-level tool description and help text."""
    st.markdown("""
    ### ⚖️ Group Balancer Tool
    **Optimizes team allocations based on individual scores and constraints.**
    Upload your participant data, configure the desired number of groups,
    and let the Constraint Programming solver mathematically minimize the
    difference in group averages.
    """)

    with st.expander("ℹ️ How to use this tool", expanded=False):
        st.markdown("""
        **Goal:** Create balanced groups from a list of participants.

        1. **Upload Data or Edit Manually:** Use an Excel/CSV file with a `Name`
           column and at least one `Score` column (e.g., `Score1`, `Score2`).
           You can also add score columns manually via the UI.
        2. **Groupers & Separators (Categorical Constraints):**
           - Every **single character** in the Groupers or Separators cell is
             treated as an independent tag.
           - *Example:* A tag of `GSA` creates three separate rules (`G`, `S`,
             and `A`). Commas and spaces are completely ignored.
           - **Groupers:** Participants sharing a grouper character
             will be kept together.
           - **Separators:** Participants sharing a separator character will
             be spread apart into different groups (e.g., Leaders).
        3. **Generate:** The algorithm will balance the dimensions
           simultaneously based on your assigned weights, prioritizing
           constraints based on your solver setup. For highly complex setups,
           increase the Max Runtime.
        """)


def render_step_progress(step: int) -> None:
    """Renders the progress indicators and step labels with ARIA semantics.

    Args:
        step (int): The current active step number (1, 2, or 3).
    """
    cols_labels = st.columns(3)
    labels = ["1. Upload Data", "2. Configure", "3. Results"]

    for i, col in enumerate(cols_labels):
        target = i + 1
        label = labels[i]
        with col:
            # aria-current indicates the active step to screen readers
            aria = 'aria-current="step"' if step == target else ""
            if step == target:
                st.markdown(
                    f'### <span {aria} style="color:#ff4b4b">{label}</span>',
                    unsafe_allow_html=True,
                )

            elif target < step:
                st.markdown(f"### {label}")
            else:
                st.markdown(f"### :gray[{label}]")

    # Logical progress bar for accessibility
    st.markdown(
        f'<div role="progressbar" aria-valuemin="1" aria-valuemax="3" '
        f'aria-valuenow="{step}" aria-label="Step {step} of 3" '
        f'style="display:none"></div>',
        unsafe_allow_html=True,
    )

    cols_bar = st.columns(3, gap="small")
    red_css = "background-color: #ff4b4b; height: 4px; width: 100%; border-radius: 2px;"
    gray_css = "background-color: #ddd; height: 4px; width: 100%; border-radius: 2px;"

    for i, col in enumerate(cols_bar):
        target = i + 1
        css = red_css if target <= step else gray_css
        # Individual segments are decorative; aria-hidden prevents redundancy
        col.markdown(
            f'<div aria-hidden="true" style="{css}"></div>',
            unsafe_allow_html=True,
        )
