# SCADA Attack Scripts

This directory contains Python scripts to simulate cyberattacks on the SCADA testbed for dataset generation.

## Prerequisites

Install the required Python packages:

```bash
pip install -r requirements.txt
```

Ensure the SCADA testbed is running:

```bash
docker-compose up -d --build
```

## Usage

### 1. Automated Scenario (Recommended)

To run a full sequence of attacks (Recon -> Injection -> DoS) while capturing traffic with Wireshark:

```bash
python run_scenario.py --target localhost
```

### 2. Manual Execution

#### Reconnaissance
Scan for Modbus services on default ports (5002-5006).

```bash
python recon_scan.py --target localhost
```

#### Command Injection
Manipulate RTU state.

*   **Open GCB (Substation)**:
    ```bash
    python command_injection.py --target localhost --port 5002 --unit 1 write-coil 0 0
    ```

*   **Trip Feeder Breaker**:
    ```bash
    python command_injection.py --target localhost --port 5003 --unit 2 write-coil 0 0
    ```

*   **Fuzzing (Random Writes)**:
    ```bash
    python command_injection.py --target localhost --port 5002 --unit 1 fuzz --count 100
    ```

#### Denial of Service (DoS)
Flood the target with Modbus queries.

```bash
python dos_flood.py --target localhost --port 5002 --duration 30 --threads 50
```

## Dataset Generation Workflow

1.  Start Wireshark and listen on the Docker network interface (e.g., `br-xxxxxxxx`).
2.  Start capture.
3.  Run `python run_scenario.py`.
4.  Stop capture and save as `.pcap` or `.csv`.
5.  Use the timestamps from `run_scenario.py` output to label the dataset.
