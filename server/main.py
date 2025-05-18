from fastapi import FastAPI, Request, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from fastapi.staticfiles import StaticFiles
import uvicorn
import logging
from collections import deque
from utlis import calculate_band_powers, calculate_fft

#logger setup
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

#global context for EEG data
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