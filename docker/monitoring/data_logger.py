#!/usr/bin/env python3
"""
Data Logger and Monitoring Service for SCADA Testbed
Logs all measurements and provides monitoring dashboard API
"""

import os
import json
import logging
import time
import requests
from datetime import datetime
from threading import Thread
from flask import Flask, jsonify
from collections import defaultdict

# Configure logging
logging.basicConfig(
    level=os.getenv('LOG_LEVEL', 'INFO'),
    format='%(asctime)s - DataLogger - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

app = Flask(__name__)

class DataLogger:
    """Logs and monitors SCADA data"""
    
    def __init__(self, scada_server_url, poll_interval=5):
        self.scada_server_url = scada_server_url
        self.poll_interval = poll_interval
        self.running = False
        self.stats = defaultdict(lambda: {
            'total_records': 0,
            'errors': 0,
            'last_update': None,
            'min_values': {},
            'max_values': {},
            'avg_values': {}
        })
        self.log_path = os.getenv('LOG_PATH', '/app/logs')
        
    def poll_scada_server(self):
        """Poll SCADA server for data"""
        try:
            response = requests.get(f"{self.scada_server_url}/api/status", timeout=5)
            if response.status_code == 200:
                data = response.json()
                self._process_measurements(data)
                return data
            else:
                logger.warning(f"SCADA server returned status {response.status_code}")
                self.stats['global']['errors'] += 1
        except requests.exceptions.RequestException as e:
            logger.error(f"Failed to connect to SCADA server: {e}")
            self.stats['global']['errors'] += 1
        
        return None
    
    def _process_measurements(self, data):
        """Process and log measurements"""
        timestamp = datetime.now().isoformat()
        
        # Log overall status
        status_log = {
            'timestamp': timestamp,
            'data': data
        }
        
        status_file = os.path.join(self.log_path, 'scada_status.jsonl')
        try:
            with open(status_file, 'a') as f:
                f.write(json.dumps(status_log) + '\n')
        except Exception as e:
            logger.error(f"Failed to write status log: {e}")
        
        # Update stats
        self.stats['global']['total_records'] += 1
        self.stats['global']['last_update'] = timestamp
        
        logger.info(f"Logged system status at {timestamp}")
    
    def get_statistics(self):
        """Get statistics for monitoring"""
        return {
            'timestamp': datetime.now().isoformat(),
            'log_path': self.log_path,
            'poll_interval': self.poll_interval,
            'stats': dict(self.stats)
        }
    
    def start(self):
        """Start the data logger"""
        self.running = True
        logger.info("Starting Data Logger")
        
        # Start polling thread
        polling_thread = Thread(target=self._polling_loop, daemon=True)
        polling_thread.start()
    
    def _polling_loop(self):
        """Periodically poll and log SCADA data"""
        while self.running:
            try:
                self.poll_scada_server()
                time.sleep(self.poll_interval)
            except Exception as e:
                logger.error(f"Error in polling loop: {e}")
    
    def stop(self):
        """Stop the data logger"""
        self.running = False
        logger.info("Stopping Data Logger")


# Initialize Data Logger
scada_server_url = os.getenv('SCADA_SERVER_URL', 'http://scada-master:8080')
poll_interval = int(os.getenv('POLL_INTERVAL', 5))
data_logger = DataLogger(scada_server_url, poll_interval)


# REST API Endpoints

@app.route('/api/stats', methods=['GET'])
def get_stats():
    """Get logging statistics"""
    return jsonify(data_logger.get_statistics())


@app.route('/api/health', methods=['GET'])
def health():
    """Health check endpoint"""
    return jsonify({'status': 'healthy', 'timestamp': datetime.now().isoformat()})


@app.route('/api/logs', methods=['GET'])
def get_logs():
    """Get recent log entries"""
    limit = request.args.get('limit', 50, type=int)
    
    try:
        log_file = os.path.join(data_logger.log_path, 'scada_status.jsonl')
        if os.path.exists(log_file):
            with open(log_file, 'r') as f:
                lines = f.readlines()
                recent_logs = [json.loads(line) for line in lines[-limit:]]
            return jsonify({'logs': recent_logs, 'count': len(recent_logs)})
    except Exception as e:
        logger.error(f"Error reading logs: {e}")
    
    return jsonify({'logs': [], 'count': 0})


def main():
    """Main function to run data logger"""
    logger.info("Initializing Data Logger")
    
    data_logger.start()
    
    # Run Flask app
    api_port = int(os.getenv('MONITORING_PORT', 8081))
    logger.info(f"Starting Monitoring API on port {api_port}")
    
    try:
        app.run(host='0.0.0.0', port=api_port, debug=False)
    except KeyboardInterrupt:
        logger.info("Received interrupt signal")
        data_logger.stop()


if __name__ == '__main__':
    main()
