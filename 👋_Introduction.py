# 👋_Introduction.py
import streamlit as st
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots
from optimization_engine import DA_Dispatch, ID_Dispatch
import io
import json
import streamlit.components.v1 as components
from streamlit_option_menu import option_menu

# --- Page Configuration ---
st.set_page_config(
    page_title="DailyBattery Optimizer",
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
if 'start_date_str' not in st.session_state:
    st.session_state['start_date_str'] = ''
if 'end_date_str' not in st.session_state:
    st.session_state['end_date_str'] = ''


# --- LLM Helper Function ---
def get_llm_interpretation(results_summary, price_summary, start_date, end_date):
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


# --- Top Navigation Bar ---
selected = option_menu(
    menu_title=None,
    options=["Introduction", "Dashboard", "Data Explorer"],
    icons=["house", "clipboard-data", "search"],
    menu_icon="cast",
    default_index=0,
    orientation="horizontal",
    styles={
        "container": {"padding": "0!important", "background-color": "#fafafa"},
        "icon": {"color": "orange", "font-size": "25px"},
        "nav-link": {
            "font-size": "25px",
            "text-align": "left",
            "margin": "0px",
            "--hover-color": "#eee",
        },
        "nav-link-selected": {"background-color": "#007bff"},
    },
)

# --- Page Content ---

if selected == "Introduction":
    # --- Interactive Header ---
    header_html = """
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
            .text-gradient {
                background: -webkit-linear-gradient(45deg, #007bff, #1a2b4d);
                -webkit-background-clip: text;
                -webkit-text-fill-color: transparent;
            }
            .typing-container .text {
                border-right: .15em solid #007bff; /* The cursor */
                white-space: nowrap;
                overflow: hidden;
                margin: 0 auto;
                letter-spacing: .1em; 
            }
            /* Mobile Responsive Styles */
            @media (max-width: 768px) {
                .welcome-header {
                    font-size: 2.5rem !important;
                }
                .welcome-subtext {
                    font-size: 1rem !important;
                }
                .typing-container {
                    font-size: 1.25rem !important;
                }
            }
        </style>
    </head>
    <body class="bg-transparent">
        <div class="text-center pt-12 md:pt-20 pb-8 md:pb-12">
            <h1 class="text-5xl md:text-7xl font-extrabold text-gradient mb-4 welcome-header">
                Welcome to DailyBattery
            </h1>
            <p class="text-lg md:text-xl text-gray-600 max-w-3xl mx-auto mb-8 welcome-subtext">
                Your daily AI-powered guide to the GB energy market. We analyze the latest data to reveal how much you could earn across various services.
            </p>
            <div class="typing-container text-2xl md:text-3xl font-semibold text-gray-800">
                <span>Potential earnings in the </span>
                <span id="typed-text" class="text text-blue-600"></span>
            </div>
        </div>

        <script>
            const typedTextSpan = document.getElementById("typed-text");
            const textArray = ["Day-Ahead Market.", "Intra-Day Market.", "Dynamic Containment.", "Frequency Response."];
            const typingDelay = 100;
            const erasingDelay = 50;
            const newTextDelay = 2000;
            let textArrayIndex = 0;
            let charIndex = 0;

            function type() {
                if (charIndex < textArray[textArrayIndex].length) {
                    typedTextSpan.textContent += textArray[textArrayIndex].charAt(charIndex);
                    charIndex++;
                    setTimeout(type, typingDelay);
                } else {
                    setTimeout(erase, newTextDelay);
                }
            }

            function erase() {
                if (charIndex > 0) {
                    typedTextSpan.textContent = textArray[textArrayIndex].substring(0, charIndex - 1);
                    charIndex--;
                    setTimeout(erase, erasingDelay);
                } else {
                    textArrayIndex++;
                    if (textArrayIndex >= textArray.length) textArrayIndex = 0;
                    setTimeout(type, typingDelay + 1100);
                }
            }

            document.addEventListener("DOMContentLoaded", function() { 
                if(textArray.length) setTimeout(type, newTextDelay + 250);
            });
        </script>
    </body>
    </html>
    """
    components.html(header_html, height=350)

    st.markdown("<br>", unsafe_allow_html=True)
    try:
        with open("battery_sim.html", 'r', encoding='utf-8') as f:
            html_code = f.read()
            components.html(html_code, height=750, scrolling=False)
    except FileNotFoundError:
        st.error("The battery_sim.html file was not found.")

    features_html = """
    <html lang="en">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <script src="https://cdn.tailwindcss.com"></script>
        <link href="https://fonts.googleapis.com/css2?family=Poppins:wght@400;500;600;700&display=swap" rel="stylesheet">
        <style>
            body { font-family: 'Poppins', sans-serif; background-color: #f0f2f5; }
            .feature-card { background-color: #ffffff; border: 1px solid #dee2e6; border-radius: 16px; padding: 2rem; box-shadow: 0 8px 24px rgba(0, 0, 0, 0.05); transition: all 0.3s ease; }
            .feature-card:hover { transform: translateY(-5px); box-shadow: 0 12px 28px rgba(0, 0, 0, 0.08); }
            .icon-bg { background: linear-gradient(135deg, #007bff, #0056b3); }
        </style>
    </head>
    <body>
        <div class="py-12 px-4">
            <div class="text-center mb-12">
                <h2 class="text-4xl font-bold text-gray-800">Core Methodology & AI Integration</h2>
                <p class="text-lg text-gray-600 mt-2">Discover the powerful features that drive our optimization engine.</p>
            </div>
            <div class="grid grid-cols-1 md:grid-cols-2 gap-8 max-w-6xl mx-auto">
                <div class="feature-card">
                    <div class="flex items-center mb-4">
                        <div class="w-12 h-12 rounded-full icon-bg flex items-center justify-center mr-4">
                            <svg class="w-6 h-6 text-white" fill="none" stroke="currentColor" viewBox="0 0 24 24" xmlns="http://www.w3.org/2000/svg"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 5H7a2 2 0 00-2 2v12a2 2 0 002 2h10a2 2 0 002-2V7a2 2 0 00-2-2h-2M9 5a2 2 0 002 2h2a2 2 0 002-2M9 5a2 2 0 012-2h2a2 2 0 012 2m-3 7h3m-3 4h3m-6-4h.01M9 16h.01"></path></svg>
                        </div>
                        <h3 class="text-2xl font-semibold text-gray-800">Sequential Optimization</h3>
                    </div>
                    <p class="text-gray-600">
                        Our model mirrors real-world energy markets by first optimizing for Day-Ahead prices, then using that as a baseline to capture further opportunities in the Intra-Day market.
                    </p>
                </div>
                <div class="feature-card">
                    <div class="flex items-center mb-4">
                        <div class="w-12 h-12 rounded-full icon-bg flex items-center justify-center mr-4">
                            <svg class="w-6 h-6 text-white" fill="none" stroke="currentColor" viewBox="0 0 24 24" xmlns="http://www.w3.org/2000/svg"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9.663 17h4.673M12 3v1m6.364 1.636l-.707.707M21 12h-1M4 12H3m3.343-5.657l-.707-.707m2.828 9.9a5 5 0 117.072 0l-.548.547A3.374 3.374 0 0014 18.469V19a2 2 0 11-4 0v-.531c0-.895-.356-1.754-.988-2.386l-.548-.547z"></path></svg>
                        </div>
                        <h3 class="text-2xl font-semibold text-gray-800">AI-Powered Analysis</h3>
                    </div>
                    <p class="text-gray-600">
                        Leverage Google's Gemini model for expert-level interpretation of results, automatically identifying key strategies and missed arbitrage opportunities to refine your approach.
                    </p>
                </div>
                <div class="feature-card">
                    <div class="flex items-center mb-4">
                        <div class="w-12 h-12 rounded-full icon-bg flex items-center justify-center mr-4">
                            <svg class="w-6 h-6 text-white" fill="none" stroke="currentColor" viewBox="0 0 24 24" xmlns="http://www.w3.org/2000/svg"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M19 11H5m14 0a2 2 0 012 2v6a2 2 0 01-2 2H5a2 2 0 01-2-2v-6a2 2 0 012-2m14 0V9a2 2 0 00-2-2M5 11V9a2 2 0 012-2m0 0V5a2 2 0 012-2h6a2 2 0 012 2v2M7 7h10"></path></svg>
                        </div>
                        <h3 class="text-2xl font-semibold text-gray-800">Degradation Modeling</h3>
                    </div>
                    <p class="text-gray-600">
                        To ensure long-term profitability, our model incorporates battery degradation costs, calculated as a linear function of discharge throughput for realistic asset management.
                    </p>
                </div>
                <div class="feature-card">
                    <div class="flex items-center mb-4">
                        <div class="w-12 h-12 rounded-full icon-bg flex items-center justify-center mr-4">
                            <svg class="w-6 h-6 text-white" fill="none" stroke="currentColor" viewBox="0 0 24 24" xmlns="http://www.w3.org/2000/svg"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M10 20l4-16m4 4l4 4-4 4M6 16l-4-4 4-4"></path></svg>
                        </div>
                        <h3 class="text-2xl font-semibold text-gray-800">Technologies Used</h3>
                    </div>
                    <div class="flex flex-wrap gap-2">
                        <span class="bg-gray-200 text-gray-700 text-sm font-medium px-3 py-1 rounded-full">Python</span>
                        <span class="bg-gray-200 text-gray-700 text-sm font-medium px-3 py-1 rounded-full">Pyomo</span>
                        <span class="bg-gray-200 text-gray-700 text-sm font-medium px-3 py-1 rounded-full">Streamlit</span>
                        <span class="bg-gray-200 text-gray-700 text-sm font-medium px-3 py-1 rounded-full">Plotly</span>
                        <span class="bg-gray-200 text-gray-700 text-sm font-medium px-3 py-1 rounded-full">Google Gemini</span>
                    </div>
                </div>
            </div>
        </div>
    </body>
    </html>
    """
    components.html(features_html, height=800)


if selected == "Dashboard":
    # --- Dashboard Content ---
    dashboard_header_html = """
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
            <h1 class="text-4xl md:text-5xl font-bold text-gray-800">🔋 BESS Dispatch Dashboard</h1>
            <p class="text-lg text-gray-600 mt-2">Configure your BESS parameters, run the optimization, and visualize the financial results.</p>
        </div>
    </body>
    </html>
    """
    components.html(dashboard_header_html, height=180)

    with st.sidebar:
        st.header("BESS Control Parameters")
        BESS_Size = st.slider("BESS Size (MWh)", 10, 1000, 50, 10)
        BESS_Duration = st.slider("BESS Duration (Hours)", 1, 10, 2, 1)
        BESS_Power = BESS_Size / BESS_Duration
        st.metric(label="BESS Power (MW)", value=f"{BESS_Power:.2f}")
        BESS_Efficiency = st.slider("BESS Roundtrip Efficiency (%)", 80, 100, 95, 1) / 100.0
        Intial_SOC_pct = st.slider("Initial State of Charge (%)", 0, 100, 10, 5) / 100.0
        SOC_Min_pct = st.slider("Minimum State of Charge (%)", 0, 50, 10, 5) / 100.0
        SOC_Max_pct = st.slider("Maximum State of Charge (%)", 50, 100, 100, 5) / 100.0
        st.header("Market & Degradation Parameters")
        DA_Cycles = st.slider("Max Cycles for DA Market", 0.5, 5.0, 1.0, 0.5)
        ID_Cycles = st.slider("Max Cycles for DA+ID Markets", 0.5, 5.0, 2.0, 0.5)
        BESS_Degradation = st.number_input("Degradation (MWh loss/MWh discharged)", 0.0, 0.001, 0.000054, format="%.6f")
        st.header("Forecasting Error Simulation")
        DA_forecasting_error = st.slider("DA Forecasting Error (%)", 0, 25, 0, 5) / 100.0
        ID_forecasting_error = st.slider("ID Forecasting Error (%)", 0, 25, 0, 5) / 100.0

    st.markdown("---")
    st.subheader("Simulation Setup")
    data_source = st.radio("Choose a data source:", ("Use Default Case (2021-2024)", "Upload your own CSV file"), horizontal=True)

    price_df = None
    if data_source == "Upload your own CSV file":
        with st.expander("View Data Template and Instructions"):
            st.info("""
                **Please ensure your CSV file has the following three columns:**
                1.  `UTC_PERIOD_START_DATETIME`: The timestamp for the start of the period (e.g., `2023-01-01 00:00:00`).
                2.  `N2EX`: The Day-Ahead (DA) price in £/MWh.
                3.  `MIP`: The Intra-Day (ID) price in £/MWh.
            """)
            template_df = pd.DataFrame({'UTC_PERIOD_START_DATETIME': ['2023-01-01 00:00:00', '2023-01-01 00:30:00'], 'N2EX': [150.50, 145.20], 'MIP': [155.75, 148.90]})
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
                    battery_params = {'capacity_mwh': BESS_Size, 'max_power_mw': BESS_Power, 'charge_efficiency': BESS_Efficiency, 'discharge_efficiency': BESS_Efficiency, 'initial_soc_[%]': Intial_SOC_pct, 'soc_min_[%]': SOC_Min_pct, 'soc_max_[%]': SOC_Max_pct, 'soh_initial_mwh': BESS_Size, 'DA_noise_[%]': DA_forecasting_error, 'ID_noise_[%]': ID_forecasting_error, 'degradation_per_mwh_discharged': BESS_Degradation}
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

    if st.session_state.get('total_results') is not None:
        total_results = st.session_state['total_results']
        selected_price = st.session_state['selected_price']
        BESS_Power = st.session_state['BESS_Power']
        start_date_str = st.session_state.get('start_date_str', '')
        end_date_str = st.session_state.get('end_date_str', '')
        DA_COLOR, ID_COLOR = '#d62728', '#1f77b4'
        CHARGE_DA_COLOR, CHARGE_ID_COLOR = '#ff9896', '#aec7e8'
        SOC_COLOR = '#2ca02c'
        PRICE_DA_COLOR, PRICE_ID_COLOR = 'rgba(255, 127, 14, 0.9)', 'rgba(31, 119, 180, 0.9)'
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
                .kpi-card {{ background-color: #ffffff; border: 1px solid #dee2e6; border-radius: 16px; padding: 1.5rem; box-shadow: 0 8px 24px rgba(0, 0, 0, 0.05); transition: all 0.3s ease; }}
                .kpi-card:hover {{ transform: translateY(-5px); box-shadow: 0 12px 28px rgba(0, 0, 0, 0.08); }}
            </style>
        </head>
        <body class="bg-transparent">
            <div class="grid grid-cols-1 md:grid-cols-3 gap-6">
                <div class="kpi-card"><p class="text-lg text-gray-500">Total Revenue</p><p class="text-4xl font-bold text-gray-800">£{total_revenue:,.2f}</p></div>
                <div class="kpi-card"><p class="text-lg text-gray-500">DA Market Revenue</p><p class="text-4xl font-bold text-blue-600">£{da_revenue:,.2f}</p></div>
                <div class="kpi-card"><p class="text-lg text-gray-500">ID Market Revenue</p><p class="text-4xl font-bold text-red-600">£{id_revenue:,.2f}</p></div>
            </div>
        </body>
        </html>
        """
        components.html(kpi_html, height=150)
        st.markdown("---")
        ai_analysis_html = """
        <div style="background-color: #ffffff; border: 1px solid #dee2e6; border-radius: 16px; padding: 2rem; box-shadow: 0 8px 24px rgba(0, 0, 0, 0.05);">
            <h3 style="font-family: 'Poppins', sans-serif; font-size: 1.5rem; font-weight: 600; color: #333;">🤖 AI-Powered Analysis</h3>
            <p style="font-family: 'Poppins', sans-serif; color: #666; margin-top: 0.5rem;">Click the button below to generate an expert-level interpretation of the optimization results using Google's Gemini model.</p>
        </div>
        """
        st.markdown(ai_analysis_html, unsafe_allow_html=True)
        if st.button("Generate Analysis", use_container_width=True):
            with st.spinner("AI is analyzing the results..."):
                total_days = (selected_price.index.max() - selected_price.index.min()).days
                results_summary = {"total_revenue": total_revenue, "da_revenue": da_revenue, "id_revenue": id_revenue, "da_percentage": (da_revenue / total_revenue * 100) if total_revenue else 0, "id_percentage": (id_revenue / total_revenue * 100) if total_revenue else 0, "total_days": total_days, "avg_daily_revenue": total_revenue / total_days if total_days > 0 else 0, "bess_power": BESS_Power, "bess_capacity": BESS_Size}
                price_summary = {"da_min": selected_price['DA[GBP/MWh]'].min(), "da_max": selected_price['DA[GBP/MWh]'].max(), "da_avg": selected_price['DA[GBP/MWh]'].mean(), "id_min": selected_price['ID[GBP/MWh]'].min(), "id_max": selected_price['ID[GBP/MWh]'].max(), "id_avg": selected_price['ID[GBP/MWh]'].mean()}
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


if selected == "Data Explorer":
    # --- Data Explorer Content ---
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
            <p class="text-lg text-gray-600 mt-2">Interactively plot results and explore the raw simulation data.</p>
        </div>
    </body>
    </html>
    """
    components.html(header_html, height=180)

    if 'total_results' in st.session_state and st.session_state['total_results'] is not None:
        total_results = st.session_state['total_results']
        selected_price = st.session_state['selected_price']
        st.markdown("---")
        st.subheader("Interactive Results Plotter")
        col1, col2 = st.columns(2)
        with col1:
            start_date = st.date_input("Plot Start Date", total_results.index.min().date(), min_value=total_results.index.min().date(), max_value=total_results.index.max().date())
        with col2:
            end_date = st.date_input("Plot End Date", total_results.index.max().date(), min_value=start_date, max_value=total_results.index.max().date())
        plot_df = pd.concat([total_results, selected_price], axis=1)
        plot_df_filtered = plot_df.loc[str(start_date):str(end_date)]
        available_columns = plot_df_filtered.columns.tolist()
        energy_power_cols = [col for col in available_columns if any(kw in col for kw in ['Charge', 'Discharge', 'SoC', 'SoH']) and 'GBP' not in col]
        price_revenue_cols = [col for col in available_columns if any(kw in col for kw in ['Price', 'Revenue', 'GBP'])]
        st.markdown("#### Energy & Power Profile")
        y_energy_selection = st.multiselect("Select energy/power data to plot:", options=energy_power_cols, default=[col for col in ['DA_Discharge_MWh', 'DA_Charge_MWh', 'SoC_Final_MWh'] if col in energy_power_cols])
        if y_energy_selection:
            fig_energy = go.Figure()
            for column in y_energy_selection:
                if 'Charge' in column:
                    fig_energy.add_trace(go.Bar(x=plot_df_filtered.index, y=-plot_df_filtered[column], name=column))
                elif 'Discharge' in column:
                    fig_energy.add_trace(go.Bar(x=plot_df_filtered.index, y=plot_df_filtered[column], name=column))
                else:
                    fig_energy.add_trace(go.Scatter(x=plot_df_filtered.index, y=plot_df_filtered[column], name=column, mode='lines'))
            fig_energy.update_layout(template="plotly_white", barmode='relative', title="Energy & Power Dispatch", xaxis_title="Date", yaxis_title="Energy (MWh) / Power (MW)")
            st.plotly_chart(fig_energy, use_container_width=True)
        else:
            st.info("Select at least one energy or power series to plot.")
        st.markdown("#### Price & Revenue Profile")
        y_price_selection = st.multiselect("Select price/revenue data to plot:", options=price_revenue_cols, default=[col for col in ['DA_Revenue_GBP', 'ID_Revenue_GBP', 'DA[GBP/MWh]'] if col in price_revenue_cols])
        if y_price_selection:
            fig_price = make_subplots(specs=[[{"secondary_y": True}]])
            for column in y_price_selection:
                is_price = 'GBP/MWh' in column
                is_revenue = 'Revenue' in column
                if is_revenue:
                    fig_price.add_trace(go.Bar(x=plot_df_filtered.index, y=plot_df_filtered[column], name=column), secondary_y=False)
                else:
                    fig_price.add_trace(go.Scatter(x=plot_df_filtered.index, y=plot_df_filtered[column], name=column, mode='lines'), secondary_y=is_price)
            fig_price.update_layout(template="plotly_white", title="Market Prices & Revenue", xaxis_title="Date", barmode='relative')
            fig_price.update_yaxes(title_text="Revenue (£)", secondary_y=False)
            fig_price.update_yaxes(title_text="Price (£/MWh)", secondary_y=True)
            st.plotly_chart(fig_price, use_container_width=True)
        else:
            st.info("Select at least one price or revenue series to plot.")
        st.markdown("---")
        st.subheader("Raw Data Tables")
        tab1, tab2 = st.tabs(["Optimization Results", "Input Price Data"])
        with tab1:
            st.markdown("This table contains the detailed results of the dispatch optimization, including charge/discharge schedules, state of charge (SoC), and revenue for each time step.")
            st.dataframe(total_results)
            csv = total_results.to_csv().encode('utf-8')
            st.download_button(label="📥 Download Full Simulation Data as CSV", data=csv, file_name='full_dispatch_results.csv', mime='text/csv')
        with tab2:
            st.markdown("This table shows the Day-Ahead and Intra-Day market prices for the period you selected for the simulation.")
            st.dataframe(selected_price)
    else:
        st.info("Run an optimization on the Dashboard page to see the results here.")
