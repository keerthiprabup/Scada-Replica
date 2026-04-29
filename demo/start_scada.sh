#!/bin/sh
echo "[!] REMOVING ISOLATION: Starting SCADA System..."
# Start the SCADA containers defined in the project
docker start substation feeder home home2 home3 scada controller
echo "[+] System Recovered."
