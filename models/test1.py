import pyshark
import joblib
import numpy as np
import json
import logging
import time
from datetime import datetime

# -------------------- CONFIG --------------------
INTERFACE = "br-fbc6827e824c"  # Replace with dnet3 bridge (ip a)
MODEL_PATH = "isolation_forest_model.joblib"
SCALER_PATH = "scaler.joblib"
REPORT_FILE = "anomaly_report.json"
LOG_FILE = "ids.log"

# -------------------- LOGGING --------------------
logging.basicConfig(
    filename=LOG_FILE,
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s"
)

print("[+] Loading model and scaler...")
model = joblib.load(MODEL_PATH)
scaler = joblib.load(SCALER_PATH)

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
    """Avoid LabelEncoder issue using hashing"""
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

        # Time delta
        if prev_time is None:
            time_delta = 0
        else:
            time_delta = timestamp - prev_time

        pkt_rate = 1 / (time_delta + 1e-6)
        port_diff = src_port - dst_port

        features = [
            pkt_len,
            src_port,
            dst_port,
            tcp_len,
            ttl,
            window,
            time_delta,
            pkt_rate,
            encode_ip(src_ip),
            encode_ip(dst_ip),
            port_diff
        ]

        return features, timestamp

    except Exception as e:
        logging.warning(f"Feature extraction error: {e}")
        return None, prev_time

# -------------------- REPORT --------------------
def generate_report(packet, score):
    try:
        report = {
            "timestamp": str(datetime.now()),
            "src_ip": getattr(packet.ip, "src", "N/A"),
            "dst_ip": getattr(packet.ip, "dst", "N/A"),
            "src_port": getattr(packet.tcp, "srcport", "N/A"),
            "dst_port": getattr(packet.tcp, "dstport", "N/A"),
            "packet_length": getattr(packet, "length", "N/A"),
            "anomaly_score": float(score),
        }

        with open(REPORT_FILE, "w") as f:
            json.dump(report, f, indent=4)

        logging.critical(f"ANOMALY DETECTED: {report}")
        print("\nANOMALY DETECTED — SYSTEM STOPPED")
        print(json.dumps(report, indent=4))

    except Exception as e:
        logging.error(f"Report generation failed: {e}")

# -------------------- MAIN LOOP --------------------
def start_ids():
    print(f"[+] Starting live capture on {INTERFACE} ...")
    logging.info("IDS started")

    capture = pyshark.LiveCapture(interface=INTERFACE)

    prev_time = None

    for packet in capture.sniff_continuously():
        features, prev_time = extract_features(packet, prev_time)

        if features is None:
            continue

        try:
            X = scaler.transform([features])
            pred = model.predict(X)
            score = model.decision_function(X)

            logging.info(f"Packet processed | Score: {score[0]}")

            # 🚨 ANOMALY DETECTED
            if pred[0] == -1:
                generate_report(packet, score[0])
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