#!/bin/bash

# SCADA Testbed Startup Script
# Run this to start the entire SCADA replica system

set -e

echo ""
echo "╔════════════════════════════════════════════════════════════════╗"
echo "║         SCADA Testbed Replica - Startup Script                ║"
echo "║  DNP3-based Power Generation Substation Simulator             ║"
echo "╚════════════════════════════════════════════════════════════════╝"
echo ""

# Check Docker
if ! command -v docker &> /dev/null; then
    echo "ERROR: Docker is not installed"
    exit 1
fi

if ! command -v docker-compose &> /dev/null; then
    echo "ERROR: Docker Compose is not installed"
    exit 1
fi

echo "[1/5] Creating logs directory..."
mkdir -p logs
chmod 777 logs

echo "[2/5] Pulling Docker images..."
docker-compose pull || true

echo "[3/5] Building Docker images..."
docker-compose build --no-cache

echo "[4/5] Starting containers..."
docker-compose up -d

echo "[5/5] Waiting for services to be ready..."
sleep 10

echo ""
echo "╔════════════════════════════════════════════════════════════════╗"
echo "║              SCADA System Started Successfully!                ║"
echo "╚════════════════════════════════════════════════════════════════╝"
echo ""
echo "Services Running:"
echo "  ✓ RTU Substation 1 (DNP3 Outstation) - Port 20000"
echo "  ✓ RTU Substation 2 (DNP3 Outstation) - Port 20001"
echo "  ✓ SCADA Master Server - Port 8080"
echo "  ✓ Data Logger & Monitoring - Port 8081"
echo ""
echo "API Endpoints:"
echo "  SCADA Status:     curl http://localhost:8080/api/status"
echo "  Outstation Data:  curl http://localhost:8080/api/outstation/1"
echo "  Measurements:     curl http://localhost:8080/api/measurements/1"
echo "  Monitor Stats:    curl http://localhost:8081/api/stats"
echo ""
echo "View Logs:"
echo "  All Services:     docker-compose logs -f"
echo "  SCADA Master:     docker-compose logs -f scada-master"
echo "  RTU Substation 1: docker-compose logs -f rtu-substation-1"
echo "  RTU Substation 2: docker-compose logs -f rtu-substation-2"
echo ""
echo "Stop System:       ./scripts/stop.sh"
echo "View Status:       ./scripts/logs.sh"
echo ""
