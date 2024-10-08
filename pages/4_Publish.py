import streamlit as st

from modules import get_comfy_client, get_workspace_model
from modules.comfyflow import Comfyflow

# Set page configuration
st.set_page_config(layout="wide", initial_sidebar_state="collapsed")

# Hide the sidebar and its elements completely
st.markdown("""
<style>
    [data-testid="collapsedControl"] {display: none}
    section[data-testid="stSidebar"] {display: none}
    div[data-testid="stToolbar"] {display: none}
    #MainMenu {visibility: hidden}
    header {visibility: hidden}
    footer {visibility: hidden}
</style>
""", unsafe_allow_html=True)


# Retrieve query parameters
query_params = st.experimental_get_query_params()

# Access specific parameters
app_name = query_params.get("name", [""])[0]
if not app_name or app_name=="":
    st.write("No App name")
    st.stop()

workspace_model= get_workspace_model()
app = workspace_model.get_app(app_name.upper())
if not app:
    st.write(f"Not found this App name:{app_name}")
    st.stop()
comfy_client = get_comfy_client()
comfyflow = Comfyflow(comfy_client=comfy_client, api_data=app.api_conf, app_data=app.app_conf)
comfyflow.create_ui()



