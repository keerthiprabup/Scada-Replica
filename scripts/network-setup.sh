#!/bin/bash

# Network diagnostics and setup for SCADA testbed

echo ""
echo "╔════════════════════════════════════════════════════════════════╗"
echo "║            SCADA Network Setup and Diagnostics                ║"
echo "╚════════════════════════════════════════════════════════════════╝"
echo ""

echo "Checking Docker Network Configuration..."
echo ""

# Check if network exists
if docker network ls | grep -q scada_scada-network; then
    echo "✓ SCADA network exists"
    docker network inspect scada_scada-network | grep -A 20 "Containers"
else
    echo "✗ SCADA network not found"
fi

echo ""
echo "Checking Container Connectivity..."
echo ""

# Test RTU 1
echo "Testing RTU Substation 1 (port 20000)..."
docker exec scada-rtu-sub1 netstat -tlnp 2>/dev/null | grep 20000 || echo "  Port 20000 not listening"

# Test RTU 2
echo "Testing RTU Substation 2 (port 20001)..."
docker exec scada-rtu-sub2 netstat -tlnp 2>/dev/null | grep 20001 || echo "  Port 20001 not listening"

# Test SCADA Master
echo "Testing SCADA Master Server (port 8080)..."
docker exec scada-master-server netstat -tlnp 2>/dev/null | grep 8080 || echo "  Port 8080 not listening"

echo ""
echo "Network Setup Complete"
echo ""
