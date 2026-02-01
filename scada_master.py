from pymodbus.client import ModbusTcpClient
import time

import os

# ---------------- RTU CONFIG ----------------
RTUS = {
    "SUBSTATION": {"ip": os.getenv("SUBSTATION_IP", "127.0.0.1"), "port": 5002, "unit": 1},
    "FEEDER":     {"ip": os.getenv("FEEDER_IP", "127.0.0.1"), "port": 5003, "unit": 2},
    "HOME":       {"ip": os.getenv("HOME_IP", "127.0.0.1"), "port": 5004, "unit": 3},
}

# ---------------- CLIENTS ----------------
clients = {}
for name, cfg in RTUS.items():
    clients[name] = ModbusTcpClient(cfg["ip"], port=cfg["port"])
    clients[name].connect()

# ---------------- POLL FUNCTIONS ----------------
def read_holding(client, unit, start, count):
    rr = client.read_holding_registers(start, count=count, unit=unit)
    return rr.registers if not rr.isError() else None

def read_coils(client, unit, start, count):
    rr = client.read_coils(start, count=count, unit=unit)
    return rr.bits if not rr.isError() else None

# ---------------- MAIN LOOP ----------------
try:
    while True:
        print("\n================ SCADA SNAPSHOT ================")

        # -------- SUBSTATION --------
        sub = RTUS["SUBSTATION"]
        c = clients["SUBSTATION"]

        hr = read_holding(c, sub["unit"], 0, 6)
        co = read_coils(c, sub["unit"], 0, 3)

        if hr and co:
            print("\n[SUBSTATION]")
            print(f" Load            : {hr[0]} %")
            print(f" Temperature     : {hr[1]} °C")
            print(f" Primary Voltage : {hr[2]*10} V")
            print(f" Secondary Volt  : {hr[3]} V")
            print(f" Apparent Power  : {hr[4]*10} kVA")
            print(f" Active Power    : {hr[5]*10} kW")
            print(f" Breaker Closed  : {co[0]}")
            print(f" Overload Trip   : {co[1]}")
            print(f" High Temp Alarm : {co[2]}")

        # -------- FEEDER --------
        fed = RTUS["FEEDER"]
        c = clients["FEEDER"]

        hr = read_holding(c, fed["unit"], 0, 5)
        co = read_coils(c, fed["unit"], 0, 4)

        if hr and co:
            print("\n[FEEDER]")
            print(f" Load            : {hr[0]} %")
            print(f" Voltage         : {hr[1]} V")
            print(f" Current         : {hr[2]} A")
            print(f" Power Factor    : {hr[3]/100:.2f}")
            print(f" Power           : {hr[4]*10} kW")
            print(f" Breaker Closed  : {co[0]}")
            print(f" Load Shed       : {co[1]}")
            print(f" Overload Alarm  : {co[2]}")
            print(f" Upstream OK     : {co[3]}")

        # -------- HOME --------
        home = RTUS["HOME"]
        c = clients["HOME"]

        hr = read_holding(c, home["unit"], 0, 5)
        co = read_coils(c, home["unit"], 0, 3)

        if hr and co:
            print("\n[HOME]")
            print(f" Load            : {hr[0]} W")
            print(f" Voltage         : {hr[1]} V")
            print(f" Current         : {hr[2]/10:.1f} A")
            print(f" Energy Today    : {hr[3]/10:.1f} kWh")
            print(f" Power Factor    : {hr[4]/100:.2f}")
            print(f" Supply Available: {co[0]}")
            print(f" Overload Trip   : {co[1]}")
            print(f" Load Shed Cmd   : {co[2]}")

        print("================================================")
        time.sleep(3)

except KeyboardInterrupt:
    print("\nSCADA Master stopped")

finally:
    for c in clients.values():
        c.close()

