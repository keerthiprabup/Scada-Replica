#!/bin/bash
set -e

echo "=== Starting SCADA Master Server ==="
echo "Master ID: $MASTER_ID"
echo "API Port: $API_PORT"

python scada_master.py
