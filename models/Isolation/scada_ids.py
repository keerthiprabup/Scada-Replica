import pyshark
import joblib
import numpy as np
import json
import logging
import time
import requests
from datetime import datetime

import argparse

# -------------------- CONFIG --------------------
parser = argparse.ArgumentParser(description="SCADA IDS")
parser.add_argument("--interface", default="br-xyb", help="Network interface to sniff on")
args = parser.parse_args()

INTERFACE = args.interface
MODEL_PATH = "isolation_forest_model.joblib"
SCALER_PATH = "scaler.joblib"
REPORT_FILE = "anomaly_report.json"
LIVE_SCORES_FILE = "live_scores.json"
LOG_FILE = "ids.log"
MAINTENANCE_SERVER_URL = "http://localhost:5050/api/isolate"

# -------------------- LOGGING --------------------
logging.basicConfig(
    filename=LOG_FILE,
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s"
)

print("[+] Loading model and scaler...")
try:
    model = joblib.load(MODEL_PATH)
    scaler = joblib.load(SCALER_PATH)
except Exception as e:
    print(f"Warning: Could not load model/scaler (run training script first). {e}")
    model = None
    scaler = None

# -------------------- HELPERS --------------------
def safe_int(value, default=0):
    try:
        return int(value)
    except:
        return default

def safe_float(value, default=0.0):
    try:
        return float(value)
    except:
        return default

def encode_ip(ip):
    return hash(ip) % 10000

# -------------------- FEATURE EXTRACTION --------------------
def extract_features(packet, prev_time):
    try:
        if not hasattr(packet, 'ip') or not hasattr(packet, 'tcp'):
            return None, prev_time

        timestamp = float(packet.sniff_timestamp)
        src_ip = packet.ip.src
        dst_ip = packet.ip.dst
        src_port = safe_int(packet.tcp.srcport)
        dst_port = safe_int(packet.tcp.dstport)
        pkt_len = safe_int(packet.length)
        ttl = safe_int(packet.ip.ttl)
        tcp_len = safe_int(getattr(packet.tcp, 'len', 0))
        window = safe_int(getattr(packet.tcp, 'window_size', 0))

        if prev_time is None:
            time_delta = 0
        else:
            time_delta = timestamp - prev_time

        pkt_rate = 1 / (time_delta + 1e-6)
        port_diff = src_port - dst_port

        features = [
            pkt_len, src_port, dst_port, tcp_len, ttl, window,
            time_delta, pkt_rate, encode_ip(src_ip), encode_ip(dst_ip), port_diff
        ]

        return features, timestamp

    except Exception as e:
        logging.warning(f"Feature extraction error: {e}")
        return None, prev_time

# -------------------- REPORT & TRIGGER --------------------
def handle_anomaly(packet, score):
    try:
        report = {
            "timestamp": str(datetime.now()),
            "src_ip": getattr(packet.ip, "src", "N/A"),
            "dst_ip": getattr(packet.ip, "dst", "N/A"),
            "anomaly_score": float(score),
        }

        with open(REPORT_FILE, "w") as f:
            json.dump(report, f, indent=4)

        logging.critical(f"ANOMALY DETECTED: {report}")
        print("\n[🚨] ANOMALY DETECTED!")
        print(json.dumps(report, indent=4))
        
        # Trigger Physical Isolation
        print(f"[>] Sending isolation command to Maintenance Dashboard: {MAINTENANCE_SERVER_URL}")
        try:
            resp = requests.post(MAINTENANCE_SERVER_URL, timeout=5)
            if resp.status_code == 200:
                print("[+] Isolation successful. System is in manual mode.")
            else:
                print(f"[-] Maintenance Server returned {resp.status_code}.")
        except Exception as e:
            print(f"[-] Failed to reach Maintenance Server: {e}")

    except Exception as e:
        logging.error(f"Report generation failed: {e}")

# -------------------- MAIN LOOP --------------------
def start_ids():
    if not model or not scaler:
         print("[!] Model missing. Exiting.")
         return
         
    print(f"[+] Starting live capture on {INTERFACE} ...")
    logging.info("IDS started")

    try:
         capture = pyshark.LiveCapture(interface=INTERFACE)
    except Exception as e:
         print(f"[-] Failed to bind interface '{INTERFACE}'. Make sure npcap/libpcap is installed.")
         print(e)
         return

    prev_time = None
    score_history = []

    for packet in capture.sniff_continuously():
        features, prev_time = extract_features(packet, prev_time)

        if features is None:
            continue

        try:
            X = scaler.transform([features])
            pred = model.predict(X)
            score = float(model.decision_function(X)[0])
            
            # Log live scores for dashboard graph
            timestamp_str = datetime.now().strftime("%H:%M:%S")
            score_history.append({"time": timestamp_str, "score": score})
            if len(score_history) > 60:
                score_history.pop(0)
                
            try:
                with open(LIVE_SCORES_FILE, "w") as f:
                    json.dump(score_history, f)
            except Exception as e:
                pass # Don't let file write errors stop the IDS

            # 🚨 ANOMALY DETECTED
            if pred[0] == -1:
                handle_anomaly(packet, score)
                break  # STOP EXECUTION

        except Exception as e:
            logging.error(f"Inference error: {e}")

    print("[!] IDS stopped due to anomaly.")

# -------------------- ENTRY --------------------
if __name__ == "__main__":
    try:
        start_ids()
    except KeyboardInterrupt:
        print("\n[!] IDS manually stopped.")
        logging.info("IDS stopped manually")
