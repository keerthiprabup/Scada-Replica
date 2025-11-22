#!/usr/bin/env python3
"""
DNP3 Outstation RTU Simulator for SCADA Testbed
Simulates electrical transformer substation with realistic parameters
"""

import os
import json
import random
import logging
from datetime import datetime
from threading import Thread
import time

try:
    from pydnp3 import opendnp3, openpal, asiopal, asiodnp3
except ImportError:
    print("WARNING: pydnp3 not available, using mock implementation")
    opendnp3 = None

# Configure logging
logging.basicConfig(
    level=os.getenv('LOG_LEVEL', 'INFO'),
    format='%(asctime)s - RTU-%(rtu_id)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

class TransformerSimulator:
    """Simulates electrical transformer parameters"""
    
    def __init__(self, rtu_id, min_voltage, max_voltage, min_current, max_current, 
                 min_freq, max_freq, min_temp, max_temp):
        self.rtu_id = rtu_id
        self.min_voltage = min_voltage
        self.max_voltage = max_voltage
        self.min_current = min_current
        self.max_current = max_current
        self.min_freq = min_freq
        self.max_freq = max_freq
        self.min_temp = min_temp
        self.max_temp = max_temp
        
        # Current values with slight noise
        self.voltage = random.uniform(min_voltage, max_voltage)
        self.current = random.uniform(min_current, max_current)
        self.frequency = random.uniform(min_freq, max_freq)
        self.temperature = random.uniform(min_temp, max_temp)
        
    def get_measurements(self):
        """Generate realistic electrical measurements with brownian motion"""
        # Add small random walk to simulate natural variations
        self.voltage += random.uniform(-0.5, 0.5)
        self.voltage = max(self.min_voltage, min(self.max_voltage, self.voltage))
        
        self.current += random.uniform(-5, 5)
        self.current = max(self.min_current, min(self.max_current, self.current))
        
        self.frequency += random.uniform(-0.02, 0.02)
        self.frequency = max(self.min_freq, min(self.max_freq, self.frequency))
        
        self.temperature += random.uniform(-0.3, 0.3)
        self.temperature = max(self.min_temp, min(self.max_temp, self.temperature))
        
        # Calculate power parameters
        power_factor = 0.95  # Typical transformer PF
        apparent_power = (self.voltage * self.current * 3) / 1000  # 3-phase, kVA
        real_power = apparent_power * power_factor  # kW
        reactive_power = (apparent_power ** 2 - real_power ** 2) ** 0.5  # kVAR
        load_percent = (self.current / self.max_current) * 100
        
        return {
            'timestamp': datetime.now().isoformat(),
            'rtu_id': self.rtu_id,
            'voltage': round(self.voltage, 2),
            'current': round(self.current, 2),
            'frequency': round(self.frequency, 3),
            'temperature': round(self.temperature, 2),
            'real_power_kw': round(real_power, 2),
            'reactive_power_kvar': round(reactive_power, 2),
            'apparent_power_kva': round(apparent_power, 2),
            'power_factor': power_factor,
            'load_percentage': round(load_percent, 2),
            'status': 'NORMAL' if self.temperature < 80 else 'WARNING'
        }


class MockDNP3Outstation:
    """Mock DNP3 Outstation for testing without pydnp3"""
    
    def __init__(self, port):
        self.port = port
        self.running = False
        
    def start(self):
        self.running = True
        logger.info(f"Mock DNP3 Outstation listening on port {self.port}")
        
    def stop(self):
        self.running = False


class DNP3OutstationRTU:
    """DNP3 Outstation RTU for SCADA communication"""
    
    def __init__(self, rtu_id, rtu_name, dnp3_port, outstation_addr, 
                 min_voltage, max_voltage, min_current, max_current,
                 min_freq, max_freq, min_temp, max_temp, poll_interval=5):
        
        self.rtu_id = rtu_id
        self.rtu_name = rtu_name
        self.dnp3_port = dnp3_port
        self.outstation_addr = outstation_addr
        self.poll_interval = poll_interval
        self.running = False
        
        # Initialize transformer simulator
        self.simulator = TransformerSimulator(
            rtu_id, min_voltage, max_voltage, min_current, max_current,
            min_freq, max_freq, min_temp, max_temp
        )
        
        # Initialize DNP3 outstation
        if opendnp3:
            self.outstation = self._init_dnp3_outstation()
        else:
            self.outstation = MockDNP3Outstation(dnp3_port)
            
        self.measurement_history = []
        
    def _init_dnp3_outstation(self):
        """Initialize actual DNP3 outstation"""
        try:
            log_handler = asiodnp3.ConsoleLogger().Create()
            manager = asiodnp3.DNP3Manager(1, log_handler)
            
            retry = asiopal.ChannelRetry().Default()
            listener = asiodnp3.PrintingChannelListener().Create()
            
            channel = manager.AddTCPServer(
                'outstation',
                opendnp3.levels.NOTHING,
                listener,
                '0.0.0.0',
                self.dnp3_port
            )
            
            config = asiodnp3.OutstationStackConfig()
            config.outstation.nodeName = self.rtu_name
            config.outstation.masterAddress = 1
            config.outstation.outstationAddress = self.outstation_addr
            
            outstation = channel.AddOutstation('outstation', asiodnp3.DefaultOutstationApplication().Create(), config)
            outstation.Enable()
            
            logger.info(f"DNP3 Outstation initialized on port {self.dnp3_port}")
            return outstation
            
        except Exception as e:
            logger.error(f"Failed to initialize DNP3: {e}")
            return MockDNP3Outstation(self.dnp3_port)
    
    def update_measurements(self):
        """Update and log measurements"""
        measurements = self.simulator.get_measurements()
        self.measurement_history.append(measurements)
        
        # Keep only last 100 measurements in memory
        if len(self.measurement_history) > 100:
            self.measurement_history = self.measurement_history[-100:]
        
        # Log to file
        log_file = f"/app/logs/rtu_{self.rtu_id}_measurements.json"
        try:
            with open(log_file, 'a') as f:
                f.write(json.dumps(measurements) + '\n')
        except Exception as e:
            logger.error(f"Failed to write measurements: {e}")
        
        logger.info(f"RTU {self.rtu_id}: V={measurements['voltage']}V, "
                   f"I={measurements['current']}A, F={measurements['frequency']}Hz, "
                   f"T={measurements['temperature']}°C, Load={measurements['load_percentage']}%")
        
        return measurements
    
    def start(self):
        """Start the RTU"""
        self.running = True
        logger.info(f"Starting RTU {self.rtu_id} - {self.rtu_name}")
        
        if self.outstation:
            self.outstation.start()
        
        # Start measurement update thread
        measurement_thread = Thread(target=self._measurement_loop, daemon=True)
        measurement_thread.start()
    
    def _measurement_loop(self):
        """Periodically update measurements"""
        while self.running:
            try:
                self.update_measurements()
                time.sleep(self.poll_interval)
            except Exception as e:
                logger.error(f"Error in measurement loop: {e}")
    
    def stop(self):
        """Stop the RTU"""
        self.running = False
        logger.info(f"Stopping RTU {self.rtu_id}")


def main():
    """Main function to run RTU simulator"""
    
    # Get configuration from environment
    rtu_id = int(os.getenv('RTU_ID', 1))
    rtu_name = os.getenv('RTU_NAME', f'Substation_{rtu_id}')
    dnp3_port = int(os.getenv('DNP3_PORT', 20000))
    outstation_addr = int(os.getenv('OUTSTATION_ADDR', 10))
    min_voltage = float(os.getenv('MIN_VOLTAGE', 380))
    max_voltage = float(os.getenv('MAX_VOLTAGE', 420))
    min_current = float(os.getenv('MIN_CURRENT', 100))
    max_current = float(os.getenv('MAX_CURRENT', 800))
    min_freq = float(os.getenv('MIN_FREQ', 59.8))
    max_freq = float(os.getenv('MAX_FREQ', 60.2))
    min_temp = float(os.getenv('MIN_TEMP', 20))
    max_temp = float(os.getenv('MAX_TEMP', 85))
    poll_interval = int(os.getenv('POLL_INTERVAL', 5))
    
    logger.info(f"Initializing RTU {rtu_id}: {rtu_name}")
    logger.info(f"Configuration: Port={dnp3_port}, Addr={outstation_addr}")
    
    # Create and start RTU
    rtu = DNP3OutstationRTU(
        rtu_id, rtu_name, dnp3_port, outstation_addr,
        min_voltage, max_voltage, min_current, max_current,
        min_freq, max_freq, min_temp, max_temp, poll_interval
    )
    
    rtu.start()
    
    try:
        # Keep running
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        logger.info("Received interrupt signal")
        rtu.stop()


if __name__ == '__main__':
    main()
