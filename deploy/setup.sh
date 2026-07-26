#!/usr/bin/env bash
# ==============================================================================
# setup.sh — Automated server installation script for AI Caller (Ubuntu/Debian)
# ==============================================================================
set -euo pipefail

echo "========================================================"
echo "  AI Caller — Server Setup Script"
echo "========================================================"

# Update system packages
sudo apt-get update -y
sudo apt-get install -y python3 python3-pip python3-venv ffmpeg git curl

# Set up project directory
PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$PROJECT_DIR"

# Install Python requirements
echo "[1/3] Installing Python dependencies..."
python3 -m pip install --upgrade pip
python3 -m pip install -r requirements.txt
python3 -m pip install -r agent/requirements.txt
python3 -m pip install livekit-api aiohttp

# Copy systemd service file
echo "[2/3] Setting up systemd service..."
sudo cp deploy/ai-caller.service /etc/systemd/system/ai-caller.service
sudo systemctl daemon-reload
sudo systemctl enable ai-caller

echo "[3/3] Setup completed successfully! ✓"
echo ""
echo "To start the service:"
echo "  sudo systemctl start ai-caller"
echo ""
echo "To check status & logs:"
echo "  sudo systemctl status ai-caller"
echo "  journalctl -u ai-caller -f"
