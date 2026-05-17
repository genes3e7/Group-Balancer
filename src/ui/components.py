"""Reusable UI components for the Streamlit application.

This module contains layout elements such as page configuration
and the progress/status header, optimized for asynchronous rendering.
"""

import streamlit as st


def setup_page() -> None:
    """Configures Streamlit page metadata and default layout parameters."""
    st.set_page_config(
        page_title="Group Balancer",
        page_icon="⚖️",
        layout="wide",
        initial_sidebar_state="collapsed",
    )


def render_header_description() -> None:
    """Renders the tool's header and instructional text."""
    st.title("⚖️ Group Balancer")
    st.markdown("""
           This tool uses the **Google OR-Tools CP-SAT** engine to optimize
           participant distribution into groups. It balances multiple scores
           simultaneously based on your assigned weights, prioritizing
           constraints based on your solver setup. For highly complex setups,
           increase the Max Runtime.
        """)


def render_step_progress(step: int) -> None:
    """Renders the progress indicators and step labels with ARIA semantics.

    Args:
        step (int): The current active step number (1, 2, or 3).
    """
    # Guard against out-of-bounds steps to maintain ARIA integrity
    clamped_step = max(1, min(step, 3))

    cols_labels = st.columns(3)
    labels = ["1. Upload Data", "2. Configure", "3. Results"]

    for i, col in enumerate(cols_labels):
        target = i + 1
        label = labels[i]
        with col:
            # aria-current indicates the active step to screen readers
            aria = ""
            if clamped_step == target:
                aria = 'aria-current="step"'
                st.markdown(
                    f'### <span {aria} style="color:#ff4b4b">{label}</span>',
                    unsafe_allow_html=True,
                )

            elif target < clamped_step:
                st.markdown(f"### {label}")
            else:
                st.markdown(f"### :gray[{label}]")

    # Logical progress bar for accessibility
    st.markdown(
        f'<div role="progressbar" aria-valuemin="1" aria-valuemax="3" '
        f'aria-valuenow="{clamped_step}" aria-label="Step {clamped_step} of 3" '
        f'style="position:absolute;width:1px;height:1px;overflow:hidden;clip:rect(1px,1px,1px,1px);white-space:nowrap;border:0;padding:0;margin:-1px;"></div>',
        unsafe_allow_html=True,
    )

    cols_bar = st.columns(3, gap="small")
    active_step_css = (
        "background-color: #ff4b4b; height: 4px; width: 100%; border-radius: 2px;"
    )
    inactive_step_css = (
        "background-color: #ddd; height: 4px; width: 100%; border-radius: 2px;"
    )

    for i, col in enumerate(cols_bar):
        target = i + 1
        css = active_step_css if target <= clamped_step else inactive_step_css
        # Individual segments are decorative; aria-hidden prevents redundancy
        col.markdown(
            f'<div aria-hidden="true" style="{css}"></div>',
            unsafe_allow_html=True,
        )
