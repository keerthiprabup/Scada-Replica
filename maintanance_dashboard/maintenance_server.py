from flask import Flask, jsonify, render_template
from flask_cors import CORS
import requests
import subprocess
import os
import threading
import json
try:
    import psutil
except ImportError:
    psutil = None

app = Flask(__name__)
CORS(app)

ISOLATION_MODE = False
IDS_PROCESS = None
IDS_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "models", "Isolation")

@app.route("/")
def index():
    return render_template("index.html")

@app.route("/api/isolation_status")
def isolation_status():
    return jsonify({
        "isolated": ISOLATION_MODE,
        "message": "Electrical system is under manual mode" if ISOLATION_MODE else "System Normal"
    })

def execute_isolation():
    global ISOLATION_MODE
    ISOLATION_MODE = True
    print("[!] Isolation triggered! Stopping SCADA Containers...")
    script_path = "stop_scada.sh"
    try:
        # Since it's Windows, we might want to just run the docker stop command directly instead of relying on sh
        # But we'll try running the script first using sh (e.g. Git Bash)
        subprocess.Popen(["sh", script_path])
        print("[+] stop_scada.sh executed.")
    except Exception as e:
        print(f"Failed to execute sh {script_path}. Attempting direct docker stop...")
        try:
            subprocess.Popen(["docker", "stop", "substation", "feeder", "home", "home2", "home3", "scada", "controller"])
            print("[+] Direct docker stop executed.")
        except Exception as ex:
             print(f"Failed direct docker stop: {ex}")

@app.route("/api/isolate", methods=["POST"])
def isolate_system():
    global ISOLATION_MODE
    if not ISOLATION_MODE:
        # Run isolation in a background thread so we don't block the response
        threading.Thread(target=execute_isolation).start()
    return jsonify({"success": True, "isolated": True, "message": "Electrical system is under manual mode"})


@app.route("/api/unisolate", methods=["POST"])
def unisolate_system():
    global ISOLATION_MODE
    ISOLATION_MODE = False
    print("[!] Recovering system from isolation...")
    script_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "start_scada.sh")
    try:
        subprocess.Popen(["sh", script_path])
        print("[+] start_scada.sh executed.")
    except Exception as e:
        print(f"Failed to execute sh {script_path}. Attempting direct docker start...")
        try:
            subprocess.Popen(["docker", "start", "substation", "feeder", "home", "home2", "home3", "scada", "controller"])
            print("[+] Direct docker start executed.")
        except Exception as ex:
             print(f"Failed direct docker start. Please manually run 'docker start substation feeder home home2 home3 scada controller': {ex}")
    
    return jsonify({"success": True, "isolated": False, "message": "System Recovered"})

@app.route("/api/interfaces")
def get_interfaces_api():
    if psutil:
        return jsonify(list(psutil.net_if_addrs().keys()))
    else:
        try:
            output = subprocess.check_output(["powershell", "-NoProfile", "-Command", "(Get-NetAdapter).Name"], text=True)
            return jsonify([line.strip() for line in output.split('\n') if line.strip()])
        except Exception:
            return jsonify(["br-xyb", "Ethernet", "Wi-Fi"])

@app.route("/api/ids/start", methods=["POST"])
def start_ids():
    from flask import request
    global IDS_PROCESS
    if IDS_PROCESS is not None and IDS_PROCESS.poll() is None:
        return jsonify({"success": False, "message": "IDS is already running"})
    
    interface = request.json.get("interface", "br-xyb")
    script_path = os.path.join(IDS_DIR, "scada_ids.py")
    
    try:
        IDS_PROCESS = subprocess.Popen(["python", script_path, "--interface", interface], cwd=IDS_DIR)
        return jsonify({"success": True, "message": f"IDS started on {interface}"})
    except Exception as e:
        return jsonify({"success": False, "message": str(e)})

@app.route("/api/ids/stop", methods=["POST"])
def stop_ids():
    global IDS_PROCESS
    if IDS_PROCESS is not None and IDS_PROCESS.poll() is None:
        IDS_PROCESS.terminate()
        IDS_PROCESS.wait()  # Optional, let it terminate
        return jsonify({"success": True, "message": "IDS stopped"})
    return jsonify({"success": False, "message": "IDS not running"})

@app.route("/api/ids/status")
def ids_status():
    running = IDS_PROCESS is not None and IDS_PROCESS.poll() is None
    return jsonify({"running": running})

@app.route("/api/ids/logs")
def ids_logs():
    log_file = os.path.join(IDS_DIR, "ids.log")
    scores_file = os.path.join(IDS_DIR, "live_scores.json")
    
    logs = ""
    scores = []
    
    if os.path.exists(log_file):
        try:
            with open(log_file, "r") as f:
                lines = f.readlines()
                logs = "".join(lines[-50:])
        except Exception:
            logs = "Error reading log file."
            
    if os.path.exists(scores_file):
        try:
            with open(scores_file, "r") as f:
                scores = json.load(f)
        except Exception:
            pass
            
    return jsonify({"logs": logs, "scores": scores})

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5050)
