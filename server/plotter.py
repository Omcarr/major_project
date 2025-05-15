import matplotlib.pyplot as plt
import matplotlib.animation as animation
from collections import deque
import socket
import json

# Connect to server that streams EEG (via localhost UDP socket or any IPC you use)
eeg_buffer = deque(maxlen=1280)

def get_data_from_stream():
    # Example using UDP socket (replace this with your own logic)
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.bind(("0.0.0.0", 9000))
    while True:
        data, _ = sock.recvfrom(1024)
        try:
            eeg = json.loads(data.decode()).get("eeg")
            if eeg is not None:
                eeg_buffer.append(float(eeg))
        except Exception:
            continue

import threading
threading.Thread(target=get_data_from_stream, daemon=True).start()

plt.style.use('ggplot')
fig, ax = plt.subplots()
line, = ax.plot([], [], lw=1)
ax.set_ylim(-300, 300)
ax.set_xlim(0, 1280)
ax.set_title("Real-time EEG Plot")
ax.set_xlabel("Samples")
ax.set_ylabel("Amplitude")

def update(frame):
    y_data = list(eeg_buffer)
    x_data = list(range(len(y_data)))
    line.set_data(x_data, y_data)
    ax.set_xlim(max(0, len(y_data) - 1280), len(y_data))
    return line,

ani = animation.FuncAnimation(fig, update, interval=50, blit=True)
plt.tight_layout()
plt.show()
