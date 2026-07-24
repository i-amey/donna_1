#!/usr/bin/env bash
# Fresh Ubuntu 24.04 -> ready for Hermes.
# Run as the default sudo user (ubuntu on AWS AMIs). Idempotent.
set -euo pipefail

echo "==> System update"
sudo apt-get update -y
sudo DEBIAN_FRONTEND=noninteractive apt-get upgrade -y

echo "==> Core dependencies"
# libopus0 + ffmpeg are required for any voice path.
# build-essential + python3.11 back the Hermes venv; nodejs backs the gateway bridges.
sudo apt-get install -y \
  build-essential git curl wget jq unzip \
  python3.11 python3.11-venv python3-pip \
  ffmpeg libopus0 libopus-dev \
  ripgrep ca-certificates

echo "==> Node.js 22"
if ! command -v node >/dev/null 2>&1; then
  curl -fsSL https://deb.nodesource.com/setup_22.x | sudo -E bash -
  sudo apt-get install -y nodejs
fi
node --version

echo "==> Docker (sandbox backend for Hermes shell tools)"
if ! command -v docker >/dev/null 2>&1; then
  sudo apt-get install -y docker.io
  sudo systemctl enable --now docker
  sudo usermod -aG docker "$USER"
  echo "    NOTE: log out and back in for docker group membership to apply."
fi

echo "==> Firewall"
sudo ufw allow OpenSSH
sudo ufw allow 80/tcp
sudo ufw allow 443/tcp
sudo ufw --force enable
sudo ufw status verbose

echo "==> Swap (protects a 2-4GB box from OOM kills during installs)"
if ! swapon --show | grep -q .; then
  sudo fallocate -l 2G /swapfile
  sudo chmod 600 /swapfile
  sudo mkswap /swapfile
  sudo swapon /swapfile
  echo '/swapfile none swap sw 0 0' | sudo tee -a /etc/fstab
fi
free -h

echo "==> Predictable updates"
sudo systemctl disable --now unattended-upgrades 2>/dev/null || true

echo
echo "Bootstrap complete. Next: scripts/01-install-hermes.sh"
