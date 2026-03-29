#!/bin/sh
echo "[!] ANOMALY DETECTED: Isolating SCADA System..."
# Stop the SCADA containers defined in the project
# This assumes the script runs in the same directory as docker-compose.yml,
# but using specific container names is safer regardless of compose directory.
docker stop substation feeder home home2 home3 scada controller
echo "[+] System Isolated."
