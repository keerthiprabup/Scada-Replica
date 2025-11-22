#!/bin/bash

# View logs from all SCADA services

CONTAINER=${1:-""}

if [ -z "$CONTAINER" ]; then
    echo "Showing logs from all services (Ctrl+C to stop)..."
    docker-compose logs -f
else
    echo "Showing logs from $CONTAINER..."
    docker-compose logs -f "$CONTAINER"
fi
