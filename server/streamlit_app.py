import time
import os
import streamlit as st
import google.generativeai as genai
from dotenv import load_dotenv
import requests


load_dotenv()

GOOGLE_API_KEY = os.environ.get('GEMINI_API_KEY')
genai.configure(api_key=GOOGLE_API_KEY)

MODEL_ROLE = 'EEG chatbot'
API_URL = "http://localhost:8000/chat_context"

st.set_page_config(
    page_title="EEG-Aware AI Assistant", 
    page_icon="🧠",
    layout="wide"
)

def fetch_eeg_context():
    """Fetch real-time EEG data from backend API"""
    try:
        response = requests.get(API_URL)
        if response.status_code == 200:
            return response.json()
        else:
            st.warning("Could not connect to EEG service")
            return {"data": {"band_powers": {"delta": 0, "theta": 0, "alpha": 0, "beta": 0, "gamma": 0}, 
                            "fft_data": {"frequencies": [], "magnitudes": []}}}
    except Exception as e:
        st.error(f"Error fetching EEG context: {e}")
        return {"data": {"band_powers": {"delta": 0, "theta": 0, "alpha": 0, "beta": 0, "gamma": 0}, 
                        "fft_data": {"frequencies": [], "magnitudes": []}}}

def build_prompt(user_input, eeg_json):
    """Build a context-aware prompt including EEG data interpretation"""
    band_powers = eeg_json.get("data", {}).get("band_powers", {})
    fft_data = eeg_json.get("data", {}).get("fft_data", {})
    delta = band_powers.get("delta", 0.0)
    theta = band_powers.get("theta", 0.0)
    alpha = band_powers.get("alpha", 0.0)
    beta = band_powers.get("beta", 0.0)
    gamma = band_powers.get("gamma", 0.0)
    
    # Calculate beta/alpha ratio with safety check
    beta_alpha_ratio = round(beta / alpha, 3) if alpha != 0 else "N/A"

    return f"""
        You are a smart, emotionally aware AI assistant that reads real-time EEG signals to understand the user's current mental state.
        ---

        ### 🧠 EEG Input Context

        **Channel Source:** FP1–FP2 (frontal region)  
        **Signal Preprocessing:**  
        - Band-pass filter applied (0.5–40 Hz)  
        - Notch filter at 50 Hz to remove powerline noise  
        - PSD calculated using Welch's method (2-second windows)  
        - Band powers averaged over Alpha (8–12 Hz) and Beta (12–30 Hz)

        ---

        ### 🔢 Processed EEG Features

        **Band Powers (μV²/Hz):**
        - Delta (0.5–4 Hz): {delta}
        - Theta (4–8 Hz): {theta}
        - Alpha (8–13 Hz): {alpha}
        - Beta (13–30 Hz): {beta}
        - Gamma (30–50 Hz): {gamma}

        **Beta/Alpha Ratio:** {beta_alpha_ratio}

        **FFT Snapshot:**  
        Frequencies (Hz): {fft_data.get("frequencies", [])[:5]}  
        Magnitudes: {fft_data.get("magnitudes", [])[:5]}

        Note: The FFT data shows the frequency distribution of the EEG signal, which aids in identifying dominant bands or anomalies.

        ---

        ### 🧠 Interpretation Guide

        - **Delta ↑** → Sleep, healing, disconnection  
        - **Theta ↑** → Dreamy, emotional, imaginative  
        - **Alpha ↑** → Calm, relaxed, open  
        - **Beta ↑** → Focused, thinking, or anxious  
        - **Gamma ↑** → Learning, memory, high-level cognition  
        - **High Beta/Alpha Ratio** → Strong focus, task engagement  
        - **Low Beta/Alpha Ratio** → Relaxed, possibly distracted

        ---

        ### 🗣️ Adaptive Response Strategy

        Interpret the data above and infer the user's **current mental state** (e.g., fatigued, anxious, focused, creative, etc). Based on that, adapt your **tone** and **communication style**:

        - If stress or overwhelm → Be gentle, reassuring, and emotionally supportive.  
        - If deep focus → Be clear, concise, and cognitively efficient.  
        - If relaxed → Be reflective, exploratory, or philosophical.  
        - If fatigued or low energy → Be encouraging, light, and supportive.

        Avoid technical jargon unless the user's focus level suggests they are ready to process detailed information.

        ---

        ### 🧑 User Input:
        "{user_input}"

        ---

        Now be helpful, human-aware, and kind. give a short, relevant reply that fits their current mental and emotional state.
        """

if "messages" not in st.session_state:
    st.session_state.messages = []

st.title("🧠 EEG-Aware AI Assistant")
st.markdown("""
This assistant uses real-time EEG data to adapt its responses to your current mental state.
It interprets your brainwave patterns to provide more empathetic and context-appropriate answers.
""")

with st.sidebar:
    st.header("Current Brain Activity")
    eeg_data = fetch_eeg_context()
    band_powers = eeg_data.get("data", {}).get("band_powers", {})
    
    # Create metrics for each band
    col1, col2 = st.columns(2)
    with col1:
        st.metric("Delta", f"{band_powers.get('delta', 0):.2f}")
        st.metric("Theta", f"{band_powers.get('theta', 0):.2f}")
        st.metric("Alpha", f"{band_powers.get('alpha', 0):.2f}")
    with col2:
        st.metric("Beta", f"{band_powers.get('beta', 0):.2f}")
        st.metric("Gamma", f"{band_powers.get('gamma', 0):.2f}")
        if band_powers.get('alpha', 0) != 0:
            beta_alpha = band_powers.get('beta', 0) / band_powers.get('alpha', 0)
            st.metric("Beta/Alpha", f"{beta_alpha:.2f}")
    
    st.divider()
    st.markdown("### Interpretation Guide")
    st.markdown("""
    - **Delta ↑** → Sleep, healing
    - **Theta ↑** → Dreamy, imaginative
    - **Alpha ↑** → Calm, relaxed
    - **Beta ↑** → Focused or anxious
    - **Gamma ↑** → Learning, high cognition
    """)
    
    if st.button("Refresh EEG Data"):
        st.rerun()

for message in st.session_state.messages:
    with st.chat_message(message["role"]):
        st.write(message["content"])

# Chat input and response logic
if prompt := st.chat_input("What would you like to discuss?"):
    # Add user message to chat history and display
    st.session_state.messages.append({"role": "user", "content": prompt})
    with st.chat_message("user"):
        st.write(prompt)
    
    # Fetch fresh EEG data for this specific interaction
    eeg_context = fetch_eeg_context()
    
    # Display a spinner while generating response
    with st.spinner("Processing your request with EEG context..."):
        # Create the context-aware prompt
        full_prompt = build_prompt(prompt, eeg_context)
        
        # Initialize Gemini model
        model = genai.GenerativeModel('gemini-1.5-flash')
        
        # Send message to Gemini
        response = model.generate_content(full_prompt)
        
        # Create a message placeholder for streaming effect
        with st.chat_message(MODEL_ROLE):
            message_placeholder = st.empty()
            full_response = ""
            
            # Simulate streaming for better UX
            for word in response.text.split():
                full_response += word + " "
                time.sleep(0.01)
                message_placeholder.write(full_response + "▌")
            message_placeholder.write(full_response)
    
    # Add assistant response to chat history
    st.session_state.messages.append({"role": MODEL_ROLE, "content": full_response})
