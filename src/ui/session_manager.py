import streamlit as st
import pandas as pd
from src.core import config


def init_session():
    """Initializes all necessary session state variables."""
    # Ensure all keys exist independently to prevent partial state corruption
    defaults = {
        "step": 1,
        "participants_df": None,
        "results_df": None,
    }

    for key, value in defaults.items():
        if key not in st.session_state:
            st.session_state[key] = value

    # Initialize the 'working' dataframe for the editor if it doesn't exist
    if "manual_df" not in st.session_state:
        st.session_state.manual_df = pd.DataFrame(
            {
                config.COL_NAME: ["Player 1", "Player 2*", "Player 3"],
                config.COL_SCORE: [80, 95, 60],
            }
        )


def go_to_step(step):
    """Updates the step state and reruns the app."""
    # Validate step before switching
    if step not in (1, 2, 3):
        step = 1

    st.session_state.step = step
    st.rerun()
