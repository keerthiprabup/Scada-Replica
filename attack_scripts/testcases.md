# SCADA Replica Attack Scripts Test Cases

This document provides a comprehensive guide on how to test the different attack scripts available in this directory against the SCADA replica. The scripts leverage the `pymodbus` library to simulate network reconnaissance, command injection, and Denial of Service (DoS) attacks on Modbus devices.

> **Note:** Ensure your SCADA Docker containers (or local target servers) are up and running before executing these tests. Replace `<TARGET_IP>` with `localhost` or the IP address of your SCADA instance.

---

## 1. Reconnaissance Scan (`recon_scan.py`)

**Purpose:** Identifies active Modbus TCP services by scanning a list of common Modbus ports on the target.

### Steps to Test
1. Make sure your target server exposes Modbus ports (e.g., `5002`, `5003`, `5004`, etc.).
2. Run the scanner:
   ```bash
   python recon_scan.py --target <TARGET_IP> --ports 5002 5003 5004 5005 5006
   ```

**Expected Output:**
- The script should report which ports are `OPEN` and verify successful Modbus protocol connection by attempting to read a holding register.
- Summary list of found Modbus services at the end.

---

## 2. Command Injection (`command_injection.py`)

**Purpose:** Directly interacts with the Modbus nodes to read or write specific device coils and registers. This simulates a threat actor bypassing the HMI and turning off/on physical processes maliciously.

### Test Case A: Write to a Coil (Function 05)
Turn ON (value `1`) or OFF (value `0`) a specific coil.
```bash
# Turn ON Coil 0 at Port 5002 (Unit ID 1)
python command_injection.py write-coil 0 1 --target <TARGET_IP> --port 5002 --unit 1

# Turn OFF Coil 0 at Port 5002 (Unit ID 1)
python command_injection.py write-coil 0 0 --target <TARGET_IP> --port 5002 --unit 1
```
**Expected Output:** Connection messages followed by `[+] Write Successful!`.

### Test Case B: Write to a Register (Function 06)
Inject a 16-bit integer value (e.g., `1234`) into a holding register.
```bash
python command_injection.py write-reg 0 1234 --target <TARGET_IP> --port 5002 --unit 1
```

### Test Case C: Fuzzing Attack
Randomly send multiple Coil and Register write commands.
```bash
# Send 50 random commands to target
python command_injection.py fuzz --count 50 --target <TARGET_IP> --port 5003 --unit 2
```

*(Note: Thanks to recent argparse enhancements, global flags like `--target`, `--port`, and `--unit` can now flawlessly be placed either before or after the command).*

---

## 3. Denial of Service (DoS) Flood (`dos_flood.py`)

**Purpose:** Floods the targeted Modbus socket/server with high-velocity `read_holding_registers` requests across concurrent threads, attempting to exhaust network or service resources.

### Steps to Test
1. Begin the flood for 10 seconds using 20 threads.
   ```bash
   python dos_flood.py --target <TARGET_IP> --port 5002 --duration 10 --threads 20
   ```
2. Monitor your SCADA container logs or HMI response times while the attack runs.
   
**Expected Output:**
- An initialization message confirming connections across multiple threads.
- Upon completion (or manual user interrupt `Ctrl+C`), logs reporting exactly how many packets were sent by each thread.

---

## 4. Full Scenario Orchestrator (`run_scenario.py`)

**Purpose:** Automates an entire multi-stage attack lifecycle (simulating a kill chain). It automatically executes Reconnaissance -> Multiple Targeted Command Injections -> Modbus Flooding -> Fuzzing.

### Steps to Test
1. Optionally start Wireshark or `tcpdump` on your Docker network interface to capture all traffic.
2. Execute the scenario against the target IP:
   ```bash
   python run_scenario.py --target <TARGET_IP>
   ```

**Expected Output:**
- The scenario script sequentially logs the execution of each stage: `[+] Starting: Reconnaissance Scan`, followed by the output of `recon_scan.py`.
- It will then print boundaries for each component until completing the final Fuzzing step.
