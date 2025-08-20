# pages/3_🧪_Gemini_Test.py
import streamlit as st
import vertexai
from vertexai.generative_models import GenerativeModel

st.set_page_config(page_title="Gemini API Test", page_icon="🧪", layout="wide")

st.title("🧪 Gemini API Connection Test")
st.markdown("""
This page is for debugging the connection to the Google Cloud Vertex AI (Gemini) API. 
Click the button below to send a simple request to the model.
""")

def run_gemini_test():
    """
    Initializes Vertex AI and sends a simple prompt to the Gemini model.
    """
    try:
        # --- IMPORTANT ---
        # Initialize Vertex AI with your specific project and location.
        # The location MUST match the region of your Cloud Run service.
        PROJECT_ID = "bess-dispatch-app"  # <-- Your Google Cloud Project ID
        LOCATION = "us-central1"        # <-- The region of your Cloud Run service

        vertexai.init(project=PROJECT_ID, location=LOCATION)
        
        # Load the Gemini model - Using the correct auto-updated alias
        model = GenerativeModel("gemini-2.5-flash-lite")

        prompt = "Hello! In one sentence, what is a Battery Energy Storage System?"
        
        response = model.generate_content(prompt)
        return response.text

    except Exception as e:
        # Return the full, detailed error message for debugging
        return f"An error occurred: {e}"

if st.button("Test Gemini Connection"):
    with st.spinner("Sending request to Gemini..."):
        response_text = run_gemini_test()
        st.subheader("Response from Gemini:")
        st.info(response_text)

