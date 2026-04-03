"""
2.4 GHz Spectrum Analyzer for nRF52840

Real-time spectrum analyzer with optional Peak Hold function.
Visualizes RSSI across the 2.4 GHz band received from nRF52840 via serial.
"""

import serial
import numpy as np
import threading
import time
import argparse
from queue import Queue, Empty
import matplotlib
import matplotlib.pyplot as plt
import sys


# ====================== SCRIPT INFORMATION ======================
print("=== 2.4 GHz Spectrum Analyzer Starting ===")
print(f"Python version: {sys.version}")
print(f"Matplotlib version: {matplotlib.__version__}")
print(f"Matplotlib backend: {matplotlib.get_backend()}")
print("=" * 60 + "\n")


# ====================== COMMAND LINE ARGUMENTS ======================
parser = argparse.ArgumentParser(
    description="2.4 GHz Spectrum Analyzer for nRF52840",
    formatter_class=argparse.ArgumentDefaultsHelpFormatter
)

parser.add_argument('--port', type=str, default='COM1',
                    help='Serial port name (e.g. COM1, /dev/ttyACM0)')
parser.add_argument('--baud', type=int, default=921600,
                    help='Baud rate')
parser.add_argument('--channels', type=int, default=81,
                    help='Number of frequency channels')
parser.add_argument('--no-log', dest='log', action='store_false',
                    help='Disable verbose console logging')
parser.add_argument('--no-peak-hold', dest='peak_hold', action='store_false',
                    help='Disable Peak Hold (maximum) curve')
parser.set_defaults(peak_hold=True)

args = parser.parse_args()

# Configuration
SERIAL_PORT = args.port
BAUD_RATE = args.baud
NUM_CHANNELS = args.channels
SHOW_CONSOLE_LOG = args.log
ENABLE_PEAK_HOLD = args.peak_hold

print(f"Starting with settings:")
print(f"   Port          = {SERIAL_PORT}")
print(f"   Channels      = {NUM_CHANNELS}")
print(f"   Verbose log   = {'ON' if SHOW_CONSOLE_LOG else 'OFF'}")
print(f"   Peak Hold     = {'ON' if ENABLE_PEAK_HOLD else 'OFF'}")


# ====================== DATA ARRAYS ======================
frequencies = np.arange(2400, 2400 + NUM_CHANNELS, dtype=float)

latest_rssi = np.full(NUM_CHANNELS, -100.0)   # Current RSSI values
max_rssi = np.full(NUM_CHANNELS, -110.0)     # Peak hold values (only used if enabled)

data_queue = Queue(maxsize=10)


# ====================== SERIAL COMMUNICATION ======================
def connect_serial():
    """Establish connection to the serial port."""
    print("Connecting to serial port...")
    while True:
        try:
            if ser.is_open:
                ser.close()
            ser.open()
            ser.reset_input_buffer()
            print(f"Successfully connected to {SERIAL_PORT}")
            return
        except Exception as e:
            print(f"Failed to connect: {e}")
            time.sleep(3)


def read_serial():
    """Background thread for reading serial data."""
    global header_read
    print("Serial reading thread started")
    packet_count = 0

    while True:
        try:
            if not ser.is_open:
                print("Serial port closed, attempting to reconnect...")
                time.sleep(2)
                connect_serial()
                continue

            line_raw = ser.readline()
            if not line_raw:
                continue

            text = line_raw.decode('utf-8', errors='replace').rstrip()
            if not text:
                continue

            if not header_read and "2400" in text:
                header_read = True
                print("Header received — starting spectrum reception")
                if SHOW_CONSOLE_LOG:
                    print(f"   Header: {text}")
                continue

            if ':' in text and text.split(':', 1)[0].isdigit():
                packet_count += 1
                if SHOW_CONSOLE_LOG:
                    print(f"Packet #{packet_count}: {text}")

                parts = text.split(':', 1)
                if len(parts) == 2:
                    values = parts[1].strip().split()
                    if len(values) == NUM_CHANNELS:
                        try:
                            rssi_array = np.array([-float(v) for v in values], dtype=float)
                            data_queue.put_nowait(rssi_array)
                            if packet_count % 10 == 0:
                                print(f"RSSI data queued (packet #{packet_count})")
                        except ValueError as e:
                            print(f"RSSI conversion error: {e}")
        except Exception as e:
            print(f"Serial read error: {e}")
            time.sleep(1)


# ====================== PLOTTING SETUP ======================
print("Initializing matplotlib...")
plt.ion()

fig, ax = plt.subplots(figsize=(13, 7))

ax.set_title("2.4 GHz Spectrum Analyzer (nRF52840)")
ax.set_xlabel("Frequency (MHz)")
ax.set_ylabel("RSSI (dBm)")

ax.set_xlim(2400, 2480)
ax.set_ylim(-110, -10)

ax.grid(True, alpha=0.5)
ax.set_axisbelow(True)

# Current RSSI line (bright cyan)
line, = ax.plot(frequencies, latest_rssi, lw=3.0, color='#00FFFF',
                label='Current RSSI', zorder=3)

# Peak Hold line (light blue) — created only if enabled
if ENABLE_PEAK_HOLD:
    max_line, = ax.plot(frequencies, max_rssi, lw=2.0, color='#FCEAD9',
                        label='Peak Hold (Max)', alpha=0.85, zorder=2)
    print("Peak Hold curve enabled (light blue)")
else:
    max_line = None
    print("Peak Hold curve disabled")

ax.legend(loc='upper right', fontsize=11)
plt.tight_layout()


# ====================== MAIN PROGRAM ======================
ser = serial.Serial()
ser.port = SERIAL_PORT
ser.baudrate = BAUD_RATE
ser.timeout = 2

header_read = False

connect_serial()

# Start serial reading thread
thread = threading.Thread(target=read_serial, daemon=True)
thread.start()

print("Spectrum analyzer is running. Waiting for data...\n")

update_count = 0
last_update_time = time.time()

try:
    while True:
        updated = False

        try:
            while True:
                new_rssi = data_queue.get_nowait()
                latest_rssi[:] = new_rssi
                
                # Update peak hold only if the feature is enabled
                if ENABLE_PEAK_HOLD:
                    max_rssi[:] = np.maximum(max_rssi, new_rssi)
                
                updated = True
        except Empty:
            pass

        if updated:
            update_count += 1
            now = time.time()
            fps = 1.0 / (now - last_update_time) if (now - last_update_time) > 0.001 else 0
            last_update_time = now

            if update_count % 5 == 0:
                print(f"Update #{update_count} | FPS ≈ {fps:.1f}")

            # Update plot lines
            line.set_ydata(latest_rssi)
            if ENABLE_PEAK_HOLD and max_line is not None:
                max_line.set_ydata(max_rssi)

            fig.canvas.draw()
            fig.canvas.flush_events()
            plt.pause(0.008)

        else:
            fig.canvas.flush_events()
            time.sleep(0.001)

except KeyboardInterrupt:
    print("\nStopped by user (Ctrl+C)")
except Exception as e:
    print(f"Critical error: {e}")
finally:
    if ser.is_open:
        ser.close()
    plt.close('all')
    print("Program terminated.")