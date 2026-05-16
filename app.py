"""Main Entry Point for the Group Balancer Application.

This script acts as the controller, initializing the Streamlit session state
and routing the user to the appropriate step (1, 2, or 3) via the
session manager. Uses asynchronous fragmentation and lazy loading to
eliminate render lag.
"""

import streamlit as st

from src.ui import components, session_manager


def main() -> None:
    """Main orchestration for the Group Balancer application."""
    components.setup_page()
    session_manager.init_session()

    # Persistent error handling for invalid routing or state issues
    if err := st.session_state.get("persistent_error"):
        st.error(err)
        if st.button("Dismiss"):
            del st.session_state["persistent_error"]
            st.rerun()

    # Render header components independently to ensure immediate visual feedback
    components.render_header_description()
    st.divider()
    components.render_step_progress(st.session_state.step)
    render_app()


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
        st.session_state.persistent_error = "Invalid application step detected."
        session_manager.go_to_step(1)


if __name__ == "__main__":
    main()
