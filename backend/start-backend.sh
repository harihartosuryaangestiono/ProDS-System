#!/bin/bash

# ProDS System Backend Startup Script
# This script starts the Flask backend application

set -e

# Change to backend directory
cd /app/ProDS-System/backend

# Set environment variables if not already set
export FLASK_ENV=${FLASK_ENV:-production}
export PORT=${PORT:-5000}

# Activate virtual environment if it exists
if [ -d "venv" ]; then
    source venv/bin/activate
fi

# Run the Flask application
exec python3 app.py
