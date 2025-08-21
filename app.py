# app.py
import streamlit as st
import streamlit.components.v1 as components

# --- Page Configuration ---
st.set_page_config(
    page_title="DailyBattery Optimizer",
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
    </style>
</head>
<body class="bg-transparent">
    <div class="text-center pt-12 md:pt-20 pb-8 md:pb-12">
        <h1 class="text-5xl md:text-7xl font-extrabold text-gradient mb-4">
            Welcome to DailyBattery
        </h1>
        <p class="text-lg md:text-xl text-gray-600 max-w-3xl mx-auto mb-8">
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
        const newTextDelay = 2000; // Delay between current and next text
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

# --- Embed the Interactive Battery Simulator ---
st.markdown("<br>", unsafe_allow_html=True) # Add some space
try:
    with open("battery_sim.html", 'r', encoding='utf-8') as f:
        html_code = f.read()
        components.html(html_code, height=750, scrolling=False)
except FileNotFoundError:
    st.error("The battery_sim.html file was not found. Please make sure it's in the same directory as app.py.")


# --- New Features Section ---
features_html = """
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <script src="https://cdn.tailwindcss.com"></script>
    <link rel="preconnect" href="https://fonts.googleapis.com">
    <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
    <link href="https://fonts.googleapis.com/css2?family=Poppins:wght@400;500;600;700&display=swap" rel="stylesheet">
    <style>
        body {
            font-family: 'Poppins', sans-serif;
            background-color: #f0f2f5;
        }
        .feature-card {
            background-color: #ffffff;
            border: 1px solid #dee2e6;
            border-radius: 16px;
            padding: 2rem;
            box-shadow: 0 8px 24px rgba(0, 0, 0, 0.05);
            transition: all 0.3s ease;
        }
        .feature-card:hover {
            transform: translateY(-5px);
            box-shadow: 0 12px 28px rgba(0, 0, 0, 0.08);
        }
        .icon-bg {
            background: linear-gradient(135deg, #007bff, #0056b3);
        }
    </style>
</head>
<body>
    <div class="py-12 px-4">
        <div class="text-center mb-12">
            <h2 class="text-4xl font-bold text-gray-800">Core Methodology & AI Integration</h2>
            <p class="text-lg text-gray-600 mt-2">Discover the powerful features that drive our optimization engine.</p>
        </div>

        <div class="grid grid-cols-1 md:grid-cols-2 gap-8 max-w-6xl mx-auto">
            
            <!-- Card 1: Sequential Optimization -->
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

            <!-- Card 2: AI-Powered Analysis -->
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

            <!-- Card 3: Degradation Modeling -->
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

            <!-- Card 4: Tech Stack -->
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


st.sidebar.success("Select a page above to get started.")
