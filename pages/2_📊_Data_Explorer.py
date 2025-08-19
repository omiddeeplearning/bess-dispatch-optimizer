# pages/2_📊_Data_Explorer.py
import streamlit as st
import pandas as pd

st.set_page_config(
    page_title="BESS Dispatch Optimizer",
    page_icon="🔎",
    layout="wide"
)

# --- Function to load custom CSS ---
def local_css(file_name):
    try:
        with open(file_name, "r") as f:
            st.markdown(f"<style>{f.read()}</style>", unsafe_allow_html=True)
    except FileNotFoundError:
        pass

local_css("style.css")


st.title("🔎 Data Explorer")
st.markdown("Explore the input price data and the detailed optimization results.")

if 'total_results' in st.session_state and st.session_state['total_results'] is not None:
    total_results = st.session_state['total_results']
    selected_price = st.session_state['selected_price']
    
    # Create tabs for different data views
    tab1, tab2 = st.tabs(["Input Price Data", "Optimization Results"])

    with tab1:
        st.subheader("Input Price Data (for simulation period)")
        st.markdown("This table shows the Day-Ahead and Intra-Day market prices for the period you selected for the simulation.")
        st.dataframe(selected_price)

    with tab2:
        st.subheader("Full Optimization Results")
        st.markdown("This table contains the detailed results of the dispatch optimization, including charge/discharge schedules, state of charge (SoC), and revenue for each time step.")
        st.dataframe(total_results)
        
        csv = total_results.to_csv().encode('utf-8')
        st.download_button(
            label="📥 Download Full Simulation Data as CSV",
            data=csv,
            file_name='full_dispatch_results.csv',
            mime='text/csv',
        )
else:
    st.info("Run an optimization on the Dashboard page to see the results here.")
