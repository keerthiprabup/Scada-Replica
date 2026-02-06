from flask import Flask, jsonify, request, render_template
from flask_cors import CORS
from pymodbus.client import ModbusTcpClient
import threading
import time
import json
import os
import datetime

# ---------------- CONFIGURATION ----------------
RTU_CONFIG_FILE = "rtu_config.json"
LOG_FILE = "/app/scada_events.json"

# Default RTUs
DEFAULT_RTUS = {
    "SUBSTATION": {"ip": os.getenv("SUBSTATION_IP", "127.0.0.1"), "port": 5002, "unit": 1},
    "FEEDER":     {"ip": os.getenv("FEEDER_IP", "127.0.0.1"), "port": 5003, "unit": 2},
}

# Add Home RTUs from Env
home_ips = os.getenv("HOME_IPS", "home").split(",")
for i, ip_addr in enumerate(home_ips):
    DEFAULT_RTUS[f"HOME_{i+1}"] = {"ip": ip_addr, "port": 5004, "unit": 3 + i}

# Global State
SYSTEM_STATE = {
    "timestamp": None,
    "rtus": {}
}

RTUS = {}

app = Flask(__name__)
CORS(app)

# ---------------- HELPER FUNCTIONS ----------------
def load_rtu_config():
    global RTUS
    if os.path.exists(RTU_CONFIG_FILE):
        try:
            with open(RTU_CONFIG_FILE, 'r') as f:
                RTUS = json.load(f)
            print("Loaded RTU config from file.")
        except Exception as e:
            print(f"Error loading config, using defaults: {e}")
            RTUS = DEFAULT_RTUS.copy()
    else:
        RTUS = DEFAULT_RTUS.copy()
        save_rtu_config()

def save_rtu_config():
    try:
        with open(RTU_CONFIG_FILE, 'w') as f:
            json.dump(RTUS, f, indent=4)
    except Exception as e:
        print(f"Error saving config: {e}")

# ---------------- MODBUS CLIENTS ----------------
clients = {}
lock = threading.Lock()

def get_client(name):
    cfg = RTUS.get(name)
    if not cfg: return None, None
    key = f"{cfg['ip']}:{cfg['port']}"
    if key not in clients:
        try:
            clients[key] = ModbusTcpClient(cfg["ip"], port=int(cfg["port"]))
        except Exception as e:
            print(f"Failed to create client for {name}: {e}")
            return None, None
            
    return clients[key], cfg["unit"]

def read_holding(client, unit, start, count):
    if not client: return None
    try:
        if not client.connected: client.connect()
        rr = client.read_holding_registers(start, count=count, slave=unit)
        return rr.registers if rr and not rr.isError() else None
    except Exception as e:
        print(f"Modbus Read Error: {e}")
        return None

def read_coils(client, unit, start, count):
    if not client: return None
    try:
        if not client.connected: client.connect()
        rr = client.read_coils(start, count=count, slave=unit)
        return rr.bits if rr and not rr.isError() else None
    except Exception as e:
        print(f"Modbus Read Coil Error: {e}")
        return None

def write_coil_cmd(rtu_name, coil_addr, value):
    try:
        with lock:
            c, unit = get_client(rtu_name)
            if not c: return False
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
        
        # Make a copy of keys to avoid runtime error if RTUS changes during iteration
        current_rtus = list(RTUS.keys())

        with lock:
            for name in current_rtus:
                c, u = get_client(name)
                if not c:
                    snapshot[name] = {"status": "OFFLINE"}
                    continue
                
                # Dynamic Logic based on naming convention or config type
                # For simplicity, we try to detect type by name or unit, but falling back to standard reads
                # We will read a standard block that covers most needs: 10 HRs and 10 Coils
                try:
                    hr = read_holding(c, u, 0, 10)
                    co = read_coils(c, u, 0, 10)
                    
                    if hr and co:
                        # Parse based on known types
                        data = {}
                        if name == "SUBSTATION":
                            data = {
                                "exported_mw": hr[0]/10.0,
                                "gen_output": hr[1]/10.0,
                                "gen_temp": hr[3],
                                "gcb_closed": co[0],
                                "overload": co[2] or co[3]
                            }
                        elif name == "FEEDER":
                            data = {
                                "load_pct": hr[0],
                                "voltage": hr[1],
                                "current": hr[2],
                                "power_kw": hr[4]/10.0,
                                "breaker_closed": co[0],
                                "overload_alarm": co[2],
                                "upstream_ok": co[3]
                            }
                        elif name.startswith("HOME"):
                            data = {
                                "load_w": hr[0],
                                "voltage": hr[1],
                                "current": hr[2]/10.0,
                                "energy_kwh": hr[3]/10.0,
                                "supply_on": co[0],
                                "trip": co[1]
                            }
                        else:
                            # Generic Raw Data for custom RTUs
                            data = {
                                "registers": hr,
                                "coils": co
                            }
                        
                        snapshot[name] = data
                    else:
                         snapshot[name] = {"status": "TIMEOUT"}
                except Exception as e:
                    snapshot[name] = {"status": "ERROR", "msg": str(e)}

        # Update Global State
        SYSTEM_STATE["timestamp"] = timestamp
        SYSTEM_STATE["rtus"] = snapshot

        # Log to JSON File (Append mode)
        log_entry = json.dumps({"timestamp": timestamp, "data": snapshot})
        try:
            # Check file size to prevent infinite growth (optional simple log rotation logic)
            if os.path.exists(LOG_FILE) and os.path.getsize(LOG_FILE) > 5 * 1024 * 1024: # 5MB
                 os.replace(LOG_FILE, LOG_FILE + ".bak")
                 
            with open(LOG_FILE, "a") as f:
                f.write(log_entry + "\n")
        except Exception as e:
            print(f"Log Error: {e}")
        
        time.sleep(2) # Faster polling for HMI responsiveness

# ---------------- API ROUTES ----------------
@app.route("/")
def index():
    return render_template("index.html")

@app.route("/api/status")
def status():
    return jsonify(SYSTEM_STATE)

@app.route("/api/rtu", methods=["POST"])
def add_rtu():
    data = request.json
    name = data.get("name")
    ip = data.get("ip")
    port = data.get("port")
    unit = data.get("unit")
    
    if not all([name, ip, port, unit]):
        return jsonify({"error": "Missing fields"}), 400
        
    with lock:
        RTUS[name] = {"ip": ip, "port": int(port), "unit": int(unit)}
        save_rtu_config()
        
    return jsonify({"success": True, "message": f"RTU {name} added"})

@app.route("/api/rtu", methods=["DELETE"])
def remove_rtu():
    name = request.args.get("name")
    if not name: return jsonify({"error": "Missing name"}), 400
    
    with lock:
        if name in RTUS:
            del RTUS[name]
            save_rtu_config()
            return jsonify({"success": True, "message": f"RTU {name} removed"})
        else:
            return jsonify({"error": "RTU not found"}), 404

@app.route("/api/history")
def history():
    # Return last N lines of logs
    limit = int(request.args.get("limit", 100))
    data = []
    try:
        if os.path.exists(LOG_FILE):
            with open(LOG_FILE, "r") as f:
                # Naive tail implementation
                lines = f.readlines()
                for line in lines[-limit:]:
                    try:
                        data.append(json.loads(line))
                    except:
                        pass
    except Exception as e:
        print(f"History Read Error: {e}")
        return jsonify([])
        
    return jsonify(data)

@app.route("/api/control", methods=["POST"])
def control():
    """
    Enhanced Control Endpoint
    {
        "target": "FEEDER",
        "type": "COIL" | "REGISTER",
        "address": 0,
        "value": 1
    }
    Legacy support: "action": "OPEN" mapped automatically
    """
    data = request.json
    target = data.get("target")
    
    # Legacy Support
    if "action" in data:
        action = data.get("action")
        coil_val = None
        coil_addr = 0 # Default assumption
        
        if target == "FEEDER":
            if action == "OPEN": coil_val = False
            elif action == "CLOSE": coil_val = True
        elif target == "SUBSTATION":
            if action == "CLOSE": coil_val = True; coil_addr = 0
            elif action == "OPEN": coil_val = True; coil_addr = 1
        elif target and target.startswith("HOME"):
             if action == "ON": coil_val = True
             elif action == "OFF": coil_val = False

        if coil_val is not None:
             success = write_coil_cmd(target, coil_addr, coil_val)
             return jsonify({"success": success})

    # New Generic Support
    ctrl_type = data.get("type")
    addr = data.get("address")
    val = data.get("value")
    
    if ctrl_type == "COIL":
        success = write_coil_cmd(target, int(addr), bool(val))
        return jsonify({"success": success})
    
    # TODO: Implement Register Write if needed
    
    return jsonify({"success": False, "error": "Invalid command"})

if __name__ == "__main__":
    load_rtu_config()
    
    # Start Poller
    t = threading.Thread(target=poll_rtus, daemon=True)
    t.start()
    
    # Start Web Server
    app.run(host="0.0.0.0", port=5000)
