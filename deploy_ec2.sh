#!/bin/bash
# =============================================================================
# Traffic_plus — EC2 t4g.small (ARM64 / Ubuntu 24.04) bootstrap script
# Run once as ubuntu user after first SSH login:
#   bash deploy_ec2.sh
# =============================================================================
set -euo pipefail

echo "=== [1/6] System update ==="
sudo apt-get update -y
sudo apt-get upgrade -y
sudo apt-get install -y git curl unzip

echo "=== [2/6] Install Docker ==="
curl -fsSL https://get.docker.com | sudo sh
sudo usermod -aG docker ubuntu
# Apply group without re-login
newgrp docker <<'DOCKERGRP'

echo "=== [3/6] Install Docker Compose plugin ==="
sudo apt-get install -y docker-compose-plugin
docker compose version

echo "=== [4/6] Clone Traffic repository ==="
# Replace with your actual repo URL or use scp to upload
git clone https://github.com/YOUR_USERNAME/YOUR_REPO.git /home/ubuntu/traffic
cd /home/ubuntu/traffic/Traffic_plus

echo "=== [5/6] Create .env from template ==="
if [ ! -f .env ]; then
  cp .env.example .env
  # Generate a secure secret key
  SECRET=$(python3 -c "import secrets; print(secrets.token_hex(32))")
  INFLUX_TOKEN=$(python3 -c "import secrets; print(secrets.token_hex(32))")
  POSTGRES_PASS=$(python3 -c "import secrets; print(secrets.token_hex(16))")
  INFLUX_PASS=$(python3 -c "import secrets; print(secrets.token_hex(16))")

  sed -i "s|change-me-generate-a-real-key|$SECRET|g"    .env
  sed -i "s|INFLUX_TOKEN=change-me|INFLUX_TOKEN=$INFLUX_TOKEN|g" .env
  sed -i "s|INFLUXDB_ADMIN_TOKEN=change-me|INFLUXDB_ADMIN_TOKEN=$INFLUX_TOKEN|g" .env
  sed -i "s|INFLUXDB_ADMIN_PASSWORD=change-me|INFLUXDB_ADMIN_PASSWORD=$INFLUX_PASS|g" .env
  sed -i "s|PROFILE=balanced|PROFILE=balanced|g"        .env
  sed -i "s|CELERY_CONCURRENCY=4|CELERY_CONCURRENCY=2|g" .env  # conservative for 2GB RAM

  echo ""
  echo ">>> .env created. Edit it now to set POSTGRES_PASSWORD and CORS_ORIGINS."
  echo ">>> Press enter when ready to continue..."
  read -r
fi

echo "=== [6/6] Start Traffic_plus ==="
docker compose pull postgres redis influxdb  # pull pre-built images first
docker compose up -d --build

echo ""
echo "================================================"
echo "  Traffic_plus deployed!"
echo "  API:    http://$(curl -s ifconfig.me):8000"
echo "  Flower: http://$(curl -s ifconfig.me):5555"
echo ""
echo "  Next steps:"
echo "  1. Open port 8000 in EC2 Security Group"
echo "  2. Update TRAFFIC_PLUS_URL in your local .Renviron"
echo "  3. Run: docker compose logs -f celery_beat"
echo "================================================"
DOCKERGRP
