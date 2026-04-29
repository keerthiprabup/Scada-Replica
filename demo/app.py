from flask import Flask, jsonify, request, render_template
from flask_cors import CORS
from pymodbus.client import ModbusTcpClient
import threading
import time
import json
import os
import datetime
import subprocess

app = Flask(__name__)
CORS(app)

# ---------------- CONFIGURATION ----------------
ISOLATION_MODE = False
IDS_PROCESS = None
IDS_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "ids")

RTU_CONFIG_FILE = "demo_rtu_config.json"
LOG_FILE = "demo_scada_events.json"

DEFAULT_RTUS = {
    "SUBSTATION": {"ip": os.getenv("SUBSTATION_IP", "127.0.0.1"), "port": 5002, "unit": 1},
    "FEEDER":     {"ip": os.getenv("FEEDER_IP", "127.0.0.1"), "port": 5003, "unit": 2},
}

home_ips = os.getenv("HOME_IPS", "127.0.0.1").split(",")
for i, ip_addr in enumerate(home_ips):
    DEFAULT_RTUS[f"HOME_{i+1}"] = {"ip": ip_addr, "port": 5004, "unit": 3 + i}

SYSTEM_STATE = {
    "timestamp": None,
    "rtus": {}
}

RTUS = DEFAULT_RTUS.copy()
clients = {}
lock = threading.Lock()

# ---------------- MODBUS & SCADA POLLING ----------------
def get_client(name):
    cfg = RTUS.get(name)
    if not cfg: return None, None
    key = f"{cfg['ip']}:{cfg['port']}"
    if key not in clients:
        try:
            clients[key] = ModbusTcpClient(cfg["ip"], port=int(cfg["port"]))
        except Exception:
            return None, None
    return clients[key], cfg["unit"]

def read_holding(client, unit, start, count):
    if not client: return None
    try:
        if not client.connected: client.connect()
        rr = client.read_holding_registers(start, count=count, slave=unit)
        return rr.registers if rr and not rr.isError() else None
    except:
        return None

def read_coils(client, unit, start, count):
    if not client: return None
    try:
        if not client.connected: client.connect()
        rr = client.read_coils(start, count=count, slave=unit)
        return rr.bits if rr and not rr.isError() else None
    except:
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

def poll_rtus():
    while True:
        snapshot = {}
        timestamp = datetime.datetime.utcnow().isoformat() + "Z"
        current_rtus = list(RTUS.keys())

        with lock:
            for name in current_rtus:
                c, u = get_client(name)
                if not c:
                    snapshot[name] = {"status": "OFFLINE"}
                    continue
                
                try:
                    hr = read_holding(c, u, 0, 10)
                    co = read_coils(c, u, 0, 10)
                    
                    if hr and co:
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
                        snapshot[name] = data
                    else:
                         snapshot[name] = {"status": "TIMEOUT"}
                except Exception as e:
                    snapshot[name] = {"status": "ERROR", "msg": str(e)}

        SYSTEM_STATE["timestamp"] = timestamp
        SYSTEM_STATE["rtus"] = snapshot
        time.sleep(2)

# ---------------- ISOLATION & IDS LOGIC ----------------
def execute_isolation():
    global ISOLATION_MODE
    ISOLATION_MODE = True
    print("[!] Isolation triggered! Stopping SCADA Containers...")
    script_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "stop_scada.sh")
    try:
        subprocess.Popen(["sh", script_path])
    except Exception as e:
        subprocess.Popen(["docker", "stop", "substation", "feeder", "home", "home2", "home3", "scada", "controller"])

# ---------------- API ROUTES ----------------
@app.route("/")
def index():
    return render_template("index.html")

@app.route("/api/status")
def status():
    return jsonify({
        "scada": SYSTEM_STATE,
        "isolation": {
            "isolated": ISOLATION_MODE,
            "message": "MANUAL OPERATING MODE" if ISOLATION_MODE else "System Normal"
        }
    })

@app.route("/api/control", methods=["POST"])
def control():
    data = request.json
    target = data.get("target")
    ctrl_type = data.get("type", "COIL")
    addr = data.get("address", 0)
    val = data.get("value", False)
    
    if ctrl_type == "COIL":
        success = write_coil_cmd(target, int(addr), bool(val))
        return jsonify({"success": success})
    
    return jsonify({"success": False})

@app.route("/api/isolate", methods=["POST"])
def isolate_system():
    if not request.json or request.json.get("password") != "userxyz":
        return jsonify({"success": False, "message": "Invalid password"}), 401
    global ISOLATION_MODE
    if not ISOLATION_MODE:
        threading.Thread(target=execute_isolation).start()
    return jsonify({"success": True})

@app.route("/api/unisolate", methods=["POST"])
def unisolate_system():
    if not request.json or request.json.get("password") != "userxyz":
        return jsonify({"success": False, "message": "Invalid password"}), 401
    global ISOLATION_MODE
    ISOLATION_MODE = False
    print("[!] Recovering system...")
    script_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "start_scada.sh")
    try:
        subprocess.Popen(["sh", script_path])
    except Exception:
        subprocess.Popen(["docker", "start", "substation", "feeder", "home", "home2", "home3", "scada", "controller"])
    return jsonify({"success": True})

@app.route("/api/interfaces")
def get_interfaces_api():
    try:
        import psutil, socket
        result = []
        stats = psutil.net_if_addrs()
        for interface_name, addrs in stats.items():
            ip = None
            for addr in addrs:
                if addr.family == socket.AF_INET:
                    ip = addr.address
                    break
            result.append({"name": interface_name, "ip": ip})
        return jsonify(result)
    except ImportError:
        try:
            output = subprocess.check_output(["powershell", "-NoProfile", "-Command", "(Get-NetAdapter).Name"], text=True)
            return jsonify([{"name": line.strip(), "ip": None} for line in output.split('\n') if line.strip()])
        except Exception:
            return jsonify([{"name": "br-xyb", "ip": None}])

@app.route("/api/containers")
def get_containers():
    network_name = request.args.get("network", "br-xyb")
    try:
        output = subprocess.check_output(["docker", "network", "inspect", network_name], text=True)
        net_info = json.loads(output)
        containers = net_info[0].get("Containers", {})
        result = [{"name": d.get("Name"), "ip": d.get("IPv4Address", "").split("/")[0]} for d in containers.values()]
        return jsonify(result)
    except:
        return jsonify([])

@app.route("/api/ids/mode", methods=["POST"])
def set_ids_mode():
    data = request.json
    mode = data.get("mode") # "ON" or "OFF"
    interface = data.get("interface", "br-xyb")
    
    global IDS_PROCESS
    
    if mode == "OFF":
        if IDS_PROCESS is not None and IDS_PROCESS.poll() is None:
            IDS_PROCESS.terminate()
            IDS_PROCESS.wait()
    elif mode == "ON":
        if IDS_PROCESS is None or IDS_PROCESS.poll() is not None:
            script_path = os.path.join(IDS_DIR, "scada_ids.py")
            try:
                IDS_PROCESS = subprocess.Popen(["python", script_path, "--interface", interface], cwd=IDS_DIR)
            except Exception as e:
                pass
                
    return jsonify({"success": True, "mode": mode, "interface": interface})

@app.route("/api/ids/logs")
def ids_logs():
    scores_file = os.path.join(IDS_DIR, "live_scores.json")
    breach_file = os.path.join(IDS_DIR, "anomaly_history.json")
    scores = []
    breaches = []
    if os.path.exists(scores_file):
        try:
            with open(scores_file, "r") as f:
                scores = json.load(f)
        except: pass
    if os.path.exists(breach_file):
        try:
            with open(breach_file, "r") as f:
                breaches = json.load(f)
        except: pass
    
    # Auto-isolate logic mock:
    # If the latest breach is NOT a Generic Traffic Anomaly, and we are not isolated, trigger it.
    if breaches and not ISOLATION_MODE:
        latest = breaches[-1]
        if "Generic Traffic Anomaly" not in latest.get("classification", ""):
            execute_isolation()
            
    return jsonify({"scores": scores, "breaches": breaches})

if __name__ == "__main__":
    t = threading.Thread(target=poll_rtus, daemon=True)
    t.start()
    app.run(host="0.0.0.0", port=5051)
