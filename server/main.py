from fastapi import FastAPI, Request, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from fastapi.staticfiles import StaticFiles
import uvicorn
import logging
from collections import deque
import google.generativeai as genai
from pydantic import BaseModel
import json
from utlis import calculate_band_powers, calculate_fft
from dotenv import load_dotenv
import os

load_dotenv()
GEMINI_API_KEY= os.environ["GEMINI_API_KEY"]

# Logger setup
logger = logging.getLogger("esp32_app")
logger.setLevel(logging.INFO)
formatter = logging.Formatter("[%(asctime)s] [%(levelname)s] %(message)s", "%Y-%m-%d %H:%M:%S")

app = FastAPI()
templates = Jinja2Templates(directory="templates")
# app.mount("/static", StaticFiles(directory="static"), name="static")



# CORS settings
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# EEG buffer (1280 = 5 seconds at 256 Hz)
eeg_buffer = deque(maxlen=1280)
connected_clients = []
SAMPLE_RATE = 256  # Hz

# eeg_context = {
#     "type": "eeg_data",
#     "data": [],  # Raw EEG data
#     "fft_data": {
#         "frequencies": [],
#         "magnitudes": []
#     },
#     "band_powers": {
#         "delta": 0,
#         "theta": 0,
#         "alpha": 0,
#         "beta": 0,
#         "gamma": 0
#     }
# }


eeg_context = {
            "type": "eeg_data",
            "data": [],
            "fft_data": {
                "frequencies": [],
                "magnitudes": []
            },
            "band_powers": []
        }
        

@app.get("/chat_context")
def get_chat_context():
    print(eeg_context)
    context_for_chatbot={
        "type": "eeg_data",
        "fft_data": {
                "frequencies": eeg_context["fft_data"].get("frequencies", [])[-50:],
                "magnitudes": eeg_context["fft_data"].get("magnitudes", [])[-50:]
            },
            "band_powers": eeg_context["band_powers"]
    }

    return {"data": context_for_chatbot}

@app.get("/")
def debug_route():
    return {"data":"hello omkar and esp32"}

# @app.get('/chatbot', response_class=HTMLResponse)
# async def get_chatbot():
    html_content="""
    <!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>EEG Brain Assistant</title>
    <style>
        :root {
            --primary-color: #4dd0e1;
            --secondary-color: #00acc1;
            --bg-color: #121212;
            --card-bg: #1e1e1e;
            --text-color: #f5f5f5;
            --border-radius: 12px;
            --shadow: 0 4px 20px rgba(0, 0, 0, 0.2);
            --highlight: rgba(77, 208, 225, 0.15);
        }
        
        * {
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }
        
        body {
            font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
            background-color: var(--bg-color);
            color: var(--text-color);
            line-height: 1.6;
            padding: 20px;
            display: flex;
            flex-direction: column;
            min-height: 100vh;
        }
        
        .container {
            max-width: 1200px;
            margin: 0 auto;
            width: 100%;
            display: flex;
            flex-direction: column;
            flex: 1;
        }
        
        header {
            display: flex;
            justify-content: space-between;
            align-items: center;
            margin-bottom: 20px;
            flex-wrap: wrap;
        }
        
        h1 {
            color: var(--primary-color);
            font-size: 28px;
            margin-right: 20px;
        }
        
        .nav-links {
            display: flex;
            gap: 15px;
        }
        
        .nav-link {
            color: var(--text-color);
            text-decoration: none;
            padding: 8px 15px;
            border-radius: 20px;
            transition: all 0.3s ease;
            font-weight: 500;
        }
        
        .nav-link:hover, .nav-link.active {
            background-color: var(--highlight);
            color: var(--primary-color);
        }
        
        .main-content {
            display: flex;
            flex: 1;
            gap: 20px;
            flex-direction: column;
        }
        
        @media (min-width: 768px) {
            .main-content {
                flex-direction: row;
            }
        }
        
        .chat-container {
            flex: 1;
            display: flex;
            flex-direction: column;
            background-color: var(--card-bg);
            border-radius: var(--border-radius);
            box-shadow: var(--shadow);
            overflow: hidden;
        }
        
        .chat-header {
            background-color: rgba(0, 0, 0, 0.2);
            padding: 15px 20px;
            display: flex;
            align-items: center;
            gap: 10px;
        }
        
        .status-indicator {
            width: 12px;
            height: 12px;
            border-radius: 50%;
            background-color: #4CAF50;
            margin-right: 5px;
        }
        
        .chat-title {
            font-size: 16px;
            font-weight: 600;
            color: var(--primary-color);
        }
        
        .chat-messages {
            flex: 1;
            padding: 20px;
            overflow-y: auto;
            display: flex;
            flex-direction: column;
            gap: 15px;
            max-height: 500px;
        }
        
        .message {
            max-width: 80%;
            padding: 12px 16px;
            border-radius: 18px;
            font-size: 14px;
            position: relative;
            line-height: 1.5;
        }
        
        .user-message {
            background-color: var(--primary-color);
            color: #000;
            align-self: flex-end;
            border-bottom-right-radius: 5px;
        }
        
        .bot-message {
            background-color: rgba(255, 255, 255, 0.1);
            color: var(--text-color);
            align-self: flex-start;
            border-bottom-left-radius: 5px;
        }
        
        .message-time {
            font-size: 10px;
            opacity: 0.7;
            margin-top: 5px;
            text-align: right;
        }
        
        .chat-input-container {
            padding: 15px;
            background-color: rgba(0, 0, 0, 0.2);
            display: flex;
            gap: 10px;
        }
        
        .chat-input {
            flex: 1;
            padding: 12px 15px;
            border-radius: 25px;
            border: none;
            background-color: rgba(255, 255, 255, 0.1);
            color: var(--text-color);
            font-size: 14px;
            outline: none;
            transition: all 0.3s ease;
        }
        
        .chat-input:focus {
            background-color: rgba(255, 255, 255, 0.15);
            box-shadow: 0 0 0 2px rgba(77, 208, 225, 0.3);
        }
        
        .send-button {
            width: 45px;
            height: 45px;
            border-radius: 50%;
            background-color: var(--primary-color);
            border: none;
            cursor: pointer;
            display: flex;
            align-items: center;
            justify-content: center;
            transition: all 0.3s ease;
        }
        
        .send-button:hover {
            background-color: var(--secondary-color);
            transform: scale(1.05);
        }
        
        .send-icon {
            width: 20px;
            height: 20px;
            color: var(--card-bg);
        }
        
        .brain-stats {
            width: 300px;
            background-color: var(--card-bg);
            border-radius: var(--border-radius);
            box-shadow: var(--shadow);
            padding: 20px;
            display: flex;
            flex-direction: column;
            gap: 15px;
        }
        
        .stats-title {
            font-size: 16px;
            font-weight: 600;
            color: var(--primary-color);
            margin-bottom: 10px;
        }
        
        .stats-group {
            display: flex;
            flex-direction: column;
            gap: 10px;
        }
        
        .stat-card {
            background-color: rgba(0, 0, 0, 0.2);
            border-radius: 8px;
            padding: 12px 15px;
        }
        
        .stat-label {
            font-size: 12px;
            color: #aaa;
            margin-bottom: 5px;
        }
        
        .stat-value {
            font-size: 18px;
            font-weight: 600;
            color: var(--text-color);
        }
        
        .brain-wave {
            display: flex;
            justify-content: space-between;
            align-items: center;
            padding: 10px 0;
            border-bottom: 1px solid rgba(255, 255, 255, 0.05);
        }
        
        .brain-wave:last-child {
            border-bottom: none;
        }
        
        .wave-name {
            font-size: 14px;
            display: flex;
            align-items: center;
            gap: 8px;
        }
        
        .wave-indicator {
            width: 10px;
            height: 10px;
            border-radius: 50%;
        }
        
        .wave-value {
            font-size: 16px;
            font-weight: 600;
        }
        
        .delta-color { color: #4fc3f7; background-color: #4fc3f7; }
        .theta-color { color: #4db6ac; background-color: #4db6ac; }
        .alpha-color { color: #aed581; background-color: #aed581; }
        .beta-color { color: #ff8a65; background-color: #ff8a65; }
        .gamma-color { color: #ba68c8; background-color: #ba68c8; }
        
        .suggestion-chips {
            display: flex;
            flex-wrap: wrap;
            gap: 10px;
            margin-top: 15px;
        }
        
        .suggestion-chip {
            background-color: rgba(255, 255, 255, 0.1);
            border-radius: 20px;
            padding: 8px 15px;
            font-size: 13px;
            cursor: pointer;
            transition: all 0.3s ease;
            border: none;
            color: var(--text-color);
        }
        
        .suggestion-chip:hover {
            background-color: var(--highlight);
            color: var(--primary-color);
        }
        
        .loading-indicator {
            display: flex;
            gap: 5px;
            align-items: center;
            margin: 10px 0;
            align-self: center;
        }
        
        .loading-dot {
            width: 8px;
            height: 8px;
            border-radius: 50%;
            background-color: var(--primary-color);
            animation: bounce 1.4s infinite ease-in-out both;
        }
        
        .loading-dot:nth-child(1) { animation-delay: -0.32s; }
        .loading-dot:nth-child(2) { animation-delay: -0.16s; }
        
        @keyframes bounce {
            0%, 80%, 100% { transform: scale(0); }
            40% { transform: scale(1); }
        }
        
        code {
            font-family: 'Courier New', monospace;
            background-color: rgba(0, 0, 0, 0.3);
            padding: 2px 5px;
            border-radius: 4px;
            font-size: 13px;
        }
        
        .markdown {
            line-height: 1.6;
        }
        
        .markdown p {
            margin-bottom: 10px;
        }
        
        .markdown h1, .markdown h2, .markdown h3 {
            margin-top: 16px;
            margin-bottom: 8px;
            color: var(--primary-color);
        }
        
        .markdown ul, .markdown ol {
            margin-left: 20px;
            margin-bottom: 10px;
        }

        .welcome-message {
            background-color: rgba(77, 208, 225, 0.1);
            border-radius: 12px;
            padding: 15px;
            margin-bottom: 15px;
            border-left: 4px solid var(--primary-color);
        }
    </style>
</head>
<body>
    <div class="container">
        <header>
            <h1>EEG Brain Assistant</h1>
            <div class="nav-links">
                <a href="dashboard" class="nav-link">Dashboard</a>
                <a href="#" class="nav-link active">AI Assistant</a>
            </div>
        </header>
        
        <div class="main-content">
            <div class="chat-container">
                <div class="chat-header">
                    <div class="status-indicator"></div>
                    <div class="chat-title">Brain Assistant</div>
                </div>
                <div class="chat-messages" id="chat-messages">
                    <div class="message bot-message">
                        <div class="welcome-message">
                            <strong>Hello!</strong> I'm your EEG Brain Assistant. I can help you understand your brain activity based on your EEG readings. 
                            <br><br>
                            I can provide insights about:
                            <ul>
                                <li>Your current brainwave patterns</li>
                                <li>What your brain activity indicates</li>
                                <li>How your alpha, beta, theta, delta, and gamma waves compare</li>
                                <li>Suggestions based on your current brainwave state</li>
                            </ul>
                        </div>
                        What would you like to know about your brain activity?
                        <div class="message-time">Just now</div>
                    </div>
                </div>
                <div class="suggestion-chips">
                    <button class="suggestion-chip">What does my current brain state mean?</button>
                    <button class="suggestion-chip">Explain my alpha waves</button>
                    <button class="suggestion-chip">Is my brain activity normal?</button>
                    <button class="suggestion-chip">Dominant wave in my EEG?</button>
                    <button class="suggestion-chip">What can I do to improve focus?</button>
                </div>
                <div class="chat-input-container">
                    <input type="text" class="chat-input" id="chat-input" placeholder="Ask me about your brain activity...">
                    <button class="send-button" id="send-button">
                        <svg class="send-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                            <line x1="22" y1="2" x2="11" y2="13"></line>
                            <polygon points="22 2 15 22 11 13 2 9 22 2"></polygon>
                        </svg>
                    </button>
                </div>
            </div>
            
            <div class="brain-stats">
                <div class="stats-title">Real-time Brain Stats</div>
                <div class="stats-group">
                    <div class="stat-card">
                        <div class="stat-label">Signal Mean</div>
                        <div class="stat-value" id="mean-value">0.00 μV</div>
                    </div>
                    <div class="stat-card">
                        <div class="stat-label">Signal Variability</div>
                        <div class="stat-value" id="std-value">0.00 μV</div>
                    </div>
                    <div class="stat-card">
                        <div class="stat-label">Signal Range</div>
                        <div class="stat-value" id="range-value">0.00 μV</div>
                    </div>
                </div>
                
                <div class="stats-title">Brainwave Analysis</div>
                <div class="brain-wave">
                    <div class="wave-name">
                        <span class="wave-indicator delta-color"></span>
                        Delta (0.5-4 Hz)
                    </div>
                    <div class="wave-value delta-color" id="delta-value">0.00</div>
                </div>
                <div class="brain-wave">
                    <div class="wave-name">
                        <span class="wave-indicator theta-color"></span>
                        Theta (4-8 Hz)
                    </div>
                    <div class="wave-value theta-color" id="theta-value">0.00</div>
                </div>
                <div class="brain-wave">
                    <div class="wave-name">
                        <span class="wave-indicator alpha-color"></span>
                        Alpha (8-13 Hz)
                    </div>
                    <div class="wave-value alpha-color" id="alpha-value">0.00</div>
                </div>
                <div class="brain-wave">
                    <div class="wave-name">
                        <span class="wave-indicator beta-color"></span>
                        Beta (13-30 Hz)
                    </div>
                    <div class="wave-value beta-color" id="beta-value">0.00</div>
                </div>
                <div class="brain-wave">
                    <div class="wave-name">
                        <span class="wave-indicator gamma-color"></span>
                        Gamma (30-50 Hz)
                    </div>
                    <div class="wave-value gamma-color" id="gamma-value">0.00</div>
                </div>
            </div>
        </div>
    </div>

    <script>
        // DOM Elements
        const chatMessages = document.getElementById('chat-messages');
        const chatInput = document.getElementById('chat-input');
        const sendButton = document.getElementById('send-button');
        const suggestionChips = document.querySelectorAll('.suggestion-chip');
        
        // State variables
        let eegContext = {
            data: [],
            fft_data: {
                frequencies: [],
                magnitudes: []
            },
            band_powers: {
                delta: 0,
                theta: 0,
                alpha: 0,
                beta: 0,
                gamma: 0
            }
        };
        
        // WebSocket connection
        const ws = new WebSocket(`ws://${window.location.host}/ws/dashboard`);
        
        ws.onopen = () => {
            console.log('Connected to WebSocket server');
        };
        
        ws.onclose = () => {
            console.log('Disconnected from WebSocket server');
            // Try to reconnect after 3 seconds
            setTimeout(() => {
                window.location.reload();
            }, 3000);
        };
        
        ws.onmessage = (event) => {
            const data = JSON.parse(event.data);
            
            if (data.type === 'eeg_data') {
                // Update our EEG context
                eegContext = data;
                
                // Update stats display
                updateStatsDisplay();
            }
        };
        
        // Update stats display
        function updateStatsDisplay() {
            if (eegContext.data && eegContext.data.length > 0) {
                // Calculate statistics
                const mean = eegContext.data.reduce((a, b) => a + b, 0) / eegContext.data.length;
                const variance = eegContext.data.reduce((a, b) => a + Math.pow(b - mean, 2), 0) / eegContext.data.length;
                const std = Math.sqrt(variance);
                const min = Math.min(...eegContext.data);
                const max = Math.max(...eegContext.data);
                
                // Update stats display
                document.getElementById('mean-value').textContent = mean.toFixed(2) + ' μV';
                document.getElementById('std-value').textContent = std.toFixed(2) + ' μV';
                document.getElementById('range-value').textContent = (max - min).toFixed(2) + ' μV';
                
                // Update brainwave values
                document.getElementById('delta-value').textContent = eegContext.band_powers.delta.toFixed(2);
                document.getElementById('theta-value').textContent = eegContext.band_powers.theta.toFixed(2);
                document.getElementById('alpha-value').textContent = eegContext.band_powers.alpha.toFixed(2);
                document.getElementById('beta-value').textContent = eegContext.band_powers.beta.toFixed(2);
                document.getElementById('gamma-value').textContent = eegContext.band_powers.gamma.toFixed(2);
            }
        }
        
        // Function to add a message to the chat
        function addMessage(text, isUser = false) {
            const messageDiv = document.createElement('div');
            messageDiv.className = `message ${isUser ? 'user-message' : 'bot-message'}`;
            
            // If it's a bot message, we'll parse markdown
            if (!isUser) {
                messageDiv.innerHTML = text;
            } else {
                messageDiv.textContent = text;
            }
            
            const timeDiv = document.createElement('div');
            timeDiv.className = 'message-time';
            timeDiv.textContent = 'Just now';
            
            messageDiv.appendChild(timeDiv);
            chatMessages.appendChild(messageDiv);
            
            // Scroll to bottom
            chatMessages.scrollTop = chatMessages.scrollHeight;
        }
        
        // Function to add a loading indicator
        function addLoadingIndicator() {
            const loadingDiv = document.createElement('div');
            loadingDiv.className = 'loading-indicator';
            loadingDiv.innerHTML = `
                <div class="loading-dot"></div>
                <div class="loading-dot"></div>
                <div class="loading-dot"></div>
            `;
            chatMessages.appendChild(loadingDiv);
            chatMessages.scrollTop = chatMessages.scrollHeight;
            return loadingDiv;
        }
        
        // Function to process user message and get AI response
        async function processMessage(message) {
            // Add user message to chat
            addMessage(message, true);
            
            // Add loading indicator
            const loadingIndicator = addLoadingIndicator();
            
            try {
                // Send message to server
                const response = await fetch('/chat', {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json'
                    },
                    body: JSON.stringify({
                        message: message,
                        eeg_context: eegContext
                    })
                });
                
                if (!response.ok) {
                    throw new Error('Network response was not ok');
                }
                
                const data = await response.json();
                
                // Remove loading indicator
                loadingIndicator.remove();
                
                // Add AI response to chat
                addMessage(data.response);
                
            } catch (error) {
                console.error('Error:', error);
                loadingIndicator.remove();
                addMessage('Sorry, I encountered an error processing your request. Please try again.');
            }
        }
        
        // Event listeners
        sendButton.addEventListener('click', () => {
            const message = chatInput.value.trim();
            if (message) {
                processMessage(message);
                chatInput.value = '';
            }
        });
        
        chatInput.addEventListener('keypress', (e) => {
            if (e.key === 'Enter') {
                const message = chatInput.value.trim();
                if (message) {
                    processMessage(message);
                    chatInput.value = '';
                }
            }
        });
        
        // Suggestion chips
        suggestionChips.forEach(chip => {
            chip.addEventListener('click', () => {
                const message = chip.textContent;
                processMessage(message);
            });
        });
        
        // Simulate initial data update
        setTimeout(() => {
            updateStatsDisplay();
        }, 1000);
    </script>
</body>
</html>"""

    return html_content

@app.get("/dashboard", response_class=HTMLResponse)
async def get_dashboard():
    """Serve HTML dashboard with real-time EEG graph"""
    html_content = """
    <!DOCTYPE html>
    <html lang="en">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>Real-time EEG Monitor</title>
        <style>
            body {
                font-family: Arial, sans-serif;
                background-color: #111;
                color: #fff;
                margin: 0;
                padding: 20px;
            }
            .container {
                max-width: 1200px;
                margin: 0 auto;
            }
            .card {
                background-color: #222;
                border-radius: 8px;
                padding: 20px;
                box-shadow: 0 4px 6px rgba(0, 0, 0, 0.1);
                margin-bottom: 20px;
            }
            h1 {
                color: #4dd0e1;
                margin-top: 0;
            }
            .chart-container {
                position: relative;
                height: 400px;
                width: 100%;
                margin-bottom: 20px;
            }
            .stats {
                display: flex;
                flex-wrap: wrap;
                gap: 20px;
                margin-top: 20px;
            }
            .stat-box {
                background-color: #333;
                border-radius: 8px;
                padding: 15px;
                flex: 1;
                min-width: 120px;
            }
            .stat-title {
                font-size: 0.9em;
                color: #aaa;
                margin-bottom: 5px;
            }
            .stat-value {
                font-size: 1.5em;
                font-weight: bold;
                color: #4dd0e1;
            }
            .connection-status {
                padding: 8px 15px;
                border-radius: 20px;
                font-size: 0.9em;
                display: inline-block;
                margin-bottom: 15px;
            }
            .status-connected {
                background-color: #2e7d32;
                color: white;
            }
            .status-disconnected {
                background-color: #c62828;
                color: white;
            }
            .controls {
                display: flex;
                gap: 10px;
                margin-bottom: 15px;
                flex-wrap: wrap;
            }
            .btn {
                background-color: #4dd0e1;
                color: #222;
                border: none;
                border-radius: 4px;
                padding: 8px 15px;
                cursor: pointer;
                font-weight: bold;
                transition: background-color 0.2s;
            }
            .btn:hover {
                background-color: #26c6da;
            }
            .btn.active {
                background-color: #00acc1;
                box-shadow: 0 0 0 2px rgba(77, 208, 225, 0.5);
            }
            .range-control {
                display: flex;
                align-items: center;
                gap: 10px;
                margin-bottom: 15px;
            }
            .range-control label {
                color: #aaa;
                min-width: 120px;
            }
            .range-control input {
                flex: 1;
            }
            .tabs {
                display: flex;
                margin-bottom: 15px;
            }
            .tab {
                padding: 10px 20px;
                background-color: #333;
                border-radius: 8px 8px 0 0;
                cursor: pointer;
                margin-right: 2px;
            }
            .tab.active {
                background-color: #4dd0e1;
                color: #222;
                font-weight: bold;
            }
            .chart-wrapper {
                display: none;
            }
            .chart-wrapper.active {
                display: block;
            }
            .brainwave-bands {
                display: flex;
                flex-wrap: wrap;
                gap: 10px;
                margin-top: 15px;
            }
            .band-box {
                background-color: #333;
                border-radius: 8px;
                padding: 12px;
                flex: 1;
                min-width: 100px;
                text-align: center;
            }
            .band-name {
                font-size: 0.9em;
                color: #aaa;
                margin-bottom: 5px;
            }
            .band-value {
                font-size: 1.3em;
                font-weight: bold;
            }
            .delta { color: #4fc3f7; }
            .theta { color: #4db6ac; }
            .alpha { color: #aed581; }
            .beta { color: #ff8a65; }
            .gamma { color: #ba68c8; }
        </style>
        <script src="https://cdnjs.cloudflare.com/ajax/libs/Chart.js/3.9.1/chart.min.js"></script>
        <script src="https://cdn.jsdelivr.net/npm/hammerjs@2.0.8"></script>
        <script src="https://cdnjs.cloudflare.com/ajax/libs/chartjs-plugin-zoom/2.0.1/chartjs-plugin-zoom.min.js"></script>
    </head>
    <body>
        <div class="container">
            <div class="card">
                <h1>Real-time EEG Signal Monitor</h1>
                <div id="connection-status" class="connection-status status-disconnected">Disconnected</div>
                
                <div class="tabs">
                    <div class="tab active" data-target="eeg-wrapper">EEG Signal</div>
                    <div class="tab" data-target="fft-wrapper">FFT Analysis</div>
                    <div class="tab" data-target="band-wrapper">Brainwave Bands</div>
                </div>
                
                <div id="eeg-wrapper" class="chart-wrapper active">
                    <div class="controls">
                        <button id="btn-reset-zoom" class="btn">Reset Zoom</button>
                        <button id="btn-smooth-toggle" class="btn active">Smoothing On</button>
                        <div class="range-control">
                            <label for="smooth-amount">Smoothing Amount:</label>
                            <input type="range" id="smooth-amount" min="1" max="20" value="5">
                        </div>
                    </div>
                    
                    <div class="chart-container">
                        <canvas id="eegChart"></canvas>
                    </div>
                </div>
                
                <div id="fft-wrapper" class="chart-wrapper">
                    <div class="controls">
                        <button id="btn-reset-zoom-fft" class="btn">Reset Zoom</button>
                    </div>
                    
                    <div class="chart-container">
                        <canvas id="fftChart"></canvas>
                    </div>
                </div>
                
                <div id="band-wrapper" class="chart-wrapper">
                    <div class="chart-container">
                        <canvas id="bandChart"></canvas>
                    </div>
                    
                    <div class="brainwave-bands">
                        <div class="band-box">
                            <div class="band-name">Delta (0.5-4 Hz)</div>
                            <div id="delta-value" class="band-value delta">--</div>
                        </div>
                        <div class="band-box">
                            <div class="band-name">Theta (4-8 Hz)</div>
                            <div id="theta-value" class="band-value theta">--</div>
                        </div>
                        <div class="band-box">
                            <div class="band-name">Alpha (8-13 Hz)</div>
                            <div id="alpha-value" class="band-value alpha">--</div>
                        </div>
                        <div class="band-box">
                            <div class="band-name">Beta (13-30 Hz)</div>
                            <div id="beta-value" class="band-value beta">--</div>
                        </div>
                        <div class="band-box">
                            <div class="band-name">Gamma (30-50 Hz)</div>
                            <div id="gamma-value" class="band-value gamma">--</div>
                        </div>
                    </div>
                </div>
                
                <div class="stats">
                    <div class="stat-box">
                        <div class="stat-title">Mean</div>
                        <div id="mean-value" class="stat-value">--</div>
                    </div>
                    <div class="stat-box">
                        <div class="stat-title">Std Dev</div>
                        <div id="std-value" class="stat-value">--</div>
                    </div>
                    <div class="stat-box">
                        <div class="stat-title">Min</div>
                        <div id="min-value" class="stat-value">--</div>
                    </div>
                    <div class="stat-box">
                        <div class="stat-title">Max</div>
                        <div id="max-value" class="stat-value">--</div>
                    </div>
                    <div class="stat-box">
                        <div class="stat-title">Data Points</div>
                        <div id="data-points" class="stat-value">0</div>
                    </div>
                </div>
            </div>
        </div>

        <script>
            // Establish WebSocket connection
            const ws = new WebSocket(`ws://${window.location.host}/ws/dashboard`);
            const statusElement = document.getElementById('connection-status');
            const ctxEeg = document.getElementById('eegChart').getContext('2d');
            const ctxFft = document.getElementById('fftChart').getContext('2d');
            const ctxBand = document.getElementById('bandChart').getContext('2d');
            
            // Stats elements
            const meanElement = document.getElementById('mean-value');
            const stdElement = document.getElementById('std-value');
            const minElement = document.getElementById('min-value');
            const maxElement = document.getElementById('max-value');
            const dataPointsElement = document.getElementById('data-points');
            
            // Brainwave band elements
            const deltaElement = document.getElementById('delta-value');
            const thetaElement = document.getElementById('theta-value');
            const alphaElement = document.getElementById('alpha-value');
            const betaElement = document.getElementById('beta-value');
            const gammaElement = document.getElementById('gamma-value');
            
            // Control elements
            const resetZoomBtn = document.getElementById('btn-reset-zoom');
            const resetZoomFftBtn = document.getElementById('btn-reset-zoom-fft');
            const smoothToggleBtn = document.getElementById('btn-smooth-toggle');
            const smoothAmountInput = document.getElementById('smooth-amount');
            
            // Tabs
            const tabs = document.querySelectorAll('.tab');
            const chartWrappers = document.querySelectorAll('.chart-wrapper');
            
            // Variables for data processing
            let rawEegData = [];
            let smoothedEegData = [];
            let fftFrequencies = [];
            let fftMagnitudes = [];
            let bandPowers = {
                delta: 0,
                theta: 0,
                alpha: 0,
                beta: 0,
                gamma: 0
            };
            let smoothingEnabled = true;
            let smoothingAmount = parseInt(smoothAmountInput.value);
            
            // Setup EEG Chart.js
            const eegChartConfig = {
                type: 'line',
                data: {
                    labels: [],
                    datasets: [{
                        label: 'EEG Signal',
                        data: [],
                        borderColor: '#00ffff',
                        borderWidth: 1.5,
                        backgroundColor: 'rgba(0, 255, 255, 0.1)',
                        fill: false,
                        tension: 0.2,
                        pointRadius: 0
                    }]
                },
                options: {
                    responsive: true,
                    maintainAspectRatio: false,
                    animation: {
                        duration: 0 // General animation time
                    },
                    scales: {
                        x: {
                            type: 'linear',
                            min: 0,
                            max: 1280,
                            grid: {
                                color: 'rgba(255, 255, 255, 0.1)'
                            },
                            title: {
                                display: true,
                                text: 'Samples',
                                color: '#aaa'
                            }
                        },
                        y: {
                            min: -300,
                            max: 300,
                            grid: {
                                color: 'rgba(255, 255, 255, 0.1)'
                            },
                            title: {
                                display: true,
                                text: 'Amplitude (μV)',
                                color: '#aaa'
                            }
                        }
                    },
                    plugins: {
                        legend: {
                            display: true,
                            labels: {
                                color: '#fff'
                            }
                        },
                        zoom: {
                            pan: {
                                enabled: true,
                                mode: 'xy'
                            },
                            zoom: {
                                wheel: {
                                    enabled: true,
                                },
                                pinch: {
                                    enabled: true
                                },
                                mode: 'xy',
                            }
                        }
                    }
                }
            };
            
            // Setup FFT Chart.js
            const fftChartConfig = {
                type: 'line',
                data: {
                    labels: [],
                    datasets: [{
                        label: 'FFT Spectrum',
                        data: [],
                        borderColor: '#ff9800',
                        borderWidth: 1.5,
                        backgroundColor: 'rgba(255, 152, 0, 0.1)',
                        fill: true,
                        tension: 0.2,
                        pointRadius: 0
                    }]
                },
                options: {
                    responsive: true,
                    maintainAspectRatio: false,
                    animation: {
                        duration: 0
                    },
                    scales: {
                        x: {
                            type: 'linear',
                            min: 0,
                            max: 60, // Show up to 60 Hz
                            grid: {
                                color: 'rgba(255, 255, 255, 0.1)'
                            },
                            title: {
                                display: true,
                                text: 'Frequency (Hz)',
                                color: '#aaa'
                            }
                        },
                        y: {
                            type: 'linear',
                            grid: {
                                color: 'rgba(255, 255, 255, 0.1)'
                            },
                            title: {
                                display: true,
                                text: 'Power',
                                color: '#aaa'
                            }
                        }
                    },
                    plugins: {
                        legend: {
                            display: true,
                            labels: {
                                color: '#fff'
                            }
                        },
                        zoom: {
                            pan: {
                                enabled: true,
                                mode: 'xy'
                            },
                            zoom: {
                                wheel: {
                                    enabled: true,
                                },
                                pinch: {
                                    enabled: true
                                },
                                mode: 'xy',
                            }
                        }
                    }
                }
            };
            
            // Setup Brainwave Band Chart
            const bandChartConfig = {
                type: 'bar',
                data: {
                    labels: ['Delta', 'Theta', 'Alpha', 'Beta', 'Gamma'],
                    datasets: [{
                        label: 'Band Power',
                        data: [0, 0, 0, 0, 0],
                        backgroundColor: [
                            'rgba(79, 195, 247, 0.8)',  // Delta - blue
                            'rgba(77, 182, 172, 0.8)',  // Theta - teal
                            'rgba(174, 213, 129, 0.8)', // Alpha - green
                            'rgba(255, 138, 101, 0.8)', // Beta - orange
                            'rgba(186, 104, 200, 0.8)'  // Gamma - purple
                        ],
                        borderColor: [
                            'rgb(79, 195, 247)',
                            'rgb(77, 182, 172)',
                            'rgb(174, 213, 129)',
                            'rgb(255, 138, 101)',
                            'rgb(186, 104, 200)'
                        ],
                        borderWidth: 1
                    }]
                },
                options: {
                    responsive: true,
                    maintainAspectRatio: false,
                    animation: {
                        duration: 500
                    },
                    scales: {
                        y: {
                            beginAtZero: true,
                            grid: {
                                color: 'rgba(255, 255, 255, 0.1)'
                            },
                            title: {
                                display: true,
                                text: 'Relative Power',
                                color: '#aaa'
                            }
                        },
                        x: {
                            grid: {
                                color: 'rgba(255, 255, 255, 0.1)'
                            }
                        }
                    },
                    plugins: {
                        legend: {
                            display: false
                        }
                    }
                }
            };
            
            // Create charts
            const eegChart = new Chart(ctxEeg, eegChartConfig);
            const fftChart = new Chart(ctxFft, fftChartConfig);
            const bandChart = new Chart(ctxBand, bandChartConfig);
            
            // Helper function to calculate mean
            function calculateMean(data) {
                if (data.length === 0) return 0;
                const sum = data.reduce((a, b) => a + b, 0);
                return sum / data.length;
            }
            
            // Helper function to calculate standard deviation
            function calculateStd(data, mean) {
                if (data.length <= 1) return 0;
                const variance = data.reduce((acc, val) => acc + Math.pow(val - mean, 2), 0) / (data.length - 1);
                return Math.sqrt(variance);
            }
            
            // Helper function to smooth data using moving average
            function smoothData(data, windowSize) {
                if (windowSize <= 1 || data.length < windowSize) {
                    return [...data]; // Return copy of original data
                }
                
                const result = [];
                for (let i = 0; i < data.length; i++) {
                    let sum = 0;
                    let count = 0;
                    
                    // Calculate centered moving average
                    const halfWindow = Math.floor(windowSize / 2);
                    for (let j = -halfWindow; j <= halfWindow; j++) {
                        const index = i + j;
                        if (index >= 0 && index < data.length) {
                            sum += data[index];
                            count++;
                        }
                    }
                    
                    result.push(sum / count);
                }
                
                return result;
            }
            
            // Handle WebSocket events
            ws.onopen = () => {
                statusElement.textContent = 'Connected';
                statusElement.classList.remove('status-disconnected');
                statusElement.classList.add('status-connected');
                console.log('Connected to WebSocket server');
            };
            
            ws.onclose = () => {
                statusElement.textContent = 'Disconnected';
                statusElement.classList.remove('status-connected');
                statusElement.classList.add('status-disconnected');
                console.log('Disconnected from WebSocket server');
                // Try to reconnect after 3 seconds
                setTimeout(() => {
                    window.location.reload();
                }, 3000);
            };
            
            ws.onmessage = (event) => {
                const data = JSON.parse(event.data);
                
                if (data.type === 'eeg_data') {
                    // Update raw data
                    rawEegData = data.data;
                    
                    // Apply smoothing if enabled
                    if (smoothingEnabled) {
                        smoothedEegData = smoothData(rawEegData, smoothingAmount);
                    } else {
                        smoothedEegData = [...rawEegData];
                    }
                    
                    // Update EEG chart
                    const labels = Array.from({length: smoothedEegData.length}, (_, i) => i);
                    eegChart.data.labels = labels;
                    eegChart.data.datasets[0].data = smoothedEegData;
                    
                    // Update chart scales if needed
                    if (smoothedEegData.length > eegChart.options.scales.x.max) {
                        eegChart.options.scales.x.max = smoothedEegData.length;
                    }
                    
                    // Update EEG chart
                    eegChart.update();
                    
                    // Get and update FFT data
                    if (data.fft_data) {
                        fftFrequencies = data.fft_data.frequencies;
                        fftMagnitudes = data.fft_data.magnitudes;
                        
                        // Update FFT chart
                        const fftPoints = fftFrequencies.map((freq, i) => ({
                            x: freq,
                            y: fftMagnitudes[i]
                        }));
                        
                        fftChart.data.datasets[0].data = fftPoints;
                        fftChart.update();
                    }
                    
                    // Update brainwave band powers
                    if (data.band_powers) {
                        bandPowers = data.band_powers;
                        
                        // Update band chart
                        bandChart.data.datasets[0].data = [
                            bandPowers.delta,
                            bandPowers.theta,
                            bandPowers.alpha,
                            bandPowers.beta,
                            bandPowers.gamma
                        ];
                        bandChart.update();
                        
                        // Update band value displays
                        deltaElement.textContent = bandPowers.delta.toFixed(2);
                        thetaElement.textContent = bandPowers.theta.toFixed(2);
                        alphaElement.textContent = bandPowers.alpha.toFixed(2);
                        betaElement.textContent = bandPowers.beta.toFixed(2);
                        gammaElement.textContent = bandPowers.gamma.toFixed(2);
                    }
                    
                    // Calculate and update statistics
                    if (rawEegData.length > 0) {
                        const mean = calculateMean(rawEegData);
                        const std = calculateStd(rawEegData, mean);
                        const min = Math.min(...rawEegData);
                        const max = Math.max(...rawEegData);
                        
                        meanElement.textContent = mean.toFixed(2);
                        stdElement.textContent = std.toFixed(2);
                        minElement.textContent = min.toFixed(2);
                        maxElement.textContent = max.toFixed(2);
                        dataPointsElement.textContent = rawEegData.length;
                    }
                }
            };
            
            ws.onerror = (error) => {
                console.error('WebSocket error:', error);
                statusElement.textContent = 'Error: ' + error;
            };
            
            // Event listeners for controls
            resetZoomBtn.addEventListener('click', () => {
                eegChart.resetZoom();
            });
            
            resetZoomFftBtn.addEventListener('click', () => {
                fftChart.resetZoom();
            });
            
            smoothToggleBtn.addEventListener('click', () => {
                smoothingEnabled = !smoothingEnabled;
                smoothToggleBtn.textContent = smoothingEnabled ? 'Smoothing On' : 'Smoothing Off';
                smoothToggleBtn.classList.toggle('active', smoothingEnabled);
                
                // Update chart with smoothed/raw data
                if (smoothingEnabled) {
                    smoothedEegData = smoothData(rawEegData, smoothingAmount);
                } else {
                    smoothedEegData = [...rawEegData];
                }
                
                eegChart.data.datasets[0].data = smoothedEegData;
                eegChart.update();
            });
            
            smoothAmountInput.addEventListener('input', () => {
                smoothingAmount = parseInt(smoothAmountInput.value);
                if (smoothingEnabled && rawEegData.length > 0) {
                    smoothedEegData = smoothData(rawEegData, smoothingAmount);
                    eegChart.data.datasets[0].data = smoothedEegData;
                    eegChart.update();
                }
            });
            
            // Tab switching
            tabs.forEach(tab => {
                tab.addEventListener('click', () => {
                    // Remove active class from all tabs and wrappers
                    tabs.forEach(t => t.classList.remove('active'));
                    chartWrappers.forEach(w => w.classList.remove('active'));
                    
                    // Add active class to clicked tab
                    tab.classList.add('active');
                    
                    // Show corresponding wrapper
                    const targetId = tab.getAttribute('data-target');
                    document.getElementById(targetId).classList.add('active');
                });
            });
        </script>
    </body>
    </html>
    """
    return html_content


@app.post("/esp_32/data")
async def receive_esp32_data(request: Request):
    try:
        data = await request.json()
        logger.info(f"Received data from ESP32: {data}")
        return {"status": "success", "received": data}
    except Exception as e:
        logger.error(f"Failed to process ESP32 data: {e}")
        raise HTTPException(status_code=400, detail="Invalid JSON or saving error.")

@app.websocket("/ws/esp32")
async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()
    print("ESP32 connected via WebSocket")

    try:
        while True:
            data = await websocket.receive_json()
            print(data)
            eeg_value = data.get("eeg")
            
            if eeg_value is not None:
                try:
                    eeg_buffer.append(float(eeg_value))
                    # Broadcast data to all dashboard clients
                    await broadcast_eeg_data()
                except ValueError:
                    print("Non-numeric EEG value received.")
    except WebSocketDisconnect:
        print("ESP32 disconnected")
    except Exception as e:
        print(f"WebSocket error: {e}")

@app.websocket("/ws/dashboard")
async def dashboard_websocket(websocket: WebSocket):
    await websocket.accept()
    connected_clients.append(websocket)
    print(f"Dashboard client connected. Total clients: {len(connected_clients)}")
    
    try:
        # Send initial data
        if eeg_buffer:
            eeg_data = list(eeg_buffer)
            # Calculate FFT and band powers
            freq_bins, magnitudes = calculate_fft(eeg_data)
            band_powers = calculate_band_powers(freq_bins, magnitudes)
            
            await websocket.send_json({
                "type": "eeg_data",
                "data": eeg_data,
                "fft_data": {
                    "frequencies": freq_bins,
                    "magnitudes": magnitudes
                },
                "band_powers": band_powers
            })
        
        # Keep connection alive
        while True:
            # Just waiting for potential client messages or disconnection
            await websocket.receive_text()
    except WebSocketDisconnect:
        connected_clients.remove(websocket)
        print(f"Dashboard client disconnected. Total clients: {len(connected_clients)}")
    except Exception as e:
        if websocket in connected_clients:
            connected_clients.remove(websocket)
        print(f"Dashboard WebSocket error: {e}")

async def broadcast_eeg_data():
    """Send EEG data to all connected dashboard clients"""
    if connected_clients:
        # Convert deque to list for JSON serialization
        eeg_data = list(eeg_buffer)
        
        # Calculate FFT and band powers
        freq_bins, magnitudes = calculate_fft(eeg_data)
        band_powers = calculate_band_powers(freq_bins, magnitudes)
        
        # message = {
        #     "type": "eeg_data",
        #     "data": eeg_data,
        #     "fft_data": {
        #         "frequencies": freq_bins,
        #         "magnitudes": magnitudes
        #     },
        #     "band_powers": band_powers
        # }
        
        global eeg_context
        eeg_context = {
            "type": "eeg_data",
            "data": eeg_data,
            "fft_data": {
                "frequencies": freq_bins,
                "magnitudes": magnitudes
            },
            "band_powers": band_powers
        }
        
        # Broadcast to all connected clients
        for client in connected_clients.copy():
            try:
                await client.send_json(eeg_context)
            except Exception as e:
                print(f"Error sending to client: {e}")
                # Remove problematic clients
                if client in connected_clients:
                    connected_clients.remove(client)
                    
          
if __name__ == "__main__":
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=False)