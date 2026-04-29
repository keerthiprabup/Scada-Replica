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
WHITELIST_PATH = "whitelist_ips.json"
REPORT_FILE = "anomaly_report.json"
HISTORY_FILE = "anomaly_history.json"
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
    with open(WHITELIST_PATH, "r") as f:
        whitelist = json.load(f)
except Exception as e:
    print(f"Warning: Could not load model/scaler/whitelist. {e}")
    model = None
    scaler = None
    whitelist = []

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

SCADA_PORTS = {80, 443, 502, 5000, 5002, 5003, 5004}
def mask_port(p):
    if p in SCADA_PORTS: return p
    return 99999 if p > 1024 else p

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
            pkt_len, mask_port(src_port), mask_port(dst_port), tcp_len, ttl, window,
            time_delta, pkt_rate, port_diff
        ]

        return features, timestamp

    except Exception as e:
        logging.warning(f"Feature extraction error: {e}")
        return None, prev_time

# -------------------- REPORT & TRIGGER --------------------
def pre_filter_hybrid(packet, src_in_wl, dst_in_wl):
    src_port = safe_int(getattr(packet.tcp, 'srcport', 0))
    dst_port = safe_int(getattr(packet.tcp, 'dstport', 0))
    tcp_len = safe_int(getattr(packet.tcp, 'len', 0))
    
    standard_ports = [5000, 5002, 5003, 5004, 80, 443]
    violations = []

    if dst_in_wl and not src_in_wl:
        # External IP hitting our SCADA server
        if dst_port in standard_ports and tcp_len>0:
            violations.append(f"Unauthorized Inbound Access to SCADA Port ({dst_port})")
        if dst_port in [5002, 5003, 5004] and tcp_len > 0:
            violations.append("Malicious RTU Command Injection")
            
    elif src_in_wl and not dst_in_wl:
        # Our SCADA server talking to an External IP
        if src_port in standard_ports and tcp_len>0:
            violations.append(f"Unauthorized Outbound Data from SCADA Port ({src_port})")
        if src_port in [5002, 5003, 5004] and tcp_len > 0:
            violations.append("Malicious RTU Command Injection (Data Exfiltration)")

    return violations

def classify_attack(features, packet):
    # features: [pkt_len, src_port, dst_port, tcp_len, ttl, window, time_delta, pkt_rate, port_diff]
    pkt_len = features[0]
    dst_port = features[2]
    tcp_len = features[3]
    ttl = features[4]
    window = features[5]
    pkt_rate = features[7]

    reasons = []
    
    if pkt_rate > 500:
        reasons.append("DoS / High-Rate Traffic Flooding")
    if pkt_len > 1500:
        reasons.append("Large Payload / Buffer Overflow Attempt")
        
    standard_ports = [5000, 5002, 5003, 5004, 80, 443]
    # mask_port maps unknown upper ports to 99999
    if dst_port not in standard_ports and dst_port > 0:
        reasons.append(f"traffic on unusual port ({dst_port})")
        
    if dst_port in [5002, 5003, 5004] and tcp_len > 0:
        reasons.append("Malicious RTU Command Injection")
        
    if ttl < 30 or ttl > 128:
        reasons.append("Suspicious TTL / Possible IP Spoofing")
        
    if window == 0 and dst_port in standard_ports:
        reasons.append("TCP Window Exhaustion Attack")

    if not reasons:
        reasons.append("Generic Traffic Anomaly")

    return reasons

def handle_anomaly(packet, score, features, custom_reason=None):
    try:
        report = {
            "timestamp": str(datetime.now()),
            "src_ip": getattr(packet.ip, "src", "N/A"),
            "dst_ip": getattr(packet.ip, "dst", "N/A"),
            "src_port": features[1],
            "dst_port": features[2],
            "length": features[0],
            "tcp_len": features[3],
            "ttl": features[4],
            "packet_rate": features[7],
            "anomaly_score": float(score),
            "classification": " | ".join(custom_reason) if custom_reason else (" | ".join(classify_attack(features, packet)) or "Generic Traffic Anomaly")
        }

        with open(REPORT_FILE, "w") as f:
            json.dump(report, f, indent=4)
            
        import os
        history = []
        if os.path.exists(HISTORY_FILE):
            try:
                with open(HISTORY_FILE, "r") as f:
                    history = json.load(f)
            except:
                pass
        
        # Keep last 500 breaches so file doesn't grow infinitely
        history.append(report)
        history = history[-500:]
        
        with open(HISTORY_FILE, "w") as f:
            json.dump(history, f, indent=4)

        logging.critical(f"ANOMALY DETECTED: {report}")
        print("\n[🚨] ANOMALY DETECTED!")
        print(json.dumps(report, indent=4))
        
        # Trigger Auto-Isolation or Unisolation based on Classification
        payload = {"password": "userxyz"}
        if "Generic Traffic Anomaly" in report["classification"]:
            target_url = "http://localhost:5050/api/unisolate"
            print("[>] Generic Anomaly detected. Sending UNISOLATE command to Maintenance Dashboard...")
        else:
            target_url = "http://localhost:5050/api/isolate"
            print("[>] Severe Anomaly detected. Sending ISOLATE command to Maintenance Dashboard...")
            
        try:
            resp = requests.post(target_url, json=payload, timeout=5)
            if resp.status_code == 200:
                print(f"[+] Command successful: {resp.json().get('message', 'OK')}")
            else:
                print(f"[-] Maintenance Server returned {resp.status_code}.")
        except Exception as e:
            print(f"[-] Failed to reach Maintenance Server: {e}")
            
        # Send Telegram Report via Maintenance Dashboard
        print("[>] Forwarding anomaly report to Telegram via Maintenance Dashboard...")
        try:
            requests.post("http://localhost:5050/api/telegram_report", json=report, timeout=5)
        except Exception as e:
            print(f"[-] Failed to forward report to Telegram: {e}")

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
            src_ip = getattr(packet.ip, "src", "N/A")
            dst_ip = getattr(packet.ip, "dst", "N/A")

            src_in_wl = src_ip in whitelist
            dst_in_wl = dst_ip in whitelist

            # Dual-Layer Default Routing
            if not src_in_wl and not dst_in_wl:
                # Discard external meaningless noise not targeting topological nodes
                continue
            
            if (not src_in_wl and dst_in_wl) or (not dst_in_wl and src_in_wl):
                # Unseen user hitting topology. Strictly enforce rule-based pre-filter heuristic first
                heuristic_violations = pre_filter_hybrid(packet, src_in_wl, dst_in_wl)
                if len(heuristic_violations) > 0:
                    handle_anomaly(packet, -1.0, features, custom_reason=heuristic_violations)
                    break
            
            # Sub-dimensional ML profile execution (Both Authorized OR Passed Firewall Heuristics)
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

            # 🚨 ANOMALY DETECTED BY ML 
            if pred[0] == -1:
                # If heuristic didn't catch it, fallback to default analysis strings
                handle_anomaly(packet, score, features)
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
