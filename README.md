# SCADA Testbed Replica - DNP3-based Power Generation Substation Simulator

A comprehensive Docker-based SCADA testbed replica simulating a power generation substation with DNP3 protocol communication, realistic electrical parameters, and monitoring capabilities.

## System Architecture

<img width="455" height="538" alt="image" src="https://github.com/user-attachments/assets/472d7f82-21ad-46ad-97f4-40cd227c12ea" />


## Features

### RTU Substation Simulators
- **DNP3 Outstation Protocol**: Industry-standard SCADA communication
- **Electrical Parameters**: Voltage, Current, Frequency, Temperature
- **Power Calculations**: Real power (kW), Reactive power (kVAR), Apparent power (kVA)
- **Load Monitoring**: Transformer load percentage and status
- **Realistic Variations**: Brownian motion simulation for natural fluctuations

### SCADA Master Server
- **DNP3 Master**: Polls all RTU outstations
- **REST API**: JSON-based access to all measurements
- **5-Second Polling**: Configurable measurement intervals
- **Connection Status**: Real-time status monitoring
- **Measurement History**: 1000-point rolling buffer per RTU

### Data Logger & Monitoring
- **Persistent Logging**: JSON-based measurement storage
- **Performance Metrics**: Record count, error tracking, timing
- **API Dashboard**: Real-time system status
- **Statistics**: Min/Max/Average calculations

## Requirements

- Docker 20.10+
- Docker Compose 2.0+
- 2GB available RAM
- 500MB disk space for logs

## Quick Start

### 1. Clone/Extract Files
Extract all files maintaining the directory structure:
```
scada-testbed/
├── docker-compose.yml
├── docker/
│   ├── rtu-simulator/
│   ├── scada-server/
│   └── monitoring/
├── scripts/
└── README.md
```

### 2. Make Scripts Executable
```bash
cd scada-testbed
chmod +x scripts/*.sh
```

### 3. Start the System
```bash
./scripts/startup.sh
```

The system will:
- Build all Docker images
- Create and start all containers
- Initialize the SCADA network
- Begin measuring and logging data

### 4. Verify Installation
```bash
./scripts/test-connection.sh
```

## API Usage

### Get Current System Status
```bash
curl http://localhost:8080/api/status | jq
```

Response:
```json
{
  "master_id": 1,
  "timestamp": "2024-01-15T10:30:45.123456",
  "outstations": {
    "1": {
      "name": "Substation_1",
      "connection_status": "CONNECTED",
      "latest_measurement": {
        "voltage": 405.2,
        "current": 425.8,
        "frequency": 60.0,
        "temperature": 52.3,
        "real_power_kw": 221.4,
        "load_percentage": 53.2
      }
    }
  }
}
```

### Get Specific Outstation Data
```bash
curl http://localhost:8080/api/outstation/1 | jq
```

### Get Measurement History
```bash
curl "http://localhost:8080/api/measurements/1?limit=50&offset=0" | jq
```

### Get Monitoring Statistics
```bash
curl http://localhost:8081/api/stats | jq
```

### Get Recent Logs
```bash
curl "http://localhost:8081/api/logs?limit=20" | jq
```

## Monitoring Logs

### View All Container Logs
```bash
./scripts/logs.sh
```

### View Specific Service Logs
```bash
./scripts/logs.sh rtu-substation-1
./scripts/logs.sh scada-master-server
./scripts/logs.sh scada-data-logger
```

### Real-time Docker Logs
```bash
docker-compose logs -f
```

## File Structure

```
scada-testbed/
├── docker-compose.yml              # Container orchestration
├── docker/
│   ├── rtu-simulator/
│   │   ├── Dockerfile
│   │   ├── rtu_outstation.py      # DNP3 Outstation implementation
│   │   ├── entrypoint.sh
│   │   └── requirements.txt
│   ├── scada-server/
│   │   ├── Dockerfile
│   │   ├── scada_master.py        # DNP3 Master + REST API
│   │   ├── entrypoint.sh
│   │   └── requirements.txt
│   └── monitoring/
│       ├── Dockerfile
│       ├── data_logger.py         # Data logging service
│       ├── entrypoint.sh
│       └── requirements.txt
├── scripts/
│   ├── startup.sh                 # Start all services
│   ├── stop.sh                    # Stop all services
│   ├── logs.sh                    # View logs
│   ├── clean.sh                   # Full cleanup
│   ├── network-setup.sh           # Network diagnostics
│   ├── test-connection.sh         # Connection tests
│   └── make-executable.sh         # Make scripts executable
└── README.md                      # This file
```

## Electrical Parameters

### Substation 1
- **Voltage Range**: 380-420 V
- **Current Range**: 100-800 A
- **Temperature Range**: 20-85°C
- **Frequency**: 59.8-60.2 Hz

### Substation 2
- **Voltage Range**: 380-420 V
- **Current Range**: 150-750 A
- **Temperature Range**: 20-85 °C
- **Frequency**: 59.8-60.2 Hz

Based on IEEE Std 666-2007 and ANSI C84.1-2020 standards for power generation plants.

## DNP3 Protocol Details

- **Protocol Version**: DNP3 (IEC 60870-5-104 compatible)
- **Transport**: TCP/IP over Docker network
- **Polling Interval**: 5 seconds (configurable)
- **Data Types**: Analog Inputs (measurements)
- **Architecture**: Master-Outstation model

### Port Mapping
- RTU Substation 1: Port 20000
- RTU Substation 2: Port 20001
- SCADA Master API: Port 8080
- Data Logger API: Port 8081

## Data Logging

All measurements are logged in JSON format:

**RTU Measurements**:
```
logs/rtu_1_measurements.json
logs/rtu_2_measurements.json
```

**System Status**:
```
logs/scada_status.jsonl
```

Each line is a complete JSON object with timestamp, measurements, and status.

## Troubleshooting

### Containers Won't Start
```bash
docker-compose logs
docker system prune
./scripts/clean.sh
./scripts/startup.sh
```

### Network Connectivity Issues
```bash
./scripts/network-setup.sh
docker-compose restart
```

### API Not Responding
```bash
# Check if services are running
docker-compose ps

# Check logs
./scripts/logs.sh

# Test connectivity
curl http://localhost:8080/api/health
curl http://localhost:8081/api/health
```

### High Memory Usage
```bash
# Clean up Docker system
docker system prune
docker image prune

# Reduce log retention
rm -rf logs/*
```

## Performance Tuning

### Increase Polling Frequency
Edit `docker-compose.yml`:
```yaml
environment:
  - POLL_INTERVAL=2  # 2 seconds instead of 5
```

### Reduce Memory Footprint
```bash
# Limit measurement history
# Edit docker/scada-server/scada_master.py:
# Change: if len(self.measurement_data[rtu_id]) > 1000:
# To: if len(self.measurement_data[rtu_id]) > 100:
```

## Extensions & Customization

### Add More RTUs
1. Add new service in `docker-compose.yml`
2. Create corresponding environment variables
3. Update `scada_master.py` to poll new outstation

### Integrate Real DNP3 Hardware
Replace mock DNP3 implementation with actual pydnp3 outstation connections.

### Add Alerting
Implement threshold-based alerts in data logger for critical parameters (temperature > 80°C, etc.)

### Database Integration
Connect to PostgreSQL/InfluxDB for time-series data persistence.

## Standards Compliance

- **IEEE Std 666-2007**: Design guide for electrical power service systems
- **ANSI C84.1-2020**: Nominal voltage ratings and tolerances
- **DNP3**: Open standard SCADA protocol
- **IEC 60870-5-104**: Compatible telecontrol protocol

## Support & Documentation

### Docker References
- https://docs.docker.com/compose/
- https://docs.docker.com/

### DNP3 Protocol
- https://www.dnp.org/
- pydnp3 documentation

### SCADA Systems
- IEEE Std 666-2007
- NERC Standards

## License

This SCADA testbed is provided for educational and testing purposes.

## Version

**Current Version**: 1.0.0  
**Last Updated**: 2024-01-15  
**Compatibility**: Docker 20.10+, Docker Compose 2.0+

---

**For issues or questions, refer to logs or check Docker container status with:**
```bash
docker-compose ps
docker-compose logs
