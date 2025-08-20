# pages/1_⚡_Dashboard.py
import streamlit as st
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots
from optimization_engine import DA_Dispatch, ID_Dispatch
import io
import json
import vertexai
from vertexai.generative_models import GenerativeModel

# --- Page Configuration ---
st.set_page_config(
    page_title="BESS Dispatch Optimizer",
    page_icon="🔋",
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

# --- Initialize Session State ---
if 'total_results' not in st.session_state:
    st.session_state['total_results'] = None
if 'selected_price' not in st.session_state:
    st.session_state['selected_price'] = None
if 'BESS_Power' not in st.session_state:
    st.session_state['BESS_Power'] = 0
if 'llm_interpretation' not in st.session_state:
    st.session_state['llm_interpretation'] = ""


# --- LLM Helper Function (Corrected for Vertex AI) ---
def get_llm_interpretation(results_summary, price_summary):
    """
    Sends a summary of the optimization results to the Vertex AI Gemini API
    and returns a natural language interpretation.
    """
    try:
        # --- IMPORTANT ---
        # Initialize Vertex AI with your specific project and location.
        # The location MUST match the region of your Cloud Run service.
        PROJECT_ID = "bess-dispatch-app"  # <-- Your Google Cloud Project ID
        LOCATION = "us-central1"        # <-- The region of your Cloud Run service

        vertexai.init(project=PROJECT_ID, location=LOCATION)
        
        # Load the Gemini model
        model = GenerativeModel("gemini-1.5-flash-001")

        prompt = f"""
        You are an expert financial analyst in the energy sector. Your task is to provide a concise, insightful summary of a Battery Energy Storage System (BESS) dispatch optimization.

        Based on the following results and market price data, provide a brief analysis (in 4-5 bullet points). 
        In addition to the points below, please analyze the price data to identify potential arbitrage opportunities (significant spreads between high and low prices) and comment on how effectively the optimization strategy captured these opportunities.

        Focus on:
        1.  Overall revenue performance.
        2.  The market participation split (Day-Ahead vs. Intra-Day).
        3.  Notable strategic behavior (e.g., capitalizing on price volatility).
        4.  How well the strategy captured available price spreads in the markets.

        Results Summary:
        - Total Revenue: £{results_summary['total_revenue']:,.2f}
        - Day-Ahead (DA) Market Revenue: £{results_summary['da_revenue']:,.2f}
        - Intra-Day (ID) Market Revenue: £{results_summary['id_revenue']:,.2f}
        - DA Revenue Percentage: {results_summary['da_percentage']:.1f}%
        - ID Revenue Percentage: {results_summary['id_percentage']:.1f}%
        - Total Simulation Days: {results_summary['total_days']}
        - Average Daily Revenue: £{results_summary['avg_daily_revenue']:,.2f}
        - BESS Power: {results_summary['bess_power']} MW
        - BESS Capacity: {results_summary['bess_capacity']} MWh

        Market Price Summary (£/MWh) for the period:
        - DA Price - Min: {price_summary['da_min']:.2f}, Max: {price_summary['da_max']:.2f}, Avg: {price_summary['da_avg']:.2f}
        - ID Price - Min: {price_summary['id_min']:.2f}, Max: {price_summary['id_max']:.2f}, Avg: {price_summary['id_avg']:.2f}

        Please begin your analysis with a clear, one-sentence summary.
        """
        
        response = model.generate_content(prompt)
        return response.text

    except Exception as e:
        return f"An error occurred during AI analysis: {e}"


# --- App Title and Description ---
st.title("🔋 BESS Dispatch Optimizer Dashboard")
st.markdown("Run the BESS dispatch optimization and visualize the results.")

# --- Sidebar ---
st.sidebar.header("BESS Control Parameters")
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
st.subheader("1. Select Price Data")
data_source = st.radio(
    "Choose a data source:",
    ("Use Default Case (2021-2024)", "Upload your own CSV file"),
    horizontal=True, label_visibility="collapsed"
)

price_df = None
if data_source == "Upload your own CSV file":
    uploaded_file = st.file_uploader("Upload Price Data (CSV)", type="csv")
    if uploaded_file:
        price_df = pd.read_csv(uploaded_file)
else:
    try:
        price_df = pd.read_csv("price_dataset.csv")
        st.success("Default 2021-2024 price data loaded.")
    except FileNotFoundError:
        st.error("Default `price_dataset.csv` not found.")

if price_df is not None:
    try:
        price_df['UTC_PERIOD_START_DATETIME'] = pd.to_datetime(price_df['UTC_PERIOD_START_DATETIME'])
        price_df = price_df.set_index('UTC_PERIOD_START_DATETIME')
        price_df.rename(columns={"N2EX": "DA[GBP/MWh]", "MIP": "ID[GBP/MWh]"}, inplace=True)

        st.subheader("2. Define Simulation Period & Run")
        col1, col2, col3 = st.columns([1,1,2])
        start_date = col1.date_input("Start Date", price_df.index.min().date(), min_value=price_df.index.min().date(), max_value=price_df.index.max().date())
        end_date = col2.date_input("End Date", price_df.index.min().date() + pd.Timedelta(days=6), min_value=start_date, max_value=price_df.index.max().date())
        
        selected_price = price_df.loc[str(start_date):str(end_date)]

        if col3.button("🚀 Run Optimization", use_container_width=True):
            with st.spinner("Running optimization..."):
                st.session_state.clear() 
                battery_params = {
                    'capacity_mwh': BESS_Size, 'max_power_mw': BESS_Power,
                    'charge_efficiency': BESS_Efficiency, 'discharge_efficiency': BESS_Efficiency,
                    'initial_soc_[%]': Intial_SOC_pct, 'soc_min_[%]': SOC_Min_pct,
                    'soc_max_[%]': SOC_Max_pct, 'soh_initial_mwh': BESS_Size,
                    'DA_noise_[%]': DA_forecasting_error, 'ID_noise_[%]': ID_forecasting_error,
                    'degradation_per_mwh_discharged': BESS_Degradation
                }

                final_DA_results_df = pd.DataFrame()
                total_days = len(selected_price) // 48
                progress_bar = st.progress(0, text="Running DA Optimization...")
                for day in range(total_days):
                    daily_price = selected_price.iloc[48*day:48*(day+1)]
                    battery_params['max_cycles_per_day'] = DA_Cycles
                    daily_results = DA_Dispatch(daily_price, battery_params)
                    final_DA_results_df = pd.concat([final_DA_results_df, daily_results])
                    if not daily_results.empty:
                        battery_params['initial_soc_[%]'] = float(daily_results['DA_SoC_MWh'].iloc[-1] / battery_params['capacity_mwh'])
                        battery_params['soh_initial_mwh'] = float(daily_results['DA_SoH_MWh'].iloc[-1])
                    progress_bar.progress((day + 1) / (total_days * 2), text=f"DA Day {day+1}/{total_days}")
                
                battery_params['initial_soc_[%]'] = Intial_SOC_pct
                battery_params['soh_initial_mwh'] = BESS_Size
                final_ID_results_df = pd.DataFrame()
                progress_bar.progress(0.5, text="Running ID Optimization...")
                for day in range(total_days):
                    daily_price = selected_price.iloc[48*day:48*(day+1)]
                    da_results_for_day = final_DA_results_df.iloc[48*day:48*(day+1)]
                    battery_params['max_cycles_per_day'] = ID_Cycles
                    daily_results = ID_Dispatch(daily_price, battery_params, da_results_for_day)
                    final_ID_results_df = pd.concat([final_ID_results_df, daily_results])
                    if not daily_results.empty:
                        battery_params['initial_soc_[%]'] = float(daily_results['SoC_Final_MWh'].iloc[-1] / battery_params['capacity_mwh'])
                        battery_params['soh_initial_mwh'] = float(daily_results['SoH_Final_MWh'].iloc[-1])
                    progress_bar.progress(0.5 + (day + 1) / (total_days * 2), text=f"ID Day {day+1}/{total_days}")
                
                progress_bar.empty()
                st.success("Optimization Complete!")
                st.session_state['total_results'] = pd.concat([final_DA_results_df, final_ID_results_df], axis=1)
                st.session_state['selected_price'] = selected_price
                st.session_state['BESS_Power'] = BESS_Power
                st.session_state['llm_interpretation'] = ""

    except Exception as e:
        st.error(f"An error occurred: {e}")

# --- Results Visualization ---
if st.session_state.get('total_results') is not None:
    total_results = st.session_state['total_results']
    selected_price = st.session_state['selected_price']
    BESS_Power = st.session_state['BESS_Power']

    DA_COLOR, ID_COLOR, CHARGE_DA_COLOR, CHARGE_ID_COLOR, SOC_COLOR, PRICE_DA_COLOR, PRICE_ID_COLOR = '#F08080', '#6495ED', '#8FBC8F', '#98FB98', '#ADD8E6', 'rgba(255, 255, 255, 0.5)', 'rgba(200, 200, 200, 0.5)'

    st.subheader("Key Performance Indicators")
    da_revenue = total_results['DA_Revenue_GBP'].sum()
    id_revenue = total_results['ID_Revenue_GBP'].sum()
    total_revenue = da_revenue + id_revenue
    
    col1, col2, col3 = st.columns(3)
    col1.metric("Total Revenue", f"£{total_revenue:,.2f}")
    col2.metric("DA Market Revenue", f"£{da_revenue:,.2f}")
    col3.metric("ID Market Revenue", f"£{id_revenue:,.2f}")

    st.markdown("---")
    
    st.subheader("🤖 AI-Powered Analysis")
    if st.button("Generate Analysis"):
        with st.spinner("AI is analyzing the results..."):
            total_days = (selected_price.index.max() - selected_price.index.min()).days
            results_summary = {
                "total_revenue": total_revenue, "da_revenue": da_revenue, "id_revenue": id_revenue,
                "da_percentage": (da_revenue / total_revenue * 100) if total_revenue else 0,
                "id_percentage": (id_revenue / total_revenue * 100) if total_revenue else 0,
                "total_days": total_days,
                "avg_daily_revenue": total_revenue / total_days if total_days > 0 else 0,
                "bess_power": BESS_Power, "bess_capacity": BESS_Size
            }
            price_summary = {
                "da_min": selected_price['DA[GBP/MWh]'].min(), "da_max": selected_price['DA[GBP/MWh]'].max(), "da_avg": selected_price['DA[GBP/MWh]'].mean(),
                "id_min": selected_price['ID[GBP/MWh]'].min(), "id_max": selected_price['ID[GBP/MWh]'].max(), "id_avg": selected_price['ID[GBP/MWh]'].mean(),
            }
            st.session_state.llm_interpretation = get_llm_interpretation(results_summary, price_summary)

    if st.session_state.get('llm_interpretation'):
        st.markdown(st.session_state.llm_interpretation)

    st.markdown("---")

    col_rev1, col_rev2, col_rev3 = st.columns(3)
    with col_rev1:
        st.markdown("##### Daily Revenue (£/MW/Day)")
        daily_revenue = total_results[['DA_Revenue_GBP', 'ID_Revenue_GBP']].resample('D').sum()
        daily_revenue_normalized = daily_revenue / BESS_Power if BESS_Power > 0 else daily_revenue
        fig_daily_rev = go.Figure()
        fig_daily_rev.add_trace(go.Bar(x=daily_revenue_normalized.index, y=daily_revenue_normalized['DA_Revenue_GBP'], name='DA Revenue', marker_color=DA_COLOR))
        fig_daily_rev.add_trace(go.Bar(x=daily_revenue_normalized.index, y=daily_revenue_normalized['ID_Revenue_GBP'], name='ID Revenue', marker_color=ID_COLOR))
        fig_daily_rev.update_layout(barmode='stack', template="plotly_dark", legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1), height=350, margin=dict(l=20, r=20, t=30, b=20))
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
            fig_yearly_rev.add_trace(go.Bar(x=yearly_revenue_normalized.index, y=yearly_revenue_normalized['DA_Revenue_GBP'], name='DA Revenue', marker_color=DA_COLOR))
            fig_yearly_rev.add_trace(go.Bar(x=yearly_revenue_normalized.index, y=yearly_revenue_normalized['ID_Revenue_GBP'], name='ID Revenue', marker_color=ID_COLOR))
            fig_yearly_rev.update_layout(barmode='group', template="plotly_dark", legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1), height=350, margin=dict(l=20, r=20, t=30, b=20))
            st.plotly_chart(fig_yearly_rev, use_container_width=True)

    with col_rev3:
        st.markdown("##### Revenue Split (Full Period)")
        positive_revenue_data = {'DA Market': da_revenue, 'ID Market': id_revenue}
        positive_revenue_data = {k: v for k, v in positive_revenue_data.items() if v > 0}
        if not positive_revenue_data:
            st.warning("No positive revenue generated.")
        else:
            fig_pie = go.Figure(data=[go.Pie(labels=list(positive_revenue_data.keys()), values=list(positive_revenue_data.values()), hole=.4)])
            fig_pie.update_traces(marker=dict(colors=[DA_COLOR, ID_COLOR]))
            fig_pie.update_layout(template="plotly_dark", height=350, showlegend=True, margin=dict(l=20, r=20, t=30, b=20))
            st.plotly_chart(fig_pie, use_container_width=True)

    st.markdown("---")
    st.subheader("Dispatch Profile")
    plot_date = st.date_input("Select a Day to Visualize", selected_price.index.min().date(), min_value=selected_price.index.min().date(), max_value=selected_price.index.max().date())
    
    plot_data = total_results.loc[str(plot_date)]
    plot_price_data = selected_price.loc[str(plot_date)]

    fig_dispatch = make_subplots(specs=[[{"secondary_y": True}]])
    fig_dispatch.add_trace(go.Bar(x=plot_data.index, y=plot_data['DA_Discharge_MWh'], name='Discharge DA', marker_color=DA_COLOR), secondary_y=False)
    fig_dispatch.add_trace(go.Bar(x=plot_data.index, y=-plot_data['DA_Charge_MWh'], name='Charge DA', marker_color=CHARGE_DA_COLOR), secondary_y=False)
    fig_dispatch.add_trace(go.Bar(x=plot_data.index, y=plot_data['ID_Discharge_MWh'], name='Discharge ID', marker_color=ID_COLOR), secondary_y=False)
    fig_dispatch.add_trace(go.Bar(x=plot_data.index, y=-plot_data['ID_Charge_MWh'], name='Charge ID', marker_color=CHARGE_ID_COLOR), secondary_y=False)
    fig_dispatch.add_trace(go.Scatter(x=plot_data.index, y=plot_data['SoC_Final_MWh'], name='SoC', mode='lines', line=dict(color=SOC_COLOR)), secondary_y=False)
    fig_dispatch.add_trace(go.Scatter(x=plot_price_data.index, y=plot_price_data['DA[GBP/MWh]'], name='DA Price', mode='lines', line=dict(color=PRICE_DA_COLOR, dash='dash')), secondary_y=True)
    fig_dispatch.add_trace(go.Scatter(x=plot_price_data.index, y=plot_price_data['ID[GBP/MWh]'], name='ID Price', mode='lines', line=dict(color=PRICE_ID_COLOR, dash='dot')), secondary_y=True)
    fig_dispatch.update_layout(barmode='relative', title_text="Daily Dispatch Profile", template="plotly_dark", legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1))
    st.plotly_chart(fig_dispatch, use_container_width=True)
