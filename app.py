"""Main Entry Point for the Group Balancer Application.

This script acts as the controller, initializing the Streamlit session state
and routing the user to the appropriate step (1, 2, or 3) via the
session manager. Uses asynchronous fragmentation and lazy loading to
eliminate render lag.
"""

import logging
import sys

import streamlit as st

from src.core import config
from src.ui import components, session_manager

# Configure global logger for the application
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
)


def main() -> None:
    """Main orchestration for the Group Balancer application."""
    components.setup_page()
    session_manager.init_session()

    # Persistent error handling for invalid routing or state issues
    if err := st.session_state.get("persistent_error"):
        st.error(err)
        if st.button("Dismiss", key="dismiss_persistent_error"):
            del st.session_state["persistent_error"]
            st.rerun()

    # Render header components independently to ensure immediate visual feedback
    components.render_header_description()
    st.divider()
    components.render_step_progress(st.session_state.step)
    render_app()


@st.fragment
def render_app() -> None:
    """Renders the main application steps asynchronously with lazy imports."""
    from src.ui import steps  # noqa: PLC0415

    if st.session_state.step == config.STEP_DATA_ENTRY:
        steps.render_step_1()

    elif st.session_state.step == config.STEP_CONFIGURE:
        steps.render_step_2()

    elif st.session_state.step == config.STEP_RESULTS:
        steps.render_step_3()

    else:
        st.session_state.persistent_error = "Invalid application step detected."
        session_manager.go_to_step(config.STEP_DATA_ENTRY)


if __name__ == "__main__":
    main()
