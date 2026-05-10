"""Main Entry Point for the Group Balancer Application.

This script acts as the controller, initializing the Streamlit session state
and routing the user to the appropriate step (1, 2, or 3) via the
session manager. Uses asynchronous fragmentation and lazy loading to
eliminate render lag.
"""

import streamlit as st

from src.ui import components, session_manager

components.setup_page()
session_manager.init_session()

# Render header components independently to ensure immediate visual feedback
components.render_header_description()
st.divider()
components.render_step_progress(st.session_state.step)


@st.fragment
def render_app() -> None:
    """Renders the main application steps asynchronously with lazy imports."""
    from src.ui import steps

    if st.session_state.step == 1:
        steps.render_step_1()

    elif st.session_state.step == 2:
        steps.render_step_2()

    elif st.session_state.step == 3:
        steps.render_step_3()

    else:
        st.error("Invalid step. Resetting...")
        session_manager.go_to_step(1)


render_app()
