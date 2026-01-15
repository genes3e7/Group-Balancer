"""
Session State Management.

This module initializes the Streamlit session state and provides
navigation functions to move between steps.
"""

import streamlit as st
import pandas as pd
from src.core import config


def init_session() -> None:
    """
    Initializes all necessary session state variables.
    Checks each key independently to prevent partial state corruption.
    """
    defaults = {
        "step": 1,
        "participants_df": None,
        "results_df": None,
    }

    for key, value in defaults.items():
        if key not in st.session_state:
            st.session_state[key] = value

    if "manual_df" not in st.session_state:
        st.session_state.manual_df = pd.DataFrame(
            {
                config.COL_NAME: ["Player 1", "Player 2*", "Player 3"],
                config.COL_SCORE: [80, 95, 60],
            }
        )


def go_to_step(step: int) -> None:
    """
    Updates the step state and reruns the app.

    Args:
        step (int): The step number to navigate to (1-3).
    """
    if step not in (1, 2, 3):
        step = 1

    st.session_state.step = step
    st.rerun()
