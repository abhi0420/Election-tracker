#!/bin/bash
# Start script for Render deployment

# Ensure gunicorn is in PATH
export PATH="$PATH:/opt/render/project/src/.venv/bin"

# Use python -m to run gunicorn
exec python -m gunicorn map_app:app --bind 0.0.0.0:$PORT --workers 1 --threads 2


