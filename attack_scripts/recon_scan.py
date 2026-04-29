
import sys
import socket
import argparse
from pymodbus.client import ModbusTcpClient
from pymodbus.exceptions import ModbusException

def check_port(ip, port):
    """Check if a TCP port is open."""
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(1)
        result = sock.connect_ex((ip, port))
        sock.close()
        return result == 0
    except Exception as e:
        print(f"[-] Error checking port {port}: {e}")
        return False

def scan_modbus(ip, ports):
    """Scan for Modbus services on specified ports."""
    print(f"[*] Scanning {ip} for Modbus services on ports: {ports}")
    found_services = []

    for port in ports:
        if check_port(ip, port):
            print(f"[+] Port {port} is OPEN. Attempting Modbus connection...")
            client = ModbusTcpClient(ip, port=port)
            try:
                if client.connect():
                    print(f"[+] Successfully connected to Modbus server at {ip}:{port}")
                    # Attempt to read registers to confirm. 
                    # Pymodbus 3.11+ uses 'device_id' and keyword-only args for count/device_id
                    rr = client.read_holding_registers(address=0, count=1, device_id=1)
                            
                    if not rr.isError():
                        print(f"    [+] confirmed Modbus protocol. Register 0: {rr.registers}")
                        found_services.append(port)
                    else:
                        print(f"    [-] Connected but failed to read register 0: {rr}")
                    client.close()
                else:
                    print(f"[-] Failed to connect to Modbus server at {ip}:{port}")
            except ModbusException as e:
                print(f"[-] Modbus Exception at {ip}:{port}: {e}")
            except Exception as e:
                print(f"[-] Error connecting to {ip}:{port}: {e}")
        else:
            print(f"[-] Port {port} is CLOSED.")
            
    return found_services

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Modbus Reconnaissance Script")
    parser.add_argument("--target", default="localhost", help="Target IP address (default: localhost)")
    parser.add_argument("--ports", nargs="+", type=int, default=[5002, 5003, 5004, 5005, 5006], help="Ports to scan (default: 5002-5006)")
    
    args = parser.parse_args()
    
    print("=== Modbus Reconnaissance Tool ===")
    found = scan_modbus(args.target, args.ports)
    
    if found:
        print("\n[+] Scan Complete. Found Modbus services on ports:")
        for p in found:
            print(f"    - {args.target}:{p}")
    else:
        print("\n[-] Scan Complete. No Modbus services found.")
