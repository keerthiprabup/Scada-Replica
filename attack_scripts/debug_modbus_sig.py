
from pymodbus.client import ModbusTcpClient
import inspect

client = ModbusTcpClient('localhost')
print("=== Pymodbus Debug Info ===")
try:
    sig = inspect.signature(client.read_holding_registers)
    print(f"Signature of read_holding_registers: {sig}")
except Exception as e:
    print(f"Could not get signature: {e}")

print("\nDocstring:")
print(client.read_holding_registers.__doc__)

print("\nAttempting default call check:")
try:
    # Try with minimal args
    client.read_holding_registers(0)
    print("read_holding_registers(0) executed (connection fail expected but arg check passed)")
except TypeError as e:
    print(f"read_holding_registers(0) failed with TypeError: {e}")
except Exception as e:
    print(f"read_holding_registers(0) failed with other error: {e}")
