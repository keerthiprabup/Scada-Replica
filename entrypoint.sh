#!/bin/bash
set -e

# Configure Wazuh if MANAGER_IP is set
if [ ! -z "$WAZUH_MANAGER_IP" ]; then
    echo "Configuring Wazuh Agent to connect to $WAZUH_MANAGER_IP"
    
    # Update manager IP in ossec.conf
    # Update manager IP in ossec.conf - Replace any existing address
    sed -i "s|<address>.*</address>|<address>$WAZUH_MANAGER_IP</address>|g" /var/ossec/etc/ossec.conf
    
    # Add configuration to monitor app logs
    # We append this to ossec.conf before the last </ossec_config>
    sed -i '/<\/ossec_config>/i \
  <localfile>\
    <location>/app/log.json</location>\
    <log_format>json</log_format>\
  </localfile>' /var/ossec/etc/ossec.conf

    # Start Wazuh Agent (using service or direct binary)
    # Since we are in docker, we might not have systemd. Use direct init script if available or binary.
    # /var/ossec/bin/wazuh-control start
    /etc/init.d/wazuh-agent start
fi

# Run the main application
exec "$@"
