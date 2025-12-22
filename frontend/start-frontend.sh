#!/bin/bash
set -euo pipefail

cd /app/ProDS-System/frontend

echo "[frontend] Starting UNPAR Scraper frontend..."
echo "[frontend] Node: $(node -v 2>/dev/null || echo 'not found')"
echo "[frontend] NPM:  $(npm -v 2>/dev/null || echo 'not found')"

# Ensure dependencies exist (vite is a devDependency, needed for build)
if [ ! -d "node_modules" ]; then
  echo "[frontend] node_modules not found; installing dependencies..."
  npm install --no-audit --no-fund
fi

# Ensure production build exists
if [ ! -d "dist" ]; then
  echo "[frontend] dist/ not found; building..."
  npm run build
fi

echo "[frontend] Serving production build on 0.0.0.0:3000"
exec npm run preview -- --host 0.0.0.0 --port 3000 --strictPort


