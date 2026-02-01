# Containerized SCADA-Based Substation Testbed

This project implements a containerized SCADA testbed for cyber-physical security research, aligned with the design proposed in the reference paper ("A Containerized SCADA-Based Substation Testbed...").

## Architecture

The testbed consists of the following components, each running in an isolated Docker container:

1.  **SCADA Master (`scada`)**: A centralized supervisory system that polls RTUs and issues control commands.
2.  **Substation RTU (`substation`)**: Simulates a generator, transformer, and Gas Circuit Breaker (GCB). Implements protection logic (Overcurrent trip).
3.  **Feeder RTU (`feeder`)**: Simulates a distribution feeder with load shedding capabilities.
4.  **Home RTU (`home`)**: Simulates a residential consumer with dynamic load profiles.
5.  **Temp Controller (`controller`)**: An external attack/control script interacting with the Substation.

### Key Features
-   **PLC-Validated Control Logic**: RTUs process commands through a 4-stage pipeline (Input Processing -> Physical Abstraction -> Protection Logic -> Output Conditioning).
-   **Containerization**: All services are Dockerized for modularity and scalability.
-   **Event-Centric Monitoring**: Logs include `t_rx` (Reception Time), `t_update` (Update Time), and `latency_delta` to facilitate forensic analysis.
-   **Wazuh Integration**: Containers are pre-configured with `wazuh-agent` for security monitoring (requires a running Wazuh Manager).

## Getting Started

### Prerequisites
-   Docker and Docker Compose
-   (Optional) Wazuh Manager for security monitoring

### Running the Testbed

1.  **Build and Start**:
    ```bash
    docker-compose up --build
    ```

    To run in the background:
    ```bash
    docker-compose up -d --build
    ```

2.  **View Logs**:
    ```bash
    docker-compose logs -f
    ```
    You will see the SCADA Master polling and the RTUs logging their state transitions.

3.  **Wazuh Configuration**:
    The agents are configured to look for a manager at IP `192.168.1.100`. To specify your own Wazuh Manager IP:
    ```bash
    WAZUH_MANAGER_IP=your.manager.ip.address docker-compose up -d --build
    ```

## Project Structure

-   `scada_master.py`: Main SCADA loop.
-   `substation_rtu.py`: Generator/Substation logic (Unit ID 1).
-   `feeder_rtu.py`: Distribution Feeder logic (Unit ID 2).
-   `home_rtu.py`: Residential Consumer logic (Unit ID 3).
-   `tempcontroller.py`: Test/Attack script.
-   `Dockerfile`: Unified build definition for Python environment and Wazuh agent.
-   `entrypoint.sh`: Startup script to configure Wazuh and launch apps.
-   `docker-compose.yml`: Service orchestration.

## Cybersecurity Research

This testbed allows for testing various attack vectors:
-   **False Data Injection**: Modify `feeder_rtu.py` logic to report fake load values.
-   **Command Replay**: Capture and resend Modbus TCP packets.
-   **DoS**: Flood the network and observe `latency_delta` in `log.json`.

## References
Based on "A Containerized SCADA-Based Substation Testbed for Supervisory-Level Cyber-Physical Security Research".
