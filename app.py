# app.py
import streamlit as st

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
        pass

local_css("style.css")


# --- About Page Content ---
st.image("https://storage.googleapis.com/gemini-studio-images/google-ai-studio-gemini-logo-2024.svg", width=100)

st.title("About This Application")
st.markdown("""
This application provides a tool for optimizing Battery Energy Storage System (BESS) dispatch in Day-Ahead (DA) and Intra-Day (ID) markets.

Use the navigation in the sidebar to go to the **Dashboard** to run a simulation or the **Data Explorer** to view results.

### Methodology
The core of this application is a sequential optimization model built using Python and the Pyomo library.

- **Sequential Optimization:** The model first optimizes for the Day-Ahead market based on forecasted prices. The resulting dispatch schedule is then fixed as a commitment. Subsequently, the model optimizes for the Intra-Day market, taking the DA commitments into account. This two-stage process reflects the real-world operational workflow of energy markets.
- **BESS Degradation:** Battery degradation is modeled as a linear function of the BESS discharge throughput.

### AI-Powered Analysis with Google Gemini
This application leverages Google's Gemini model to provide an expert-level interpretation of the optimization results.
- **Automated Insights:** After running a simulation, you can generate an AI analysis that summarizes the financial performance, market strategy, and effectiveness of the dispatch.
- **Opportunity Identification:** The AI analyst will examine the price spreads in the market data to identify potential arbitrage opportunities and comment on how well the BESS strategy capitalized on them.

### Technologies Used
- **Backend:** Python, Pyomo, Pandas
- **Frontend:** Streamlit
- **Plotting:** Plotly
- **AI Model:** Google Gemini
- **Solver:** GLPK
""")

st.sidebar.success("Select a page above to get started.")
