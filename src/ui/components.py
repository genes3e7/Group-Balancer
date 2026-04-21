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
           increase the Max Runtime or use Simple Mode.
        """)

    st.divider()

    # Progress steps using standard, safe Streamlit components
    # 1. Labels row
    cols_labels = st.columns(3)
    labels = ["1. Upload Data", "2. Configure", "3. Results"]

    for i, col in enumerate(cols_labels):
        target = i + 1
        label = labels[i]
        with col:
            if step == target:
                st.markdown(f"### :red[{label}]")
            elif target < step:
                st.markdown(f"### {label}")
            else:
                st.markdown(f"### :gray[{label}]")

    # 2. Contiguous Bar row using SVG data URIs
    # This provides the exact Red theme and contiguous look without XSS risk.
    # It scales dynamically with the container width.
    cols_bar = st.columns(3, gap="small")

    # Height is set to 2px for a thinner, professional look.
    red_svg = (
        "data:image/svg+xml,<svg xmlns='http://www.w3.org/2000/svg' "
        "width='100' height='2'><rect width='100' height='2' "
        "fill='%23ff4b4b'/></svg>"
    )
    gray_svg = (
        "data:image/svg+xml,<svg xmlns='http://www.w3.org/2000/svg' "
        "width='100' height='2'><rect width='100' height='2' "
        "fill='%23ddd'/></svg>"
    )

    for i, col in enumerate(cols_bar):
        target = i + 1
        with col:
            if target <= step:
                st.image(red_svg, width="stretch")
            else:
                st.image(gray_svg, width="stretch")

    st.write("")  # Final padding
