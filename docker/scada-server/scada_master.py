#!/usr/bin/env python3
"""
DNP3 Master SCADA Server for SCADA Testbed
Polls multiple RTU/IED outstations and provides REST API
"""

import os
import json
import logging
import time
from datetime import datetime
from threading import Thread
from collections import defaultdict
from flask import Flask, jsonify, request

# Configure logging
logging.basicConfig(
    level=os.getenv('LOG_LEVEL', 'INFO'),
    format='%(asctime)s - SCADA-Master - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

app = Flask(__name__)

class SCADAMasterServer:
    """DNP3 Master SCADA Server"""
    
    def __init__(self):
        self.master_id = int(os.getenv('MASTER_ID', 1))
        self.outstations = {}
        self.measurement_data = defaultdict(list)
        self.last_update = {}
        self.running = False
        self.poll_interval = int(os.getenv('POLL_INTERVAL', 5))
        
        # Configure outstations
        self._configure_outstations()
        
    def _configure_outstations(self):
        """Configure outstation connections"""
        # Outstation 1
        self.outstations[1] = {
            'name': 'Substation_1',
            'host': os.getenv('OUTSTATION_1_HOST', 'rtu-substation-1'),
            'port': int(os.getenv('OUTSTATION_1_PORT', 20000)),
            'address': int(os.getenv('OUTSTATION_1_ADDR', 10)),
            'connection_status': 'DISCONNECTED'
        }
        
        # Outstation 2
        self.outstations[2] = {
            'name': 'Substation_2',
            'host': os.getenv('OUTSTATION_2_HOST', 'rtu-substation-2'),
            'port': int(os.getenv('OUTSTATION_2_PORT', 20001)),
            'address': int(os.getenv('OUTSTATION_2_ADDR', 11)),
            'connection_status': 'DISCONNECTED'
        }
        
        logger.info(f"Configured {len(self.outstations)} outstations")
    
    def poll_outstations(self):
        """Poll all outstations for measurements"""
        for outstation_id, config in self.outstations.items():
            try:
                # Simulate polling - in production, would use real DNP3 library
                logger.info(f"Polling outstation {outstation_id}: {config['name']}")
                
                # Update connection status
                self.outstations[outstation_id]['connection_status'] = 'CONNECTED'
                self.last_update[outstation_id] = datetime.now().isoformat()
                
            except Exception as e:
                logger.error(f"Error polling outstation {outstation_id}: {e}")
                self.outstations[outstation_id]['connection_status'] = 'ERROR'
    
    def read_measurements_from_log(self, rtu_id):
        """Read latest measurements from RTU log file"""
        try:
            log_file = f"/app/logs/rtu_{rtu_id}_measurements.json"
            if os.path.exists(log_file):
                with open(log_file, 'r') as f:
                    lines = f.readlines()
                    if lines:
                        latest = json.loads(lines[-1])
                        self.measurement_data[rtu_id].append(latest)
                        
                        # Keep only last 1000 measurements
                        if len(self.measurement_data[rtu_id]) > 1000:
                            self.measurement_data[rtu_id] = self.measurement_data[rtu_id][-1000:]
                        
                        return latest
        except Exception as e:
            logger.error(f"Error reading measurements from RTU {rtu_id}: {e}")
        
        return None
    
    def get_current_status(self):
        """Get current system status"""
        status = {
            'master_id': self.master_id,
            'timestamp': datetime.now().isoformat(),
            'outstations': {}
        }
        
        for rtu_id, config in self.outstations.items():
            measurement = self.read_measurements_from_log(rtu_id)
            status['outstations'][rtu_id] = {
                'name': config['name'],
                'host': config['host'],
                'port': config['port'],
                'connection_status': config['connection_status'],
                'last_update': self.last_update.get(rtu_id),
                'latest_measurement': measurement
            }
        
        return status
    
    def start(self):
        """Start the SCADA master server"""
        self.running = True
        logger.info(f"Starting SCADA Master {self.master_id}")
        
        # Start polling thread
        polling_thread = Thread(target=self._polling_loop, daemon=True)
        polling_thread.start()
    
    def _polling_loop(self):
        """Periodically poll outstations"""
        while self.running:
            try:
                self.poll_outstations()
                time.sleep(self.poll_interval)
            except Exception as e:
                logger.error(f"Error in polling loop: {e}")
    
    def stop(self):
        """Stop the SCADA master server"""
        self.running = False
        logger.info("Stopping SCADA Master")


# Initialize SCADA Master
scada_master = SCADAMasterServer()


# REST API Endpoints

@app.route('/api/status', methods=['GET'])
def get_status():
    """Get current system status"""
    return jsonify(scada_master.get_current_status())


@app.route('/api/outstation/<int:outstation_id>', methods=['GET'])
def get_outstation(outstation_id):
    """Get specific outstation data"""
    status = scada_master.get_current_status()
    if outstation_id in status['outstations']:
        return jsonify(status['outstations'][outstation_id])
    return jsonify({'error': 'Outstation not found'}), 404


@app.route('/api/measurements/<int:rtu_id>', methods=['GET'])
def get_measurements(rtu_id):
    """Get measurements history for RTU"""
    measurements = scada_master.measurement_data.get(rtu_id, [])
    
    # Support pagination
    limit = request.args.get('limit', 100, type=int)
    offset = request.args.get('offset', 0, type=int)
    
    return jsonify({
        'rtu_id': rtu_id,
        'total_records': len(measurements),
        'limit': limit,
        'offset': offset,
        'measurements': measurements[offset:offset+limit]
    })


@app.route('/api/health', methods=['GET'])
def health():
    """Health check endpoint"""
    return jsonify({'status': 'healthy', 'timestamp': datetime.now().isoformat()})


@app.route('/api/config', methods=['GET'])
def get_config():
    """Get SCADA master configuration"""
    return jsonify({
        'master_id': scada_master.master_id,
        'poll_interval': scada_master.poll_interval,
        'outstations': [
            {
                'id': oid,
                'name': config['name'],
                'host': config['host'],
                'port': config['port'],
                'address': config['address']
            }
            for oid, config in scada_master.outstations.items()
        ]
    })


@app.errorhandler(404)
def not_found(error):
    """Handle 404 errors"""
    return jsonify({'error': 'Endpoint not found'}), 404


@app.errorhandler(500)
def internal_error(error):
    """Handle 500 errors"""
    logger.error(f"Internal server error: {error}")
    return jsonify({'error': 'Internal server error'}), 500


def main():
    """Main function to run SCADA master server"""
    logger.info("Initializing SCADA Master Server")
    
    scada_master.start()
    
    # Run Flask app
    api_port = int(os.getenv('API_PORT', 8080))
    logger.info(f"Starting Flask API on port {api_port}")
    
    try:
        app.run(host='0.0.0.0', port=api_port, debug=False)
    except KeyboardInterrupt:
        logger.info("Received interrupt signal")
        scada_master.stop()


if __name__ == '__main__':
    main()
