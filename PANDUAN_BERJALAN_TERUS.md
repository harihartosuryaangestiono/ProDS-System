# 🚀 Panduan Agar Web Berjalan Terus

Panduan lengkap untuk memastikan ProDS System berjalan otomatis dan terus-menerus.

## ✅ Status Saat Ini

Berdasarkan verifikasi:
- ✅ **Backend Service**: `active (running)` - Port 5000 listening
- ✅ **API Endpoint**: Merespons dengan baik
- ✅ **Dependencies**: Semua terinstall dengan benar
- ✅ **Service File**: Sudah dikonfigurasi dengan benar

---

## 📋 Checklist Final - Pastikan Semua Sudah Benar

### 1. Verifikasi Backend Service Enabled untuk Auto-Start

```bash
# Cek apakah service enabled untuk auto-start saat boot
sudo systemctl is-enabled prods-backend.service

# Jika belum enabled, enable sekarang:
sudo systemctl enable prods-backend.service

# Verifikasi status
sudo systemctl status prods-backend.service
```

**Harus menampilkan:** `enabled` dan `Active: active (running)`

---

### 2. Setup Frontend Service (Jika Belum)

```bash
# Cek apakah frontend service sudah ada
sudo systemctl status prods-frontend.service

# Jika service belum ada, jalankan setup:
cd /app/ProDS-System
sudo bash setup-auto-start.sh
```

**Pastikan frontend service juga:**
- ✅ Status: `active (running)`
- ✅ Enabled: `enabled` (auto-start saat boot)
- ✅ Port 3000 listening

---

### 3. Verifikasi Kedua Service Enabled

```bash
# Cek kedua service sekaligus
sudo systemctl is-enabled prods-backend.service prods-frontend.service

# Jika ada yang belum enabled:
sudo systemctl enable prods-backend.service
sudo systemctl enable prods-frontend.service
```

**Harus menampilkan:**
```
enabled
enabled
```

---

### 4. Test Auto-Restart (Optional)

Test apakah service bisa auto-restart jika crash:

```bash
# Simulasi crash backend
sudo systemctl status prods-backend.service | grep "Main PID" | awk '{print $3}' | xargs sudo kill -9

# Tunggu 10-15 detik
sleep 15

# Cek status - harus otomatis restart
sudo systemctl status prods-backend.service
```

**Harus:** Service otomatis restart dan kembali `active (running)`

---

### 5. Test Reboot (Optional - Hati-hati!)

**⚠️ PERINGATAN:** Hanya lakukan jika Anda yakin server bisa di-reboot!

```bash
# Reboot server
sudo reboot

# Setelah reboot, cek status (tunggu server selesai boot)
sudo systemctl status prods-backend.service
sudo systemctl status prods-frontend.service
```

**Harus:** Kedua service otomatis start setelah reboot

---

## 🎯 Perintah Penting untuk Maintenance

### Cek Status Semua Service

```bash
# Status backend
sudo systemctl status prods-backend.service

# Status frontend
sudo systemctl status prods-frontend.service

# Status keduanya sekaligus
sudo systemctl status prods-backend.service prods-frontend.service
```

### Start/Stop/Restart Services

```bash
# Start semua service
sudo systemctl start prods-backend.service prods-frontend.service

# Stop semua service
sudo systemctl stop prods-backend.service prods-frontend.service

# Restart semua service
sudo systemctl restart prods-backend.service prods-frontend.service
```

### Lihat Logs

```bash
# Backend logs (real-time)
sudo journalctl -u prods-backend.service -f

# Frontend logs (real-time)
sudo journalctl -u prods-frontend.service -f

# Logs terakhir (50 baris)
sudo journalctl -u prods-backend.service -n 50
sudo journalctl -u prods-frontend.service -n 50
```

### Cek Port Listening

```bash
# Cek port backend (5000) dan frontend (3000)
sudo ss -tlnp | grep -E "(5000|3000)"
```

**Harus menampilkan:**
- Port 5000: Backend listening
- Port 3000: Frontend listening

---

## 🔄 Setelah Update Code

Jika Anda update code aplikasi:

```bash
# Restart kedua service
sudo systemctl restart prods-backend.service prods-frontend.service

# Cek status
sudo systemctl status prods-backend.service prods-frontend.service
```

---

## 🔄 Setelah Update Dependencies

### Backend Dependencies

```bash
cd /app/ProDS-System/backend

# Install dependencies untuk root (karena service berjalan sebagai root)
sudo pip3 install -r requirements.txt

# Restart service
sudo systemctl restart prods-backend.service

# Cek status
sudo systemctl status prods-backend.service
```

### Frontend Dependencies

```bash
cd /app/ProDS-System/frontend

# Install dependencies
npm install

# Restart service
sudo systemctl restart prods-frontend.service

# Cek status
sudo systemctl status prods-frontend.service
```

---

## 🐛 Troubleshooting

### Service Tidak Start Setelah Reboot?

1. **Cek apakah service enabled:**
   ```bash
   sudo systemctl is-enabled prods-backend.service
   ```

2. **Enable service:**
   ```bash
   sudo systemctl enable prods-backend.service
   sudo systemctl enable prods-frontend.service
   ```

3. **Cek logs untuk error:**
   ```bash
   sudo journalctl -u prods-backend.service -n 100
   ```

### Service Crash Terus?

1. **Cek logs detail:**
   ```bash
   sudo journalctl -u prods-backend.service -n 100 --no-pager
   ```

2. **Cek dependencies:**
   ```bash
   sudo python3 -c "import flask; print('OK')"
   ```

3. **Cek database:**
   ```bash
   sudo systemctl status postgresql
   ```

### Port Sudah Digunakan?

```bash
# Gunakan script fix
sudo bash /app/ProDS-System/fix-port-conflict.sh
```

---

## ✅ Checklist Final - Pastikan Semua

Sebelum yakin web berjalan terus, pastikan:

- [ ] Backend service: `active (running)`
- [ ] Frontend service: `active (running)` (jika ada)
- [ ] Backend service: `enabled` (auto-start saat boot)
- [ ] Frontend service: `enabled` (auto-start saat boot)
- [ ] Port 5000: Listening (backend)
- [ ] Port 3000: Listening (frontend, jika ada)
- [ ] API endpoint: Merespons (`curl http://localhost:5000/`)
- [ ] Logs: Tidak ada error yang terus muncul

---

## 🎉 Setelah Semua Checklist ✅

**Aplikasi Anda sekarang akan:**
- ✅ **Otomatis start** saat server boot
- ✅ **Otomatis restart** jika crash
- ✅ **Berjalan terus** tanpa perlu buka IDE atau terminal
- ✅ **Logs tersimpan** di systemd journal

**Tidak perlu melakukan apa-apa lagi!** Aplikasi akan berjalan otomatis.

---

## 📝 Catatan Penting

1. **Jangan jalankan aplikasi manual** (misalnya `python3 app.py` atau `npm start`) karena akan conflict dengan systemd service

2. **Gunakan systemctl** untuk manage service:
   - `sudo systemctl start/stop/restart prods-backend.service`
   - Jangan kill process secara manual

3. **Cek logs secara berkala** untuk memastikan tidak ada error:
   ```bash
   sudo journalctl -u prods-backend.service -n 50
   ```

4. **Setelah update code**, selalu restart service:
   ```bash
   sudo systemctl restart prods-backend.service prods-frontend.service
   ```

---

## 🔗 Akses Aplikasi

Setelah semua setup:
- **Backend API**: `http://10.211.1.188:5000` atau `http://localhost:5000`
- **Frontend**: `http://10.211.1.188:3000` atau `http://localhost:3000` (jika ada)

---

**Selamat! Aplikasi Anda sekarang berjalan otomatis dan akan terus berjalan! 🚀**

