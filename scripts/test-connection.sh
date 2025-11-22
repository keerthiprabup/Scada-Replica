#!/bin/bash

# Connection test script for SCADA services

echo ""
echo "╔════════════════════════════════════════════════════════════════╗"
echo "║           SCADA Services - Connection Test                   ║"
echo "╚════════════════════════════════════════════════════════════════╝"
echo ""

# Wait for services to be ready
echo "Waiting for services to be ready..."
sleep 5

BASE_URL="http://localhost"

# Test SCADA Master
echo "Testing SCADA Master Server (Port 8080)..."
RESPONSE=$(curl -s -o /dev/null -w "%{http_code}" $BASE_URL:8080/api/status)
if [ "$RESPONSE" == "200" ]; then
    echo "  ✓ SCADA Master is responding"
    curl -s $BASE_URL:8080/api/status | python -m json.tool 2>/dev/null | head -20
else
    echo "  ✗ SCADA Master not responding (HTTP $RESPONSE)"
fi

echo ""

# Test Data Logger
echo "Testing Data Logger (Port 8081)..."
RESPONSE=$(curl -s -o /dev/null -w "%{http_code}" $BASE_URL:8081/api/health)
if [ "$RESPONSE" == "200" ]; then
    echo "  ✓ Data Logger is responding"
    curl -s $BASE_URL:8081/api/stats | python -m json.tool 2>/dev/null | head -20
else
    echo "  ✗ Data Logger not responding (HTTP $RESPONSE)"
fi

echo ""
echo "Connection tests complete"
echo ""
