FROM python:3.9-slim

# Install dependencies for adding repos and Wazuh Agent
RUN apt-get update && apt-get install -y \
    curl \
    gnupg \
    lsb-release \
    procps \
    apt-transport-https \
    && rm -rf /var/lib/apt/lists/*

# Add Wazuh repo and install agent
# RUN curl -s https://packages.wazuh.com/key/GPG-KEY-WAZUH | gpg --no-default-keyring --keyring gnupg-ring:/usr/share/keyrings/wazuh.gpg --import && \
#     chmod 644 /usr/share/keyrings/wazuh.gpg && \
#     echo "deb [signed-by=/usr/share/keyrings/wazuh.gpg] https://packages.wazuh.com/4.x/apt/ stable main" | tee -a /etc/apt/sources.list.d/wazuh.list && \
#     apt-get update && \
#     apt-get install -y wazuh-agent=4.7.2-1 && \
#     rm -rf /var/lib/apt/lists/*

# Install Python dependencies
RUN pip install pymodbus flask flask-cors

# Setup app directory
WORKDIR /app
COPY . .

# Ensure entrypoint is executable
RUN chmod +x ./entrypoint.sh

# Use entrypoint script
ENTRYPOINT ["/app/entrypoint.sh"]
