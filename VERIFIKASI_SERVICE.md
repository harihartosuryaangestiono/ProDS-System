# 🔍 Panduan Verifikasi Service ProDS System

Panduan step-by-step untuk memastikan backend service berjalan dengan benar setelah perbaikan.

## ✅ Step 1: Install Dependencies untuk Root User

**MASALAH:** Service berjalan sebagai `root`, tapi dependencies terinstall untuk user `unpar`.

**SOLUSI:** Install dependencies untuk root user:

```bash
cd /app/ProDS-System/backend
sudo pip3 install -r requirements.txt
```

**Atau gunakan script otomatis:**
```bash
sudo bash /app/ProDS-System/fix-backend-dependencies.sh
```

**Verifikasi:**
```bash
sudo python3 -c "import flask; print('Flask OK')"
```

---

## ✅ Step 2: Update Service File ke Systemd

Service file di repository sudah diperbaiki. Sekarang perlu di-copy ke systemd:

```bash
sudo cp /app/ProDS-System/backend/prods-backend.service /etc/systemd/system/
sudo systemctl daemon-reload
```

**Cek hasil:**
```bash
cat /etc/systemd/system/prods-backend.service | grep ExecStart
```

**Harus menampilkan:**
```
ExecStart=/app/ProDS-System/backend/start-backend.sh
```

---

## ✅ Step 3: Verifikasi Script Startup

Pastikan script `start-backend.sh` ada dan bisa dijalankan:

```bash
# Cek file ada
ls -la /app/ProDS-System/backend/start-backend.sh

# Cek isi file
cat /app/ProDS-System/backend/start-backend.sh

# Cek permission (harus executable)
ls -l /app/ProDS-System/backend/start-backend.sh | grep -E "^-rwx"
```

**Harus menampilkan:** File ada dan permission `-rwxr-xr-x` atau `-rwx------`

---

## ✅ Step 4: Test Script Secara Manual (Optional)

Test script bisa jalan sebelum dijalankan oleh systemd:

```bash
cd /app/ProDS-System/backend
bash start-backend.sh
```

**Catatan:** Script ini akan jalan terus sampai di-stop dengan `Ctrl+C`. Ini normal untuk testing.

**Yang harus terjadi:**
- Tidak ada error di awal
- Aplikasi mulai loading (lihat log database connection, dll)
- Port 5000 mulai listen

**Stop dengan:** `Ctrl+C`

---

## ✅ Step 5: Restart Service

Setelah service file di-update, restart service:

```bash
# Stop service dulu (jika sedang running)
sudo systemctl stop prods-backend.service

# Start service
sudo systemctl start prods-backend.service

# Tunggu 3-5 detik
sleep 5
```

---

## ✅ Step 6: Cek Status Service

Cek apakah service berjalan dengan baik:

```bash
sudo systemctl status prods-backend.service
```

**Status yang diharapkan:**
```
● prods-backend.service - ProDS System Backend Service
     Loaded: loaded (/etc/systemd/system/prods-backend.service; enabled; preset: disabled)
     Active: active (running) since [timestamp]
   Main PID: [number] (start-backend.sh)
      Tasks: [number]
     Memory: [size]
        CPU: [time]
```

**✅ BAIK jika:** `Active: active (running)`

**❌ MASALAH jika:** `Active: activating (auto-restart)` atau `Active: failed`

---

## ✅ Step 7: Cek Logs Service

Lihat log untuk memastikan tidak ada error:

```bash
# Logs terakhir (50 baris)
sudo journalctl -u prods-backend.service -n 50 --no-pager

# Atau follow logs real-time
sudo journalctl -u prods-backend.service -f
```

**Yang harus ada di log:**
- ✅ "Starting ProDS Flask Application with SocketIO"
- ✅ Database connection info
- ✅ "Running on http://0.0.0.0:5000"

**❌ Error yang mungkin muncul:**
- Database connection error → Cek PostgreSQL running
- Module not found → Cek dependencies terinstall
- Port already in use → Cek port 5000

---

## ✅ Step 8: Test API Endpoint

Test apakah backend merespons:

```bash
# Test health check atau root endpoint
curl http://localhost:5000/

# Atau test dengan IP server
curl http://10.211.1.188:5000/
```

**Harus dapat response** (bisa JSON, HTML, atau error message yang valid, bukan connection refused)

---

## ✅ Step 9: Cek Port Listening

Pastikan aplikasi benar-benar listen di port 5000:

```bash
# Cek port 5000
sudo netstat -tlnp | grep 5000
# atau
sudo ss -tlnp | grep 5000
```

**Harus menampilkan:**
```
tcp  0  0  0.0.0.0:5000  0.0.0.0:*  LISTEN  [PID]/python3
```

---

## ✅ Step 10: Test dari Frontend (Jika Frontend Running)

Jika frontend sudah running, test dari browser:

1. Buka browser
2. Akses frontend (misalnya: `http://10.211.1.188:3000`)
3. Coba fitur yang memanggil backend API
4. Cek browser console (F12) untuk error

---

## ✅ Step 11: Verifikasi Auto-Restart

Test apakah service bisa auto-restart jika crash:

```bash
# Simulasi crash (kill process)
sudo systemctl status prods-backend.service | grep "Main PID" | awk '{print $3}' | xargs sudo kill -9

# Tunggu 10-15 detik
sleep 15

# Cek status lagi
sudo systemctl status prods-backend.service
```

**Harus:** Service otomatis restart dan kembali `active (running)`

---

## 🐛 Troubleshooting

### Service masih "activating (auto-restart)"

1. **Cek logs detail:**
   ```bash
   sudo journalctl -u prods-backend.service -n 100 --no-pager
   ```

2. **Cek error umum:**
   - **ModuleNotFoundError (Flask, dll)** → Install dependencies untuk root: `sudo pip3 install -r /app/ProDS-System/backend/requirements.txt`
   - Database tidak running → `sudo systemctl start postgresql`
   - Permission error → `sudo chmod +x /app/ProDS-System/backend/start-backend.sh`
   - Port sudah digunakan → `sudo ss -tlnp | grep 5000` lalu kill process
   - Service file belum ter-update → `sudo cp /app/ProDS-System/backend/prods-backend.service /etc/systemd/system/ && sudo systemctl daemon-reload`

### Script tidak executable

```bash
sudo chmod +x /app/ProDS-System/backend/start-backend.sh
```

### Service file tidak ter-update

```bash
sudo cp /app/ProDS-System/backend/prods-backend.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl restart prods-backend.service
```

---

## 📋 Checklist Final

- [ ] Service file sudah di-copy ke `/etc/systemd/system/`
- [ ] `systemctl daemon-reload` sudah dijalankan
- [ ] Script `start-backend.sh` ada dan executable
- [ ] Service status menunjukkan `active (running)`
- [ ] Logs tidak menunjukkan error
- [ ] Port 5000 listening
- [ ] API endpoint bisa diakses
- [ ] Frontend bisa connect ke backend (jika frontend running)

---

## 🎉 Jika Semua Checklist ✅

Service backend sudah berjalan dengan benar! Aplikasi akan:
- ✅ Otomatis start saat server boot
- ✅ Otomatis restart jika crash
- ✅ Logs tersimpan di systemd journal

---

**Perintah Berguna:**
```bash
# Start/Stop/Restart
sudo systemctl start prods-backend.service
sudo systemctl stop prods-backend.service
sudo systemctl restart prods-backend.service

# Status & Logs
sudo systemctl status prods-backend.service
sudo journalctl -u prods-backend.service -f

# Enable/Disable auto-start
sudo systemctl enable prods-backend.service
sudo systemctl disable prods-backend.service
```

