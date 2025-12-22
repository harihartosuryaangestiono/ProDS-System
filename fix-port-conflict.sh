#!/bin/bash

# Script untuk fix port conflict (port 5000 sudah digunakan)
# Jalankan dengan: sudo bash fix-port-conflict.sh

set -e

echo "=========================================="
echo "Fix Port Conflict - Port 5000"
echo "=========================================="

# Check if running as root
if [ "$EUID" -ne 0 ]; then 
    echo "❌ Silakan jalankan script ini dengan sudo"
    echo "   Contoh: sudo bash fix-port-conflict.sh"
    exit 1
fi

PORT=5000

echo ""
echo "🔍 Mencari process yang menggunakan port $PORT..."

# Find process using port 5000
PID=$(ss -tlnp | grep ":$PORT " | grep -oP 'pid=\K[0-9]+' | head -1)

if [ -z "$PID" ]; then
    echo "   ✅ Port $PORT tidak digunakan oleh process lain"
    echo ""
    echo "🔄 Restarting backend service..."
    systemctl restart prods-backend.service
    sleep 5
    systemctl status prods-backend.service --no-pager -l
    exit 0
fi

echo "   Ditemukan process PID: $PID"

# Get process info
PROCESS_INFO=$(ps -p $PID -o comm=,args= 2>/dev/null || echo "Process tidak ditemukan")

echo "   Process: $PROCESS_INFO"

echo ""
echo "🛑 Menghentikan process yang menggunakan port $PORT..."

# Kill the process
kill -9 $PID 2>/dev/null && echo "   ✅ Process dihentikan" || echo "   ⚠️  Gagal menghentikan process"

# Wait a bit
sleep 2

# Verify port is free
if ss -tlnp | grep -q ":$PORT "; then
    echo "   ⚠️  Port masih digunakan, mencoba force kill..."
    # Try to find and kill all python processes on port 5000
    fuser -k ${PORT}/tcp 2>/dev/null || true
    sleep 2
fi

echo ""
echo "🔄 Restarting backend service..."
systemctl restart prods-backend.service

echo ""
echo "⏳ Menunggu service untuk start..."
sleep 5

echo ""
echo "📊 Status Backend:"
systemctl status prods-backend.service --no-pager -l

echo ""
echo "🔍 Verifikasi port $PORT:"
ss -tlnp | grep ":$PORT " || echo "   ⚠️  Port $PORT tidak listening (cek logs untuk error)"

echo ""
echo "=========================================="
echo "✅ Fix selesai!"
echo "=========================================="
echo ""
echo "📝 Cek logs jika ada masalah:"
echo "   sudo journalctl -u prods-backend.service -n 50"
echo ""

