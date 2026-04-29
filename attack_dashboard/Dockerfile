FROM python:3.10-slim

WORKDIR /app

RUN pip install flask requests pymodbus==3.5.0 docker

# Ensure docker CLI is installed so we can run docker network commands
RUN apt-get update && apt-get install -y docker.io

COPY . /app

CMD ["python", "app.py"]
