"""Session State Management.

Initializes the Streamlit session state and guarantees that missing keys
(like the advanced constraints) are injected to prevent application crashes.
"""

import pandas as pd
import streamlit as st

from src.core import config


def init_session() -> None:
    """Initializes all necessary session state variables.

    Checks each key independently to prevent partial state corruption.
    """
    defaults = {
        "step": 1,
        "participants_df": None,
        "results_df": None,
        "interactive_df": None,
        "num_groups_target": 2,
        "group_capacities": [],
        "confirm_reset": False,
        "score_cols": [f"{config.SCORE_PREFIX}1"],
        "solver_status": None,
        "solver_elapsed": 0.0,
    }

    for key, value in defaults.items():
        if key not in st.session_state:
            st.session_state[key] = value

    if "manual_df" not in st.session_state:
        default_score_col = f"{config.SCORE_PREFIX}1"
        st.session_state.manual_df = pd.DataFrame(
            {
                config.COL_NAME: ["Alice", "Bob", "Charlie"],
                default_score_col: [80.0, 95.0, 60.0],
                config.COL_GROUPER: ["A", "A", ""],
                config.COL_SEPARATOR: ["", "X", "X"],
            },
        )


def go_to_step(target_step: int) -> None:
    """Updates the step state and reruns the app.

    Input validation clamps the target_step between 1 and 3.

    Args:
        target_step (int): The step number to navigate to (1-3).
    """
    st.session_state.step = max(1, min(3, target_step))
    st.rerun()
