#!/bin/bash

# Complete cleanup of SCADA Testbed

set -e

echo ""
echo "╔════════════════════════════════════════════════════════════════╗"
echo "║               SCADA Testbed - Complete Cleanup                ║"
echo "╚════════════════════════════════════════════════════════════════╝"
echo ""

echo "[1/4] Stopping containers..."
docker-compose down || true

echo "[2/4] Removing Docker images..."
docker-compose down --rmi all || true

echo "[3/4] Removing logs..."
rm -rf logs/*

echo "[4/4] Removing build artifacts..."
find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true

echo ""
echo "Cleanup complete. System reset to initial state."
echo ""
