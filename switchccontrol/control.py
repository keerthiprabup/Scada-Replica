# switch_control.py
from pymodbus.client import ModbusTcpClient
import time

RTU_IP = "127.0.0.1"
RTU_PORT = 502
UNIT_ID = 1

client = ModbusTcpClient(RTU_IP, port=RTU_PORT)
client.connect()

# Toggle switch 0 ON
r = client.write_coil(0, True, unit=UNIT_ID)
if r.isError():
    print("Error writing coil")
else:
    print("Switch 0 turned ON")

time.sleep(1)

# Read switch 0
r = client.read_coils(0, 1, unit=UNIT_ID)
if r.isError():
    print("Error reading coil")
else:
    print(f"Switch 0 state: {r.bits[0]}")

# Toggle switch 0 OFF
r = client.write_coil(0, False, unit=UNIT_ID)
print("Switch 0 turned OFF")

client.close()
