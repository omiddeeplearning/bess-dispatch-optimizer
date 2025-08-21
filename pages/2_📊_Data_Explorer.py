# pages/2_📊_Data_Explorer.py
import streamlit as st
import pandas as pd
import streamlit.components.v1 as components
import plotly.graph_objects as go
from plotly.subplots import make_subplots

# --- Page Configuration ---
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

# --- Page Header ---
header_html = """
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <script src="https://cdn.tailwindcss.com"></script>
    <link href="https://fonts.googleapis.com/css2?family=Poppins:wght@400;600;700;800&display=swap" rel="stylesheet">
    <style>
        body { font-family: 'Poppins', sans-serif; }
        .header-gradient { background: linear-gradient(90deg, #e3f2fd, #f0f2f5); }
    </style>
</head>
<body class="bg-transparent">
    <div class="header-gradient p-8 rounded-2xl border border-gray-200">
        <h1 class="text-4xl md:text-5xl font-bold text-gray-800">🔎 Data Explorer</h1>
        <p class="text-lg text-gray-600 mt-2">
            Interactively plot results and explore the raw simulation data.
        </p>
    </div>
</body>
</html>
"""
components.html(header_html, height=180)


if 'total_results' in st.session_state and st.session_state['total_results'] is not None:
    total_results = st.session_state['total_results']
    selected_price = st.session_state['selected_price']
    
    # --- Interactive Plotting Section ---
    st.markdown("---")
    st.subheader("Interactive Results Plotter")

    col1, col2 = st.columns(2)
    with col1:
        start_date = st.date_input(
            "Plot Start Date", 
            total_results.index.min().date(), 
            min_value=total_results.index.min().date(), 
            max_value=total_results.index.max().date()
        )
    with col2:
        end_date = st.date_input(
            "Plot End Date", 
            total_results.index.max().date(), 
            min_value=start_date, 
            max_value=total_results.index.max().date()
        )

    # Combine results and prices for plotting
    plot_df = pd.concat([total_results, selected_price], axis=1)
    
    # Filter dataframe based on date selection
    plot_df_filtered = plot_df.loc[str(start_date):str(end_date)]

    # Get available columns and separate them into categories
    available_columns = plot_df_filtered.columns.tolist()
    energy_power_cols = [col for col in available_columns if any(kw in col for kw in ['Charge', 'Discharge', 'SoC', 'SoH']) and 'GBP' not in col]
    price_revenue_cols = [col for col in available_columns if any(kw in col for kw in ['Price', 'Revenue', 'GBP'])]

    # --- Figure 1: Energy and Power ---
    st.markdown("#### Energy & Power Profile")
    y_energy_selection = st.multiselect(
        "Select energy/power data to plot:",
        options=energy_power_cols,
        default=[col for col in ['DA_Discharge_MWh', 'DA_Charge_MWh', 'SoC_Final_MWh'] if col in energy_power_cols]
    )

    if y_energy_selection:
        fig_energy = go.Figure()
        for column in y_energy_selection:
            if 'Charge' in column:
                fig_energy.add_trace(go.Bar(x=plot_df_filtered.index, y=-plot_df_filtered[column], name=column))
            elif 'Discharge' in column:
                fig_energy.add_trace(go.Bar(x=plot_df_filtered.index, y=plot_df_filtered[column], name=column))
            else:
                fig_energy.add_trace(go.Scatter(x=plot_df_filtered.index, y=plot_df_filtered[column], name=column, mode='lines'))
        
        fig_energy.update_layout(
            template="plotly_white",
            barmode='relative',
            title="Energy & Power Dispatch",
            xaxis_title="Date",
            yaxis_title="Energy (MWh) / Power (MW)"
        )
        st.plotly_chart(fig_energy, use_container_width=True)
    else:
        st.info("Select at least one energy or power series to plot.")

    # --- Figure 2: Price and Revenue ---
    st.markdown("#### Price & Revenue Profile")
    y_price_selection = st.multiselect(
        "Select price/revenue data to plot:",
        options=price_revenue_cols,
        default=[col for col in ['DA_Revenue_GBP', 'ID_Revenue_GBP', 'DA[GBP/MWh]'] if col in price_revenue_cols]
    )

    if y_price_selection:
        fig_price = make_subplots(specs=[[{"secondary_y": True}]])
        for column in y_price_selection:
            is_price = 'GBP/MWh' in column
            is_revenue = 'Revenue' in column
            
            if is_revenue:
                 fig_price.add_trace(
                    go.Bar(x=plot_df_filtered.index, y=plot_df_filtered[column], name=column),
                    secondary_y=False
                )
            else:
                fig_price.add_trace(
                    go.Scatter(x=plot_df_filtered.index, y=plot_df_filtered[column], name=column, mode='lines'),
                    secondary_y=is_price
                )
        
        fig_price.update_layout(
            template="plotly_white",
            title="Market Prices & Revenue",
            xaxis_title="Date",
            barmode='relative'
        )
        fig_price.update_yaxes(title_text="Revenue (£)", secondary_y=False)
        fig_price.update_yaxes(title_text="Price (£/MWh)", secondary_y=True)
        st.plotly_chart(fig_price, use_container_width=True)
    else:
        st.info("Select at least one price or revenue series to plot.")


    # --- Data Tables Section ---
    st.markdown("---")
    st.subheader("Raw Data Tables")
    tab1, tab2 = st.tabs(["Optimization Results", "Input Price Data"])

    with tab1:
        st.markdown("This table contains the detailed results of the dispatch optimization, including charge/discharge schedules, state of charge (SoC), and revenue for each time step.")
        st.dataframe(total_results)
        
        csv = total_results.to_csv().encode('utf-8')
        st.download_button(
            label="📥 Download Full Simulation Data as CSV",
            data=csv,
            file_name='full_dispatch_results.csv',
            mime='text/csv',
        )
        
    with tab2:
        st.markdown("This table shows the Day-Ahead and Intra-Day market prices for the period you selected for the simulation.")
        st.dataframe(selected_price)

else:
    st.info("Run an optimization on the Dashboard page to see the results here.")
