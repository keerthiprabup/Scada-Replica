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

try:
    import telebot
    from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton
except ImportError:
    telebot = None

try:
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
except ImportError:
    plt = None

try:
    from pymodbus.client import ModbusTcpClient
except ImportError:
    ModbusTcpClient = None

import io

TELEGRAM_BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "")
ADMIN_CHAT_ID = os.environ.get("ADMIN_CHAT_ID", "")

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
    from flask import request
    if not request.json or request.json.get("password") != "userxyz":
        return jsonify({"success": False, "message": "Invalid password"}), 401
        
    global ISOLATION_MODE
    if not ISOLATION_MODE:
        # Run isolation in a background thread so we don't block the response
        threading.Thread(target=execute_isolation).start()
    return jsonify({"success": True, "isolated": True, "message": "Electrical system is under manual mode"})


def execute_unisolation():
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

@app.route("/api/unisolate", methods=["POST"])
def unisolate_system():
    from flask import request
    if not request.json or request.json.get("password") != "userxyz":
        return jsonify({"success": False, "message": "Invalid password"}), 401
    
    execute_unisolation()
    return jsonify({"success": True, "isolated": False, "message": "System Recovered"})

@app.route("/api/interfaces")
def get_interfaces_api():
    if psutil:
        import socket
        result = []
        stats = psutil.net_if_addrs()
        for interface_name, addrs in stats.items():
            ip = None
            for addr in addrs:
                if addr.family == socket.AF_INET:
                    ip = addr.address
                    break
            if ip:
                result.append({"name": interface_name, "ip": ip})
            else:
                result.append({"name": interface_name, "ip": None})
        return jsonify(result)
    else:
        try:
            output = subprocess.check_output(["powershell", "-NoProfile", "-Command", "(Get-NetAdapter).Name"], text=True)
            return jsonify([{"name": line.strip(), "ip": None} for line in output.split('\n') if line.strip()])
        except Exception:
            return jsonify([{"name": "br-xyb", "ip": None}])

@app.route("/api/containers")
def get_containers():
    try:
        import subprocess, json
        output = subprocess.check_output(["docker", "network", "inspect", "br-xyb"], text=True)
        net_info = json.loads(output)
        containers = net_info[0].get("Containers", {})
        result = []
        for cid, details in containers.items():
            result.append({"name": details.get("Name"), "ip": details.get("IPv4Address", "").split("/")[0]})
        return jsonify(result)
    except Exception:
        return jsonify([])

@app.route("/api/ids/start", methods=["POST"])
def start_ids():
    from flask import request
    if request.json.get("password") != "userxyz":
        return jsonify({"success": False, "message": "Invalid password"}), 401
    
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
    from flask import request
    if request.json.get("password") != "userxyz":
        return jsonify({"success": False, "message": "Invalid password"}), 401
        
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

@app.route("/api/verify_password", methods=["POST"])
def verify_password():
    from flask import request
    if request.json.get("password") == "userxyz":
        return jsonify({"success": True})
    return jsonify({"success": False, "message": "Invalid password"}), 401

@app.route("/api/anomaly_report", methods=["GET"])
def anomaly_report():
    import json
    report_file = os.path.join(IDS_DIR, "anomaly_report.json")
    if os.path.exists(report_file):
        try:
            with open(report_file, "r") as f:
                return jsonify(json.load(f))
        except:
            return jsonify({"error": "Failed to read report"}), 500
    return jsonify({"error": "No report found"}), 404

@app.route("/api/breach_history", methods=["GET"])
def breach_history():
    import json
    report_file = os.path.join(IDS_DIR, "anomaly_history.json")
    if os.path.exists(report_file):
        try:
            with open(report_file, "r") as f:
                return jsonify(json.load(f))
        except:
            return jsonify([])
    return jsonify([])

DEFAULT_RTUS = {
    "SUBSTATION": {"ip": os.getenv("SUBSTATION_IP", "127.0.0.1"), "port": 5002, "unit": 1},
    "FEEDER":     {"ip": os.getenv("FEEDER_IP", "127.0.0.1"), "port": 5003, "unit": 2},
    "HOME":       {"ip": "127.0.0.1", "port": 5004, "unit": 3}
}

def get_scada_status():
    if not ModbusTcpClient: return "pymodbus not installed.", None
    status_text = ""
    plot_data = {"names": [], "powers": []}
    
    for name, cfg in DEFAULT_RTUS.items():
        try:
            client = ModbusTcpClient(cfg["ip"], port=int(cfg["port"]))
            if client.connect():
                hr = client.read_holding_registers(0, count=10, slave=cfg["unit"])
                co = client.read_coils(0, count=10, slave=cfg["unit"])
                
                if not hr.isError() and not co.isError():
                    if name == "SUBSTATION":
                        exported_mw = hr.registers[0]/10.0
                        status_text += f"🏭 *{name}*\n└ Exported: {exported_mw} MW\n"
                        plot_data["names"].append("SUB")
                        plot_data["powers"].append(exported_mw * 1000)
                    elif name == "FEEDER":
                        power_kw = hr.registers[4]/10.0
                        status_text += f"⚡ *{name}*\n└ {hr.registers[1]}V | {power_kw} kW | Breaker: {'ON' if co.bits[0] else 'OFF'}\n"
                        plot_data["names"].append("FEED")
                        plot_data["powers"].append(power_kw)
                    elif name.startswith("HOME"):
                        load_w = hr.registers[0]
                        status_text += f"🏠 *{name}*\n└ {hr.registers[1]}V | {load_w} W | Supply: {'ON' if co.bits[0] else 'OFF'}\n"
                        plot_data["names"].append("HOME")
                        plot_data["powers"].append(load_w / 1000.0)
                else:
                    status_text += f"❌ *{name}*: Modbus Error\n"
            else:
                status_text += f"🔴 *{name}*: Offline\n"
            client.close()
        except Exception as e:
            status_text += f"⚠️ *{name}*: Error\n"
    
    return status_text, plot_data

bot = None
if telebot and TELEGRAM_BOT_TOKEN:
    bot = telebot.TeleBot(TELEGRAM_BOT_TOKEN)

    def main_menu():
        markup = InlineKeyboardMarkup(row_width=2)
        markup.add(
            InlineKeyboardButton("📊 SCADA Status", callback_data="status"),
            InlineKeyboardButton("📈 Value Graph", callback_data="graph"),
            InlineKeyboardButton("📜 Last 10 Reports", callback_data="reports"),
            InlineKeyboardButton("ℹ️ System State", callback_data="system_state"),
            InlineKeyboardButton("▶️ Start IDS", callback_data="start_ids_menu"),
            InlineKeyboardButton("⏹️ Stop IDS", callback_data="stop_ids"),
            InlineKeyboardButton("🔒 Isolate", callback_data="isolate"),
            InlineKeyboardButton("🔓 Unisolate", callback_data="unisolate")
        )
        return markup

    @bot.message_handler(commands=['start', 'menu'])
    def send_welcome(message):
        if str(message.chat.id) != ADMIN_CHAT_ID: return
        bot.send_message(message.chat.id, "🤖 *SCADA Command Center*\nSelect an action:", reply_markup=main_menu(), parse_mode="Markdown")

    @bot.callback_query_handler(func=lambda call: True)
    def callback_query(call):
        global IDS_PROCESS
        global ISOLATION_MODE
        
        if str(call.message.chat.id) != ADMIN_CHAT_ID: return
        try:
            if call.data == "system_state":
                running = IDS_PROCESS is not None and IDS_PROCESS.poll() is None
                msg = f"🛡️ *IDS Status*: {'Running ✅' if running else 'Stopped ❌'}\n"
                msg += f"🔌 *Isolation Mode*: {'MANUAL / ISOLATED 🔴' if ISOLATION_MODE else 'NORMAL 🟢'}"
                bot.edit_message_text(msg, call.message.chat.id, call.message.message_id, reply_markup=main_menu(), parse_mode="Markdown")
                
            elif call.data == "status":
                bot.answer_callback_query(call.id, "Polling RTUs...")
                text, _ = get_scada_status()
                bot.edit_message_text("📡 *Live SCADA Status*\n\n" + text, call.message.chat.id, call.message.message_id, reply_markup=main_menu(), parse_mode="Markdown")
                
            elif call.data == "graph":
                if not plt:
                    bot.answer_callback_query(call.id, "matplotlib not installed.")
                    return
                bot.answer_callback_query(call.id, "Generating graph...")
                _, plot_data = get_scada_status()
                if not plot_data or not plot_data["names"]:
                    bot.send_message(call.message.chat.id, "No RTU data available.")
                    return
                
                plt.figure(figsize=(6, 4))
                plt.bar(plot_data["names"], plot_data["powers"], color='skyblue')
                plt.title("Current Power Usage (kW)")
                plt.ylabel("Power (kW)")
                buf = io.BytesIO()
                plt.savefig(buf, format='png')
                buf.seek(0)
                plt.close()
                
                bot.send_photo(call.message.chat.id, buf, caption="📈 Real-time Power Values")
                
            elif call.data == "reports":
                report_file = os.path.join(IDS_DIR, "anomaly_history.json")
                if os.path.exists(report_file):
                    with open(report_file, "r") as f:
                        data = json.load(f)
                        last_10 = data[-10:]
                        msg = "📜 *Last 10 Anomalies*\n\n"
                        for i, r in enumerate(reversed(last_10)):
                            cls = r.get('classification', 'N/A')
                            time_str = r.get('timestamp', '')[:19]
                            msg += f"*{i+1}.* `{time_str}` - {cls}\n"
                        bot.edit_message_text(msg, call.message.chat.id, call.message.message_id, reply_markup=main_menu(), parse_mode="Markdown")
                else:
                    bot.answer_callback_query(call.id, "No reports found.")
                    
            elif call.data == "start_ids_menu":
                interfaces = ["br-xyb", "eth0", "lo"]
                if psutil:
                    import socket
                    stats = psutil.net_if_addrs()
                    interfaces = list(stats.keys())
                markup = InlineKeyboardMarkup()
                for intf in interfaces[:5]:
                    markup.add(InlineKeyboardButton(f"Start on {intf}", callback_data=f"start_ids_{intf}"))
                markup.add(InlineKeyboardButton("🔙 Back", callback_data="system_state"))
                bot.edit_message_text("Select Interface to sniff:", call.message.chat.id, call.message.message_id, reply_markup=markup)
                
            elif call.data.startswith("start_ids_"):
                interface = call.data.replace("start_ids_", "")
                if IDS_PROCESS is not None and IDS_PROCESS.poll() is None:
                    bot.answer_callback_query(call.id, "IDS already running!")
                    return
                script_path = os.path.join(IDS_DIR, "scada_ids.py")
                IDS_PROCESS = subprocess.Popen(["python", script_path, "--interface", interface], cwd=IDS_DIR)
                bot.edit_message_text(f"✅ IDS Started on `{interface}`", call.message.chat.id, call.message.message_id, reply_markup=main_menu(), parse_mode="Markdown")
                
            elif call.data == "stop_ids":
                if IDS_PROCESS is not None and IDS_PROCESS.poll() is None:
                    IDS_PROCESS.terminate()
                    IDS_PROCESS.wait()
                    bot.edit_message_text("⏹️ IDS Stopped.", call.message.chat.id, call.message.message_id, reply_markup=main_menu())
                else:
                    bot.answer_callback_query(call.id, "IDS not running.")
                    
            elif call.data == "isolate":
                if not ISOLATION_MODE:
                    threading.Thread(target=execute_isolation).start()
                    bot.edit_message_text("🚨 *System Isolated!*", call.message.chat.id, call.message.message_id, reply_markup=main_menu(), parse_mode="Markdown")
                else:
                    bot.answer_callback_query(call.id, "Already isolated.")
                    
            elif call.data == "unisolate":
                execute_unisolation()
                bot.edit_message_text("✅ *System Unisolated!*", call.message.chat.id, call.message.message_id, reply_markup=main_menu(), parse_mode="Markdown")
                
        except Exception as e:
            bot.answer_callback_query(call.id, f"Error: {str(e)}")

    @bot.message_handler(commands=['isolate'])
    def handle_isolate_command(message):
        if str(message.chat.id) != ADMIN_CHAT_ID: return
        if not ISOLATION_MODE:
            threading.Thread(target=execute_isolation).start()
            bot.reply_to(message, "🚨 System Isolated.")

    @bot.message_handler(commands=['unisolate'])
    def handle_unisolate_command(message):
        if str(message.chat.id) != ADMIN_CHAT_ID: return
        execute_unisolation()
        bot.reply_to(message, "✅ System Unisolated.")

@app.route("/api/telegram_report", methods=["POST"])
def telegram_report():
    from flask import request
    report = request.json
    if not report:
        return jsonify({"success": False}), 400
        
    if bot and ADMIN_CHAT_ID:
        try:
            msg = "🚨 *SCADA Anomaly Report* 🚨\n\n"
            msg += f"Classification: `{report.get('classification', 'N/A')}`\n"
            msg += f"Score: `{report.get('anomaly_score', 'N/A')}`\n"
            msg += f"Target: `{report.get('dst_ip', 'N/A')}:{report.get('dst_port', 'N/A')}`\n"
            msg += f"Source: `{report.get('src_ip', 'N/A')}:{report.get('src_port', 'N/A')}`\n"
            msg += f"Time: `{report.get('timestamp', 'N/A')}`\n"
            
            if "Generic Traffic Anomaly" in report.get('classification', ''):
                msg += "\nℹ️ *Action*: General Anomaly -> System UNISOLATED/Kept Normal"
            else:
                msg += "\n⚠️ *Action*: Severe Anomaly -> System ISOLATED"
                
            bot.send_message(ADMIN_CHAT_ID, msg, parse_mode="Markdown")
            return jsonify({"success": True})
        except Exception as e:
            print(f"Failed to send telegram report: {e}")
            return jsonify({"success": False, "error": str(e)})
    return jsonify({"success": False, "message": "Bot not configured"})

def start_bot():
    if bot:
        print("[+] Telegram Bot Started")
        try:
            bot.polling(none_stop=True)
        except Exception as e:
            print(f"[-] Telegram Bot Polling Error: {e}")

if __name__ == "__main__":
    t = threading.Thread(target=start_bot, daemon=True)
    t.start()
    app.run(host="0.0.0.0", port=5050)
