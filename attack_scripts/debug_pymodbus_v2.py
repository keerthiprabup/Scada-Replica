
import inspect
from pymodbus.client import ModbusTcpClient

print("=== Pymodbus Signature Debugger ===")
client = ModbusTcpClient('localhost')

methods = [
    ('read_holding_registers', client.read_holding_registers),
    ('write_coil', client.write_coil),
    ('write_register', client.write_register)
]

for name, method in methods:
    print(f"\n--- {name} ---")
    try:
        sig = inspect.signature(method)
        print(f"Signature: {sig}")
        print("Parameters:")
        for param in sig.parameters.values():
            print(f"  - {param.name}: {param.kind} (Default: {param.default})")
    except Exception as e:
        print(f"Error getting signature: {e}")

print("\n=== Connectivity Test (localhost:5002) ===")
# Try to connect and detect working call style
if client.connect():
    print("[+] Connected.")
    
    # Check 1: Full Keywords with 'slave'
    print("\nAttempt 1: client.read_holding_registers(address=0, count=1, slave=1)")
    try:
        client.read_holding_registers(address=0, count=1, slave=1)
        print(">>> SUCCESS")
    except Exception as e:
        print(f">>> FAILED: {e}")

    # Check 2: Full Keywords with 'unit'
    print("\nAttempt 2: client.read_holding_registers(address=0, count=1, unit=1)")
    try:
        client.read_holding_registers(address=0, count=1, unit=1)
        print(">>> SUCCESS")
    except Exception as e:
        print(f">>> FAILED: {e}")

    # Check 3: Positional Address, Keyword Count, Keyword slave
    print("\nAttempt 3: client.read_holding_registers(0, count=1, slave=1)")
    try:
        client.read_holding_registers(0, count=1, slave=1)
        print(">>> SUCCESS")
    except Exception as e:
        print(f">>> FAILED: {e}")

    # Check 4: No Unit/Slave ID
    print("\nAttempt 4: client.read_holding_registers(address=0, count=1)")
    try:
        client.read_holding_registers(address=0, count=1)
        print(">>> SUCCESS (Warning: No Unit ID sent)")
    except Exception as e:
        print(f">>> FAILED: {e}")

    client.close()
else:
    print("[-] Could not connect to localhost:5002. Ensure container is running.")
