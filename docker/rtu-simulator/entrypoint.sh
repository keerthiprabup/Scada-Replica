#!/bin/bash
set -e

echo "=== Starting RTU Simulator (DNP3 Outstation) ==="
echo "RTU ID: $RTU_ID"
echo "RTU Name: $RTU_NAME"
echo "DNP3 Port: $DNP3_PORT"

python rtu_outstation.py
