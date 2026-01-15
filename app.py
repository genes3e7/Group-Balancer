import streamlit as st
from src.ui import components, session_manager, steps

# 1. Setup
components.setup_page()
session_manager.init_session()

# 2. Render Header
components.render_page_header(st.session_state.step)

# 3. Route to Current Step
if st.session_state.step == 1:
    steps.render_step_1()

elif st.session_state.step == 2:
    steps.render_step_2()

elif st.session_state.step == 3:
    steps.render_step_3()

else:
    # Fallback for invalid states
    st.error("Invalid step. Resetting...")
    session_manager.go_to_step(1)
