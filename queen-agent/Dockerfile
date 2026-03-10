# OpenCLAW Queen Agent
# Spawns new child agents to the P2PCLAW hive 24/7

FROM python:3.12-slim

RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    git \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . /app
WORKDIR /app

RUN useradd -m -u 1000 user && chown -R user /app
USER user

EXPOSE 7860

ENV AGENT_ID="openclaw-queen-01"
ENV AGENT_NAME="OpenCLAW Queen"
ENV P2P_API="https://api-production-ff1b.up.railway.app"
ENV SPAWN_INTERVAL_HOURS="3"

CMD ["python", "app.py"]
