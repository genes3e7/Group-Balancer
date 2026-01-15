"""
Main Entry Point for the Group Balancer Application.

This script acts as the controller, initializing the Streamlit session state
and routing the user to the appropriate step (1, 2, or 3) via the
session manager.
"""

import streamlit as st
from src.ui import components, session_manager, steps

components.setup_page()
session_manager.init_session()

components.render_page_header(st.session_state.step)

if st.session_state.step == 1:
    steps.render_step_1()

elif st.session_state.step == 2:
    steps.render_step_2()

elif st.session_state.step == 3:
    steps.render_step_3()

else:
    st.error("Invalid step. Resetting...")
    session_manager.go_to_step(1)
