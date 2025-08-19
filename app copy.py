# app.py
import streamlit as st
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots
from optimization_engine import DA_Dispatch, ID_Dispatch, plot_market_revenue
import io

# --- Page Configuration ---
st.set_page_config(
    page_title="BESS Dispatch Optimizer",
    page_icon="🔋",
    layout="wide"
)

# --- Function to load custom CSS ---
def local_css(file_name):
    try:
        with open(file_name) as f:
            st.markdown(f"<style>{f.read()}</style>", unsafe_allow_html=True)
    except FileNotFoundError:
        # This allows the app to run even if the style.css is missing
        pass

# Load the custom CSS
local_css("style.css")


# --- App Title and Description ---
st.title("🔋 Battery Energy Storage System (BESS) Dispatch Optimizer")
st.markdown("""
This application optimizes BESS dispatch in Day-Ahead (DA) and Intra-Day (ID) markets using a Pyomo-based sequential optimization model.
First, select your price data source, then adjust the parameters in the sidebar and run the simulation.
""")

# --- Sidebar for User Inputs ---
st.sidebar.header("BESS Control Parameters")

# Sliders and number inputs for battery parameters
BESS_Size = st.sidebar.slider("BESS Size (MWh)", 10, 1000, 50, 10)
BESS_Duration = st.sidebar.slider("BESS Duration (Hours)", 1, 10, 2, 1)
BESS_Power = BESS_Size / BESS_Duration
st.sidebar.metric(label="BESS Power (MW)", value=f"{BESS_Power:.2f}")

BESS_Efficiency = st.sidebar.slider("BESS Roundtrip Efficiency (%)", 80, 100, 95, 1) / 100.0
Intial_SOC_pct = st.sidebar.slider("Initial State of Charge (%)", 0, 100, 10, 5) / 100.0
SOC_Min_pct = st.sidebar.slider("Minimum State of Charge (%)", 0, 50, 10, 5) / 100.0
SOC_Max_pct = st.sidebar.slider("Maximum State of Charge (%)", 50, 100, 100, 5) / 100.0

st.sidebar.header("Market & Degradation Parameters")
DA_Cycles = st.sidebar.slider("Max Cycles for DA Market", 0.5, 5.0, 1.0, 0.5)
ID_Cycles = st.sidebar.slider("Max Cycles for DA+ID Markets", 0.5, 5.0, 2.0, 0.5)
BESS_Degradation = st.sidebar.number_input("Degradation (MWh loss/MWh discharged)", 0.0, 0.001, 0.000054, format="%.6f")

st.sidebar.header("Forecasting Error Simulation")
DA_forecasting_error = st.sidebar.slider("DA Forecasting Error (%)", 0, 25, 0, 5) / 100.0
ID_forecasting_error = st.sidebar.slider("ID Forecasting Error (%)", 0, 25, 0, 5) / 100.0

# --- Data Input Section ---
st.subheader("1. Select Your Price Data")
data_source = st.radio(
    "Choose a data source:",
    ("Use Default Case (2021-2024)", "Upload your own CSV file"),
    horizontal=True,
    label_visibility="collapsed"
)

price_df = None  # Initialize price_df

if data_source == "Upload your own CSV file":
    uploaded_file = st.file_uploader("Upload Price Data (CSV)", type="csv")
    with st.expander("View Required CSV Format"):
        st.markdown("""
        The CSV file must contain three columns:
        1.  `UTC_PERIOD_START_DATETIME`: Timestamps for the price periods.
        2.  `N2EX`: Day-Ahead (DA) market prices in £/MWh.
        3.  `MIP`: Intra-Day (ID) market prices in £/MWh.
        """)
        sample_data = {
            'UTC_PERIOD_START_DATETIME': ['2023-01-01 00:00:00+00:00', '2023-01-01 00:30:00+00:00'],
            'N2EX': [68.0, 68.0],
            'MIP': [68.54, 69.82]
        }
        sample_df = pd.DataFrame(sample_data)
        st.dataframe(sample_df)
        st.download_button(
            label="Download Template CSV",
            data=sample_df.to_csv(index=False).encode('utf-8'),
            file_name='price_data_template.csv',
            mime='text/csv',
        )
    if uploaded_file:
        price_df = pd.read_csv(uploaded_file)

else:  # Default Case
    try:
        price_df = pd.read_csv("price_dataset.csv")
        st.success("Default 2021-2024 price data loaded successfully.")
    except FileNotFoundError:
        st.error("Default `price_dataset.csv` not found. Please upload a file.")
        price_df = None

# --- Main Application Logic ---
if price_df is not None:
    try:
        # Process the dataframe
        price_df['UTC_PERIOD_START_DATETIME'] = pd.to_datetime(price_df['UTC_PERIOD_START_DATETIME'])
        price_df = price_df.set_index('UTC_PERIOD_START_DATETIME')
        price_df.rename(columns={"N2EX": "DA[GBP/MWh]", "MIP": "ID[GBP/MWh]"}, inplace=True)

        st.sidebar.header("Simulation Period")
        start_date = st.sidebar.date_input("Start Date", price_df.index.min().date(), min_value=price_df.index.min().date(), max_value=price_df.index.max().date())
        end_date = st.sidebar.date_input("End Date", price_df.index.min().date() + pd.Timedelta(days=6), min_value=start_date, max_value=price_df.index.max().date())

        selected_price = price_df.loc[str(start_date):str(end_date)]

        if st.button("🚀 Run Optimization", use_container_width=True):
            with st.spinner("Running sequential optimization... This may take a few moments."):
                # --- Run Day-Ahead (DA) Optimization Loop ---
                st.info("Starting Day-Ahead Dispatch Simulation...")
                battery_params_da = {
                    'capacity_mwh': BESS_Size, 'duration_hours': BESS_Duration, 'max_power_mw': BESS_Power,
                    'charge_efficiency': BESS_Efficiency, 'discharge_efficiency': BESS_Efficiency,
                    'max_cycles_per_day': DA_Cycles, 'degradation_per_mwh_discharged': BESS_Degradation,
                    'initial_soc_[%]': Intial_SOC_pct, 'soc_min_[%]': SOC_Min_pct,
                    'soc_max_[%]': SOC_Max_pct, 'soh_initial_mwh': BESS_Size,
                    'DA_noise_[%]': DA_forecasting_error, 'ID_noise_[%]': ID_forecasting_error
                }

                final_DA_results_df = pd.DataFrame()
                total_days = len(selected_price) // 48
                progress_bar = st.progress(0)

                for day in range(total_days):
                    daily_price = selected_price.iloc[48*day:48*(day+1)]
                    daily_results = DA_Dispatch(daily_price, battery_params_da)
                    final_DA_results_df = pd.concat([final_DA_results_df, daily_results])
                    
                    if not daily_results.empty:
                        battery_params_da['initial_soc_[%]'] = float(daily_results['DA_SoC_MWh'].iloc[-1] / battery_params_da['capacity_mwh'])
                        battery_params_da['soh_initial_mwh'] = float(daily_results['DA_SoH_MWh'].iloc[-1])
                    progress_bar.progress((day + 1) / (total_days * 2))

                # --- Run Intra-Day (ID) Optimization Loop ---
                st.info("Starting Intra-Day Dispatch Simulation...")
                battery_params_id = {
                    'capacity_mwh': BESS_Size, 'duration_hours': BESS_Duration, 'max_power_mw': BESS_Power,
                    'charge_efficiency': BESS_Efficiency, 'discharge_efficiency': BESS_Efficiency,
                    'max_cycles_per_day': ID_Cycles, 'degradation_per_mwh_discharged': BESS_Degradation,
                    'initial_soc_[%]': Intial_SOC_pct, 'soc_min_[%]': SOC_Min_pct,
                    'soc_max_[%]': SOC_Max_pct, 'soh_initial_mwh': BESS_Size,
                    'DA_noise_[%]': DA_forecasting_error, 'ID_noise_[%]': ID_forecasting_error
                }

                final_ID_results_df = pd.DataFrame()
                for day in range(total_days):
                    daily_price = selected_price.iloc[48*day:48*(day+1)]
                    da_results_for_day = final_DA_results_df.iloc[48*day:48*(day+1)]
                    
                    daily_results = ID_Dispatch(daily_price, battery_params_id, da_results_for_day)
                    final_ID_results_df = pd.concat([final_ID_results_df, daily_results])

                    if not daily_results.empty:
                        battery_params_id['initial_soc_[%]'] = float(daily_results['SoC_Final_MWh'].iloc[-1] / battery_params_id['capacity_mwh'])
                        battery_params_id['soh_initial_mwh'] = float(daily_results['SoH_Final_MWh'].iloc[-1])
                    progress_bar.progress(0.5 + (day + 1) / (total_days * 2))

                progress_bar.empty()
                st.success("Optimization Complete!")

                # --- Combine and Display Results ---
                total_results = pd.concat([final_DA_results_df, final_ID_results_df], axis=1)
                
                # Store results in session state to be used by plotting controls
                st.session_state['total_results'] = total_results
                st.session_state['selected_price'] = selected_price
                st.session_state['price_df'] = price_df
                st.session_state['BESS_Power'] = BESS_Power

    except Exception as e:
        st.error(f"An error occurred: {e}")
        st.error("Please ensure the uploaded CSV has the correct format ('UTC_PERIOD_START_DATETIME', 'N2EX', 'MIP') and the dates are compatible.")

# --- Results Visualization Section ---
if 'total_results' in st.session_state:
    st.subheader("📊 Results Visualization")
    
    total_results = st.session_state['total_results']
    selected_price = st.session_state['selected_price']
    price_df = st.session_state['price_df']
    BESS_Power = st.session_state['BESS_Power']
    
    # --- Add controls for plotting period ---
    st.markdown("#### Adjust Dispatch Profile Plotting Period")
    plot_date = st.date_input("Select a Day to Plot", selected_price.index.min().date(), min_value=selected_price.index.min().date(), max_value=selected_price.index.max().date(), key="plot_date")
    
    plot_data = total_results.loc[str(plot_date)]
    plot_price_data = selected_price.loc[str(plot_date)]

    # --- Dispatch Profile Plot (Interactive with Plotly) ---
    st.markdown("#### Daily Dispatch Profile")

    # Create figure with secondary y-axis
    fig_dispatch = make_subplots(specs=[[{"secondary_y": True}]])

    # Add traces for dispatch
    fig_dispatch.add_trace(go.Bar(x=plot_data.index, y=plot_data['DA_Discharge_MWh'], name='Discharge DA (MWh)', marker_color='#FF7F0E'), secondary_y=False)
    fig_dispatch.add_trace(go.Bar(x=plot_data.index, y=-plot_data['DA_Charge_MWh'], name='Charge DA (MWh)', marker_color='#2CA02C'), secondary_y=False)
    fig_dispatch.add_trace(go.Bar(x=plot_data.index, y=plot_data['ID_Discharge_MWh'], name='Discharge ID (MWh)', marker_color='#FFBB78'), secondary_y=False)
    fig_dispatch.add_trace(go.Bar(x=plot_data.index, y=-plot_data['ID_Charge_MWh'], name='Charge ID (MWh)', marker_color='#98DF8A'), secondary_y=False)
    
    # Add trace for SoC
    fig_dispatch.add_trace(go.Scatter(x=plot_data.index, y=plot_data['SoC_Final_MWh'], name='SoC (MWh)', mode='lines', line=dict(color='red')), secondary_y=False)
    
    # Add traces for prices on secondary y-axis
    fig_dispatch.add_trace(go.Scatter(x=plot_price_data.index, y=plot_price_data['DA[GBP/MWh]'], name='DA Price (£/MWh)', mode='lines', line=dict(color='blue', dash='dash')), secondary_y=True)
    fig_dispatch.add_trace(go.Scatter(x=plot_price_data.index, y=plot_price_data['ID[GBP/MWh]'], name='ID Price (£/MWh)', mode='lines', line=dict(color='deepskyblue', dash='dot')), secondary_y=True)

    # Update layout
    fig_dispatch.update_layout(
        barmode='relative',
        title_text="Daily Dispatch and Market Prices",
        template="plotly_white",
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1)
    )
    fig_dispatch.update_xaxes(title_text="Time of Day")
    fig_dispatch.update_yaxes(title_text="<b>Energy (MWh)</b>", secondary_y=False)
    fig_dispatch.update_yaxes(title_text="<b>Price (£/MWh)</b>", secondary_y=True)
    
    st.plotly_chart(fig_dispatch, use_container_width=True)


    # --- Revenue Analysis Section ---
    st.subheader("Revenue Analysis for Full Simulation Period")
    
    da_revenue = (total_results['DA_Revenue_GBP']).sum()
    id_revenue = (total_results['ID_Revenue_GBP']).sum()
    total_revenue = da_revenue + id_revenue
    
    col1, col2, col3 = st.columns(3)
    col1.metric("Total Revenue", f"£{total_revenue:,.2f}")
    col2.metric("Day-Ahead Revenue", f"£{da_revenue:,.2f}")
    col3.metric("Intra-Day Revenue", f"£{id_revenue:,.2f}")
    
    st.markdown("---")
    
    col_rev1, col_rev2, col_rev3 = st.columns(3)

    with col_rev1:
        st.markdown("##### Daily Revenue (£/MW/Day)")
        daily_revenue = total_results[['DA_Revenue_GBP', 'ID_Revenue_GBP']].resample('D').sum()
        daily_revenue_normalized = daily_revenue / BESS_Power if BESS_Power > 0 else daily_revenue
        
        fig_daily_rev = go.Figure()
        fig_daily_rev.add_trace(go.Bar(x=daily_revenue_normalized.index, y=daily_revenue_normalized['DA_Revenue_GBP'], name='DA Revenue', marker_color='#FF7F0E'))
        fig_daily_rev.add_trace(go.Bar(x=daily_revenue_normalized.index, y=daily_revenue_normalized['ID_Revenue_GBP'], name='ID Revenue', marker_color='#1F77B4'))
        fig_daily_rev.update_layout(barmode='stack', template="plotly_white", legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1), height=350)
        st.plotly_chart(fig_daily_rev, use_container_width=True)

    with col_rev2:
        st.markdown("##### Yearly Revenue (£/MW/Year)")
        yearly_revenue = total_results[['DA_Revenue_GBP', 'ID_Revenue_GBP']].resample('Y').sum()
        yearly_revenue_normalized = yearly_revenue / BESS_Power if BESS_Power > 0 else yearly_revenue
        
        if yearly_revenue_normalized.empty:
            st.warning("Not enough data for a yearly plot.")
        else:
            yearly_revenue_normalized.index = yearly_revenue_normalized.index.year
            fig_yearly_rev = go.Figure()
            fig_yearly_rev.add_trace(go.Bar(x=yearly_revenue_normalized.index, y=yearly_revenue_normalized['DA_Revenue_GBP'], name='DA Revenue', marker_color='#FF7F0E'))
            fig_yearly_rev.add_trace(go.Bar(x=yearly_revenue_normalized.index, y=yearly_revenue_normalized['ID_Revenue_GBP'], name='ID Revenue', marker_color='#1F77B4'))
            fig_yearly_rev.update_layout(barmode='group', template="plotly_white", legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1), height=350)
            st.plotly_chart(fig_yearly_rev, use_container_width=True)

    with col_rev3:
        st.markdown("##### Revenue Split (Full Period)")
        positive_revenue_data = {'DA Market': da_revenue, 'ID Market': id_revenue}
        positive_revenue_data = {k: v for k, v in positive_revenue_data.items() if v > 0}
        
        if not positive_revenue_data:
            st.warning("No positive revenue generated.")
        else:
            fig_pie = go.Figure(data=[go.Pie(labels=list(positive_revenue_data.keys()), values=list(positive_revenue_data.values()), hole=.3)])
            fig_pie.update_layout(template="plotly_white", height=350, showlegend=False)
            st.plotly_chart(fig_pie, use_container_width=True)

    # --- Dataframe Display ---
    st.subheader("Dispatch Results Data (Full Simulation Period)")
    st.dataframe(total_results)
    
    csv = total_results.to_csv().encode('utf-8')
    st.download_button(
        label="📥 Download Full Simulation Data as CSV",
        data=csv,
        file_name='full_dispatch_results.csv',
        mime='text/csv',
    )
