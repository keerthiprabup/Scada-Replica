from flask import Flask, render_template, request, jsonify
import subprocess
import os
import threading
import time

app = Flask(__name__)

ATTACK_SCRIPTS_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "attack_scripts")

import json

# Store running processes and current network state
running_attacks = {}
current_network = None
lock = threading.Lock()

def connect_network(network_name):
    global current_network
    try:
        hostname = os.environ.get("HOSTNAME", "attacker_dashboard")
        subprocess.run(["docker", "network", "connect", network_name, hostname], check=True)
        print(f"Connected {hostname} to {network_name}")
        current_network = network_name
        return True
    except Exception as e:
        print(f"Failed to connect to network: {e}")
        return False

def disconnect_network():
    global current_network
    if not current_network: return
    try:
        hostname = os.environ.get("HOSTNAME", "attacker_dashboard")
        subprocess.run(["docker", "network", "disconnect", current_network, hostname], check=True)
        print(f"Disconnected {hostname} from {current_network}")
        current_network = None
    except Exception as e:
        print(f"Failed to disconnect from network: {e}")

@app.route("/")
def index():
    return render_template("index.html")

@app.route("/api/networks")
def get_networks():
    try:
        output = subprocess.check_output(["docker", "network", "ls", "--format", "{{.Name}}"], text=True)
        networks = [line.strip() for line in output.split('\n') if line.strip()]
        return jsonify(networks)
    except:
        return jsonify(["br-xyb", "bridge"])

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

@app.route("/api/attack/<attack_type>", methods=["POST"])
def start_attack(attack_type):
    data = request.json
    
    with lock:
        if attack_type in running_attacks:
            return jsonify({"success": False, "message": "Attack already running."})
        
        target_network = data.get("network", "br-xyb")
        
        # Connect to SCADA network if not already connected
        if current_network != target_network:
            if current_network:
                disconnect_network()
            connect_network(target_network)
        
        cmd = []
        if attack_type == "command_injection":
            script = os.path.join(ATTACK_SCRIPTS_DIR, "command_injection.py")
            val = 1 if data.get("value") else 0
            cmd = ["python", script, "--target", data.get("ip"), "--port", str(data.get("port")), 
                   "--unit", str(data.get("unit")), "write-coil", str(data.get("coil")), str(val)]
        elif attack_type == "dos_flood":
            script = os.path.join(ATTACK_SCRIPTS_DIR, "dos_flood.py")
            cmd = ["python", script, "--target", data.get("ip"), "--port", str(data.get("port")), 
                   "--threads", str(data.get("threads", 50))]
        elif attack_type == "replay_attack":
            script = os.path.join(ATTACK_SCRIPTS_DIR, "replay_attack.py")
            cmd = ["python", script, "--target", data.get("ip"), "--port", str(data.get("port")), 
                   "--unit", str(data.get("unit")), "--address", str(data.get("address"))]
        elif attack_type == "false_data_injection":
            script = os.path.join(ATTACK_SCRIPTS_DIR, "command_injection.py")
            cmd = ["python", script, "--target", data.get("ip"), "--port", str(data.get("port")), 
                   "--unit", str(data.get("unit")), "write-reg", str(data.get("address")), 
                   str(data.get("value"))]
        else:
            return jsonify({"success": False, "message": "Unknown attack type."})
            
        try:
            # We don't wait for completion here, we let it run in background
            proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
            running_attacks[attack_type] = proc
            
            # For one-shot attacks like command injection and FDI, they complete quickly.
            # We will start a thread to reap them so they don't stay "running" forever.
            if attack_type in ["command_injection", "false_data_injection"]:
                def reap_process(atype, p):
                    p.wait()
                    with lock:
                        if atype in running_attacks and running_attacks[atype] == p:
                            del running_attacks[atype]
                            if len(running_attacks) == 0:
                                disconnect_network()
                threading.Thread(target=reap_process, args=(attack_type, proc)).start()
                
            return jsonify({"success": True, "message": f"Started {attack_type}"})
        except Exception as e:
            disconnect_network()
            return jsonify({"success": False, "message": str(e)})

@app.route("/api/attack/<attack_type>/stop", methods=["POST"])
def stop_attack(attack_type):
    with lock:
        proc = running_attacks.get(attack_type)
        if proc:
            proc.terminate()
            proc.wait()
            del running_attacks[attack_type]
            
            # Disconnect if no attacks are running
            if len(running_attacks) == 0:
                disconnect_network()
                
            return jsonify({"success": True, "message": f"Stopped {attack_type}"})
        return jsonify({"success": False, "message": "Attack not running."})

@app.route("/api/attack/<attack_type>/status")
def attack_status(attack_type):
    with lock:
        proc = running_attacks.get(attack_type)
        if proc:
            if proc.poll() is None:
                return jsonify({"running": True})
            else:
                del running_attacks[attack_type]
                if len(running_attacks) == 0:
                    disconnect_network()
                return jsonify({"running": False})
        return jsonify({"running": False})

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)
