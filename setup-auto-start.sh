#!/bin/bash

# Script untuk setup automatic startup ProDS System
# Jalankan dengan: sudo bash setup-auto-start.sh

set -e

echo "=========================================="
echo "Setup Automatic Startup ProDS System"
echo "=========================================="

# Check if running as root
if [ "$EUID" -ne 0 ]; then 
    echo "❌ Silakan jalankan script ini dengan sudo"
    echo "   Contoh: sudo bash setup-auto-start.sh"
    exit 1
fi

PROJECT_DIR="/app/ProDS-System"
BACKEND_SERVICE="prods-backend.service"
FRONTEND_SERVICE="prods-frontend.service"

# Check if project directory exists
if [ ! -d "$PROJECT_DIR" ]; then
    echo "❌ Directory $PROJECT_DIR tidak ditemukan!"
    exit 1
fi

echo ""
echo "📦 Menginstall systemd services..."

# Copy service files to systemd directory
cp "$PROJECT_DIR/backend/$BACKEND_SERVICE" /etc/systemd/system/
cp "$PROJECT_DIR/frontend/$FRONTEND_SERVICE" /etc/systemd/system/

# Reload systemd
systemctl daemon-reload

echo ""
echo "✅ Service files telah diinstall"
echo ""

# Check if Python3 exists
if ! command -v python3 &> /dev/null; then
    echo "⚠️  Python3 tidak ditemukan. Pastikan Python3 sudah terinstall."
fi

# Check if npm exists
if ! command -v npm &> /dev/null; then
    echo "⚠️  npm tidak ditemukan. Pastikan Node.js sudah terinstall."
fi

# Enable services to start on boot
echo "🔧 Mengaktifkan services untuk startup otomatis..."
systemctl enable $BACKEND_SERVICE
systemctl enable $FRONTEND_SERVICE

echo ""
echo "✅ Services telah diaktifkan untuk startup otomatis"
echo ""

# Ask if user wants to start services now
read -p "🚀 Apakah Anda ingin menjalankan services sekarang? (y/n): " -n 1 -r
echo
if [[ $REPLY =~ ^[Yy]$ ]]; then
    echo ""
    echo "🔄 Menjalankan services..."
    systemctl start $BACKEND_SERVICE
    systemctl start $FRONTEND_SERVICE
    
    echo ""
    echo "⏳ Menunggu services untuk start..."
    sleep 3
    
    # Check status
    echo ""
    echo "📊 Status Backend:"
    systemctl status $BACKEND_SERVICE --no-pager -l
    
    echo ""
    echo "📊 Status Frontend:"
    systemctl status $FRONTEND_SERVICE --no-pager -l
fi

echo ""
echo "=========================================="
echo "✅ Setup selesai!"
echo "=========================================="
echo ""
echo "📝 Perintah yang berguna:"
echo "   - Start services:   sudo systemctl start $BACKEND_SERVICE $FRONTEND_SERVICE"
echo "   - Stop services:    sudo systemctl stop $BACKEND_SERVICE $FRONTEND_SERVICE"
echo "   - Restart services: sudo systemctl restart $BACKEND_SERVICE $FRONTEND_SERVICE"
echo "   - Check status:     sudo systemctl status $BACKEND_SERVICE"
echo "   - View logs:        sudo journalctl -u $BACKEND_SERVICE -f"
echo "   - View logs:        sudo journalctl -u $FRONTEND_SERVICE -f"
echo ""

