#!/bin/bash
set -e

echo "=== Starting Data Logger and Monitoring Service ==="
echo "SCADA Server URL: $SCADA_SERVER_URL"

python data_logger.py
