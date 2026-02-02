from flask import Flask, jsonify, request, render_template
from flask_cors import CORS
from pymodbus.client import ModbusTcpClient
import threading
import time
import json
import os
import datetime

# ---------------- CONFIGURATION ----------------
# RTU Config
RTUS = {
    "SUBSTATION": {"ip": os.getenv("SUBSTATION_IP", "127.0.0.1"), "port": 5002, "unit": 1},
    "FEEDER":     {"ip": os.getenv("FEEDER_IP", "127.0.0.1"), "port": 5003, "unit": 2},
}

# Add Home RTUs
home_ips = os.getenv("HOME_IPS", "home").split(",")
for i, ip_addr in enumerate(home_ips):
    RTUS[f"HOME_{i+1}"] = {"ip": ip_addr, "port": 5004, "unit": 3 + i} # Unit 3, 4, 5...

LOG_FILE = "/app/scada_events.json"

# Global State
SYSTEM_STATE = {
    "timestamp": None,
    "rtus": {}
}

app = Flask(__name__)
CORS(app)

# ---------------- MODBUS CLIENTS ----------------
clients = {}
lock = threading.Lock()

def get_client(name):
    cfg = RTUS.get(name)
    if not cfg: return None
    key = f"{cfg['ip']}:{cfg['port']}"
    if key not in clients:
        clients[key] = ModbusTcpClient(cfg["ip"], port=cfg["port"])
    return clients[key], cfg["unit"]

def read_holding(client, unit, start, count):
    if not client.connected: client.connect()
    rr = client.read_holding_registers(start, count=count, slave=unit)
    return rr.registers if rr and not rr.isError() else None

def read_coils(client, unit, start, count):
    if not client.connected: client.connect()
    rr = client.read_coils(start, count=count, slave=unit)
    return rr.bits if rr and not rr.isError() else None

def write_coil_cmd(rtu_name, coil_addr, value):
    try:
        with lock:
            c, unit = get_client(rtu_name)
            if not c.connected: c.connect()
            c.write_coil(coil_addr, value, slave=unit)
            return True
    except Exception as e:
        print(f"Error writing coil {rtu_name}: {e}")
        return False

# ---------------- POLLING LOOP ----------------
def poll_rtus():
    while True:
        snapshot = {}
        timestamp = datetime.datetime.utcnow().isoformat() + "Z"
        
        with lock:
            # 1. Substation
            c, u = get_client("SUBSTATION")
            hr = read_holding(c, u, 0, 6)
            co = read_coils(c, u, 0, 5)
            if hr and co:
                snapshot["SUBSTATION"] = {
                    "exported_mw": hr[0]/10.0,
                    "gen_output": hr[1]/10.0,
                    "gen_temp": hr[3],
                    "gcb_closed": co[0],
                    "overload": co[2] or co[3]
                }

            # 2. Feeder
            c, u = get_client("FEEDER")
            hr = read_holding(c, u, 0, 5)
            co = read_coils(c, u, 0, 4)
            if hr and co:
                snapshot["FEEDER"] = {
                    "load_pct": hr[0],
                    "voltage": hr[1],
                    "current": hr[2],
                    "power_kw": hr[4]/10.0,
                    "breaker_closed": co[0],
                    "overload_alarm": co[2],
                    "upstream_ok": co[3]
                }

            # 3. Homes
            for name in RTUS:
                if name.startswith("HOME"):
                    c, u = get_client(name)
                    hr = read_holding(c, u, 0, 5)
                    co = read_coils(c, u, 0, 3)
                    if hr and co:
                        snapshot[name] = {
                            "load_w": hr[0],
                            "voltage": hr[1],
                            "current": hr[2]/10.0,
                            "energy_kwh": hr[3]/10.0,
                            "supply_on": co[0],
                            "trip": co[1]
                        }
        
        # Update Global State
        SYSTEM_STATE["timestamp"] = timestamp
        SYSTEM_STATE["rtus"] = snapshot

        # Log to JSON File (Append mode)
        log_entry = json.dumps({"timestamp": timestamp, "data": snapshot})
        try:
            with open(LOG_FILE, "a") as f:
                f.write(log_entry + "\n")
        except Exception as e:
            print(f"Log Error: {e}")

        # Console Output (Simplified)
        print(f"\n[SCADA POLL] {timestamp}")
        # print(json.dumps(snapshot, indent=2))
        
        time.sleep(3)

# ---------------- API ROUTES ----------------
@app.route("/")
def index():
    return render_template("index.html")

@app.route("/api/status")
def status():
    return jsonify(SYSTEM_STATE)

@app.route("/api/control", methods=["POST"])
def control():
    data = request.json
    target = data.get("target") # e.g. FEEDER
    action = data.get("action") # OPEN, CLOSE, RESET
    
    mapping = {
        "SUBSTATION": {"OPEN": (1, True), "CLOSE": (0, True), "RESET": (2, True)}, # Coil 0=Close, 1=Open
        "FEEDER":     {"OPEN": (0, False), "CLOSE": (0, True), "RESET": (0, True)}, # Feeder Logic: 0=BreakerStatus (Write True to Close)
    }
    
    # Simple logic for now
    if target == "FEEDER":
        if action == "OPEN":
            success = write_coil_cmd("FEEDER", 0, False) # Coil 0 = Breaker Cmd
        elif action == "CLOSE":
            success = write_coil_cmd("FEEDER", 0, True)
        else:
            success = False
    elif target.startswith("HOME"):
        if action == "ON":
            success = write_coil_cmd(target, 0, True)
        elif action == "OFF":
             success = write_coil_cmd(target, 0, False)
        else:
             success = False
    else:
        success = False

    return jsonify({"success": success})

if __name__ == "__main__":
    # Start Poller
    t = threading.Thread(target=poll_rtus, daemon=True)
    t.start()
    
    # Start Web Server
    app.run(host="0.0.0.0", port=5000)
