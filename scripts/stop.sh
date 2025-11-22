#!/bin/bash

# SCADA Testbed Stop Script

set -e

echo ""
echo "Stopping SCADA Testbed..."
docker-compose down

echo "All containers stopped."
