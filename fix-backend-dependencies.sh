#!/bin/bash

# Script untuk fix backend service - Install dependencies untuk root
# Jalankan dengan: sudo bash fix-backend-dependencies.sh

set -e

echo "=========================================="
echo "Fix Backend Service - Install Dependencies"
echo "=========================================="

# Check if running as root
if [ "$EUID" -ne 0 ]; then 
    echo "❌ Silakan jalankan script ini dengan sudo"
    echo "   Contoh: sudo bash fix-backend-dependencies.sh"
    exit 1
fi

PROJECT_DIR="/app/ProDS-System"
BACKEND_DIR="$PROJECT_DIR/backend"

echo ""
echo "📦 Menginstall Python dependencies untuk root user..."

# Install dependencies
cd "$BACKEND_DIR"
pip3 install -r requirements.txt

echo ""
echo "✅ Dependencies telah terinstall"
echo ""

echo "🔄 Mengupdate service file..."
# Copy service file
cp "$BACKEND_DIR/prods-backend.service" /etc/systemd/system/
systemctl daemon-reload

echo ""
echo "✅ Service file telah di-update"
echo ""

echo "🚀 Menjalankan backend service..."
systemctl restart prods-backend.service

echo ""
echo "⏳ Menunggu service untuk start..."
sleep 5

echo ""
echo "📊 Status Backend:"
systemctl status prods-backend.service --no-pager -l

echo ""
echo "=========================================="
echo "✅ Fix selesai!"
echo "=========================================="
echo ""
echo "📝 Cek logs jika ada masalah:"
echo "   sudo journalctl -u prods-backend.service -n 50"
echo ""

