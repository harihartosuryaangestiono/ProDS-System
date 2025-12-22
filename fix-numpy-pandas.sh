#!/bin/bash

# Script untuk fix numpy-pandas compatibility issue
# Jalankan dengan: sudo bash fix-numpy-pandas.sh

set -e

echo "=========================================="
echo "Fix Numpy-Pandas Compatibility Issue"
echo "=========================================="

# Check if running as root
if [ "$EUID" -ne 0 ]; then 
    echo "❌ Silakan jalankan script ini dengan sudo"
    echo "   Contoh: sudo bash fix-numpy-pandas.sh"
    exit 1
fi

echo ""
echo "🔍 Mengecek versi numpy dan pandas..."

# Check current versions
NUMPY_VERSION=$(python3 -c "import numpy; print(numpy.__version__)" 2>/dev/null || echo "not installed")
PANDAS_VERSION=$(python3 -c "import pandas; print(pandas.__version__)" 2>/dev/null || echo "not installed")

echo "   numpy: $NUMPY_VERSION"
echo "   pandas: $PANDAS_VERSION"

echo ""
echo "📦 Memperbaiki kompatibilitas numpy-pandas..."

# Uninstall numpy and pandas first
echo "   Uninstalling numpy dan pandas..."
pip3 uninstall -y numpy pandas 2>/dev/null || true

# Install compatible versions
# Pandas 2.0.3 requires numpy >= 1.20.3 and < 2.0.0
echo "   Installing numpy < 2.0.0 (compatible with pandas 2.0.3)..."
pip3 install "numpy<2.0.0,>=1.20.3"

echo "   Installing pandas 2.0.3..."
pip3 install pandas==2.0.3

echo ""
echo "✅ Numpy dan pandas telah di-reinstall dengan versi yang kompatibel"

# Verify
echo ""
echo "🔍 Verifikasi..."
python3 -c "import numpy; import pandas; print('✅ numpy:', numpy.__version__); print('✅ pandas:', pandas.__version__); print('✅ Import berhasil!')" || {
    echo "❌ Masih ada masalah dengan import"
    exit 1
}

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
echo "=========================================="
echo "✅ Fix selesai!"
echo "=========================================="
echo ""
echo "📝 Cek logs jika ada masalah:"
echo "   sudo journalctl -u prods-backend.service -n 50"
echo ""

