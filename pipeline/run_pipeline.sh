#!/bin/bash

cd "$(dirname "$0")/.." || exit 1

echo "=== [$(date)] Starting Spotify Pipeline Update & Run ==="

echo "Pulling latest code from git..."
git pull origin main

echo "activating virtual environment"
source .venv/bin/activate

echo "syncing dependencies"
pip install -r pipeline/requirements.txt

echo "running spotify ingestion script"
python pipeline/main.py

