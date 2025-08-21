# pages/1_⚡_Dashboard.py
import streamlit as st
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots
from optimization_engine import DA_Dispatch, ID_Dispatch
import io
import json
import streamlit.components.v1 as components

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


# --- LLM Helper Function ---
def get_llm_interpretation(results_summary, price_summary, start_date, end_date):
    """
    Sends a summary of the optimization results to the Vertex AI Gemini API
    and returns a natural language interpretation.
    """
    try:
        import vertexai
        from vertexai.generative_models import GenerativeModel

        PROJECT_ID = "bess-dispatch-app"
        LOCATION = "us-central1"

        vertexai.init(project=PROJECT_ID, location=LOCATION)
        model = GenerativeModel("gemini-2.5-flash-lite")

        prompt = f"""
        As an expert energy market analyst, create a humanized performance report for a BESS operating in the GB market between {start_date} and {end_date}.

        **Instructions:**
        1.  **Narrative Summary (One Paragraph):** Write a single paragraph that tells the story of the market during this period and how the BESS strategically responded. Mention key market dynamics (e.g., volatility, price spikes) and the battery's core actions (e.g., charging low, discharging high, focusing on a specific market).
        2.  **Key Highlights (Max 4 Bullet Points):** After the paragraph, provide up to four bullet points summarizing the most important outcomes.

        **Key Data Points to Weave into the Narrative and Highlights:**
        - **Analysis Period:** {start_date} to {end_date}
        - **Total Revenue:** £{results_summary['total_revenue']:,.2f}
        - **DA Market Revenue:** £{results_summary['da_revenue']:,.2f} ({results_summary['da_percentage']:.1f}%)
        - **ID Market Revenue:** £{results_summary['id_revenue']:,.2f} ({results_summary['id_percentage']:.1f}%)
        - **DA Price Range:** £{price_summary['da_min']:.2f} to £{price_summary['da_max']:.2f}
        - **ID Price Range:** £{price_summary['id_min']:.2f} to £{price_summary['id_max']:.2f}
        """
        
        response = model.generate_content(prompt)
        return response.text

    except Exception as e:
        return f"An error occurred during AI analysis: {e}"


# --- App Title and Description ---
dashboard_header_html = """
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <script src="https://cdn.tailwindcss.com"></script>
    <link rel="preconnect" href="https://fonts.googleapis.com">
    <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
    <link href="https://fonts.googleapis.com/css2?family=Poppins:wght@400;600;700;800&display=swap" rel="stylesheet">
    <style>
        body {
            font-family: 'Poppins', sans-serif;
        }
        .header-gradient {
            background: linear-gradient(90deg, #e3f2fd, #f0f2f5);
        }
    </style>
</head>
<body class="bg-transparent">
    <div class="header-gradient p-8 rounded-2xl border border-gray-200">
        <h1 class="text-4xl md:text-5xl font-bold text-gray-800">
            🔋 BESS Dispatch Dashboard
        </h1>
        <p class="text-lg text-gray-600 mt-2">
            Configure your BESS parameters, run the optimization, and visualize the financial results.
        </p>
    </div>
</body>
</html>
"""
components.html(dashboard_header_html, height=180)


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
st.markdown("---")
st.subheader("Simulation Setup")
data_source = st.radio(
    "Choose a data source:",
    ("Use Default Case (2021-2024)", "Upload your own CSV file"),
    horizontal=True
)

price_df = None
if data_source == "Upload your own CSV file":
    with st.expander("View Data Template and Instructions"):
        st.info("""
            **Please ensure your CSV file has the following three columns:**
            1.  `UTC_PERIOD_START_DATETIME`: The timestamp for the start of the period (e.g., `2023-01-01 00:00:00`).
            2.  `N2EX`: The Day-Ahead (DA) price in £/MWh.
            3.  `MIP`: The Intra-Day (ID) price in £/MWh.
            
            **Example Format:**
        """)
        template_df = pd.DataFrame({
            'UTC_PERIOD_START_DATETIME': ['2023-01-01 00:00:00', '2023-01-01 00:30:00'],
            'N2EX': [150.50, 145.20],
            'MIP': [155.75, 148.90]
        })
        st.dataframe(template_df)

    uploaded_file = st.file_uploader("Upload Price Data (CSV)", type="csv")
    if uploaded_file:
        price_df = pd.read_csv(uploaded_file)
else:
    try:
        price_df = pd.read_csv("price_dataset.csv")
    except FileNotFoundError:
        st.error("Default `price_dataset.csv` not found.")

if price_df is not None:
    try:
        price_df['UTC_PERIOD_START_DATETIME'] = pd.to_datetime(price_df['UTC_PERIOD_START_DATETIME'])
        price_df = price_df.set_index('UTC_PERIOD_START_DATETIME')
        price_df.rename(columns={"N2EX": "DA[GBP/MWh]", "MIP": "ID[GBP/MWh]"}, inplace=True)

        col1, col2 = st.columns(2)
        with col1:
            start_date = st.date_input("Start Date", price_df.index.min().date(), min_value=price_df.index.min().date(), max_value=price_df.index.max().date())
        with col2:
            end_date = st.date_input("End Date", price_df.index.min().date() + pd.Timedelta(days=6), min_value=start_date, max_value=price_df.index.max().date())
        
        selected_price = price_df.loc[str(start_date):str(end_date)]

        if st.button("🚀 Run Optimization", use_container_width=True):
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
                st.session_state['start_date_str'] = start_date.strftime("%Y-%m-%d")
                st.session_state['end_date_str'] = end_date.strftime("%Y-%m-%d")

    except Exception as e:
        st.error(f"An error occurred: {e}")

# --- Results Visualization ---
if st.session_state.get('total_results') is not None:
    total_results = st.session_state['total_results']
    selected_price = st.session_state['selected_price']
    BESS_Power = st.session_state['BESS_Power']
    start_date_str = st.session_state.get('start_date_str', '')
    end_date_str = st.session_state.get('end_date_str', '')

    # --- Updated Color Palette ---
    DA_COLOR, ID_COLOR = '#d62728', '#1f77b4' # Red for DA, Blue for ID
    CHARGE_DA_COLOR, CHARGE_ID_COLOR = '#ff9896', '#aec7e8' # Lighter shades for charging
    SOC_COLOR = '#2ca02c' # Green for SoC
    PRICE_DA_COLOR, PRICE_ID_COLOR = 'rgba(255, 127, 14, 0.9)', 'rgba(31, 119, 180, 0.9)' # Orange for DA Price, Blue for ID Price

    st.markdown("---")
    st.subheader("Key Performance Indicators")
    da_revenue = total_results['DA_Revenue_GBP'].sum()
    id_revenue = total_results['ID_Revenue_GBP'].sum()
    total_revenue = da_revenue + id_revenue
    
    kpi_html = f"""
    <html lang="en">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <script src="https://cdn.tailwindcss.com"></script>
        <link href="https://fonts.googleapis.com/css2?family=Poppins:wght@400;500;600;700&display=swap" rel="stylesheet">
        <style>
            body {{ font-family: 'Poppins', sans-serif; }}
            .kpi-card {{
                background-color: #ffffff;
                border: 1px solid #dee2e6;
                border-radius: 16px;
                padding: 1.5rem;
                box-shadow: 0 8px 24px rgba(0, 0, 0, 0.05);
                transition: all 0.3s ease;
            }}
            .kpi-card:hover {{
                transform: translateY(-5px);
                box-shadow: 0 12px 28px rgba(0, 0, 0, 0.08);
            }}
        </style>
    </head>
    <body class="bg-transparent">
        <div class="grid grid-cols-1 md:grid-cols-3 gap-6">
            <div class="kpi-card">
                <p class="text-lg text-gray-500">Total Revenue</p>
                <p class="text-4xl font-bold text-gray-800">£{total_revenue:,.2f}</p>
            </div>
            <div class="kpi-card">
                <p class="text-lg text-gray-500">DA Market Revenue</p>
                <p class="text-4xl font-bold text-blue-600">£{da_revenue:,.2f}</p>
            </div>
            <div class="kpi-card">
                <p class="text-lg text-gray-500">ID Market Revenue</p>
                <p class="text-4xl font-bold text-red-600">£{id_revenue:,.2f}</p>
            </div>
        </div>
    </body>
    </html>
    """
    components.html(kpi_html, height=150)

    st.markdown("---")
    
    ai_analysis_html = """
    <div style="background-color: #ffffff; border: 1px solid #dee2e6; border-radius: 16px; padding: 2rem; box-shadow: 0 8px 24px rgba(0, 0, 0, 0.05);">
        <h3 style="font-family: 'Poppins', sans-serif; font-size: 1.5rem; font-weight: 600; color: #333;">🤖 AI-Powered Analysis</h3>
        <p style="font-family: 'Poppins', sans-serif; color: #666; margin-top: 0.5rem;">
            Click the button below to generate an expert-level interpretation of the optimization results using Google's Gemini model.
        </p>
    </div>
    """
    st.markdown(ai_analysis_html, unsafe_allow_html=True)
    if st.button("Generate Analysis", use_container_width=True):
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
            st.session_state.llm_interpretation = get_llm_interpretation(results_summary, price_summary, start_date_str, end_date_str)

    if st.session_state.get('llm_interpretation'):
        st.info(st.session_state.llm_interpretation)

    st.markdown("---")

    col_rev1, col_rev2, col_rev3 = st.columns(3)
    with col_rev1:
        st.markdown("##### Daily Revenue (£/MW/Day)")
        daily_revenue = total_results[['DA_Revenue_GBP', 'ID_Revenue_GBP']].resample('D').sum()
        daily_revenue_normalized = daily_revenue / BESS_Power if BESS_Power > 0 else daily_revenue
        fig_daily_rev = go.Figure()
        fig_daily_rev.add_trace(go.Bar(x=daily_revenue_normalized.index, y=daily_revenue_normalized['DA_Revenue_GBP'], name='DA Revenue', marker_color=DA_COLOR))
        fig_daily_rev.add_trace(go.Bar(x=daily_revenue_normalized.index, y=daily_revenue_normalized['ID_Revenue_GBP'], name='ID Revenue', marker_color=ID_COLOR))
        fig_daily_rev.update_layout(barmode='stack', template="plotly_white", legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1), height=350, margin=dict(l=20, r=20, t=30, b=20))
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
            fig_yearly_rev.update_layout(barmode='group', template="plotly_white", legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1), height=350, margin=dict(l=20, r=20, t=30, b=20))
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
            fig_pie.update_layout(template="plotly_white", height=350, showlegend=True, margin=dict(l=20, r=20, t=30, b=20))
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
    fig_dispatch.add_trace(go.Scatter(x=plot_price_data.index, y=plot_price_data['DA[GBP/MWh]'], name='DA Price', mode='lines', line=dict(color=PRICE_DA_COLOR, dash='dash', width=2)), secondary_y=True)
    fig_dispatch.add_trace(go.Scatter(x=plot_price_data.index, y=plot_price_data['ID[GBP/MWh]'], name='ID Price', mode='lines', line=dict(color=PRICE_ID_COLOR, dash='dot', width=2)), secondary_y=True)
    fig_dispatch.update_layout(barmode='relative', title_text="Daily Dispatch Profile", template="plotly_white", legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1))
    fig_dispatch.update_yaxes(title_text="Power (MW) / SoC (MWh)", secondary_y=False)
    fig_dispatch.update_yaxes(title_text="Price (£/MWh)", secondary_y=True)
    st.plotly_chart(fig_dispatch, use_container_width=True)
