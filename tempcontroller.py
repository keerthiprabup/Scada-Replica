from pymodbus.client import ModbusTcpClient
import time

import os

RTU_IP = os.getenv("SUBSTATION_IP", "127.0.0.1")
RTU_PORT = int(os.getenv("SUBSTATION_PORT", 5002))
UNIT_ID = 1

# Connect to RTU
client = ModbusTcpClient(RTU_IP, port=RTU_PORT)
if not client.connect():
    print("[SCADA] Cannot connect to RTU")
    exit(1)

print("[SCADA] Connected to Generating Substation RTU")

# Example: close GCB every 10 sec
try:
    t0 = time.time()
    while True:
        elapsed = time.time() - t0

        # write CLOSE every 10 sec (demo)
        if int(elapsed) % 10 == 0:
            client.write_coil(0, True, unit=UNIT_ID)
            print(f"[SCADA] t={elapsed:.1f}s → GCB = CLOSED")

        time.sleep(1)

except KeyboardInterrupt:
    print("[SCADA] Controller stopped")

finally:
    client.close()
