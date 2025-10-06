-- ========================
-- DROP TABLES (Dalam urutan yang benar untuk menghindari dependency issues)
-- ========================

-- Drop tables dalam urutan terbalik dari pembuatan untuk menghindari masalah dependencies
DROP TABLE IF EXISTS stg_publikasi_sitasi_tahunan_dr;
DROP TABLE IF EXISTS stg_publikasi_dosen_dt;
DROP TABLE IF EXISTS stg_prosiding_dr;
DROP TABLE IF EXISTS stg_penelitian_dr;
DROP TABLE IF EXISTS stg_buku_dr;
DROP TABLE IF EXISTS stg_artikel_dr;
DROP TABLE IF EXISTS stg_publikasi_tr;
DROP TABLE IF EXISTS stg_jurnal_mt;
DROP TABLE IF EXISTS tmp_dosen_dt;
DROP TABLE IF EXISTS stg_jurusan_mt;
DROP TABLE IF EXISTS users;

-- Jika ingin drop database juga (hati-hati!)
-- DROP DATABASE IF EXISTS "SKM_PUBLIKASI";

-- ========================
-- RECREATE DATABASE DAN TABLES DENGAN TIMESTAMP TRACKING
-- ========================

-- ========================
-- 1. Tabel Jurusan dengan timestamp
-- ========================
CREATE TABLE stg_jurusan_mt (
    v_id_jurusan SERIAL PRIMARY KEY,
    v_nama_jurusan VARCHAR(200) NOT NULL
);

-- ========================
-- 2. Tabel Dosen dengan timestamp
-- ========================
CREATE TABLE tmp_dosen_dt (
    v_id_dosen SERIAL PRIMARY KEY,
    v_nama_dosen VARCHAR(200) NOT NULL,
    v_id_jurusan INT, -- hanya kolom, tanpa FK
    n_total_publikasi INT DEFAULT 0,
    n_total_sitasi_gs INT DEFAULT 0, -- dari Google Scholar
    v_id_googleScholar VARCHAR(100),
    v_id_sinta VARCHAR(100),
    n_i10_index_gs INT,
    n_i10_index_gs2020 INT,
    n_h_index_gs INT, -- dari Google Scholar 
    n_h_index_gs2020 INT,
    n_h_index_gs_sinta INT, -- dari SINTA
    n_h_index_scopus INT,
    n_g_index_gs_sinta INT,
    n_g_index_scopus INT,
    n_skor_sinta NUMERIC(10,2),
    n_skor_sinta_3yr NUMERIC(10,2),
    n_artikel_gs INT,
    n_artikel_scopus INT,
    n_sitasi_gs INT, -- dari SINTA
    n_sitasi_scopus INT,
    n_sitasi_dokumen_gs INT,
    n_sitasi_dokumen_scopus INT,
    v_sumber VARCHAR(50),
    v_link_url VARCHAR(255),
    t_tanggal_unduh TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

SELECT *
FROM tmp_dosen_dt
-- ========================
-- 3. Tabel Jurnal dengan timestamp
-- ========================
CREATE TABLE stg_jurnal_mt (
    v_id_jurnal SERIAL PRIMARY KEY,
    v_nama_jurnal VARCHAR(255) NOT NULL
);

CREATE TABLE temp_dosenGS_scraping (
    v_id_GS VARCHAR(50) NOT NULL,
    v_nama VARCHAR(255) NOT NULL,
    v_affiliation VARCHAR (100),
    n_citations INT DEFAULT 0,
    v_link VARCHAR (255)
);

-- ========================
-- 4. Tabel Publikasi (Superclass) dengan timestamp
-- ========================
CREATE TABLE stg_publikasi_tr (
    v_id_publikasi SERIAL PRIMARY KEY,
    v_judul TEXT NOT NULL,
    v_authors TEXT,
    v_jenis VARCHAR(20) NOT NULL CHECK (v_jenis IN ('artikel','buku','penelitian','prosiding')),
    v_tahun_publikasi INT,
    n_total_sitasi INT DEFAULT 0,
    v_sumber VARCHAR(50),
    v_publisher VARCHAR(200),
    v_link_url VARCHAR(255),
    t_tanggal_unduh TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- ========================
-- 5. Subclass Publikasi dengan timestamp
-- ========================
CREATE TABLE stg_artikel_dr (
    v_id_publikasi INT PRIMARY KEY,
    v_id_jurnal INT, -- hanya kolom, tanpa FK
    v_volume VARCHAR(50),
    v_issue VARCHAR(50),
    v_pages VARCHAR(50),
    v_terindeks VARCHAR(50), -- Scopus, WoS, DOAJ, dll
    v_ranking VARCHAR(50) -- Q1-Q4, Sinta 1-6
);

CREATE TABLE stg_buku_dr (
    v_id_publikasi INT PRIMARY KEY, -- hanya kolom, tanpa FK
    v_isbn VARCHAR(50)
);

CREATE TABLE stg_penelitian_dr (
    v_id_publikasi INT PRIMARY KEY, -- hanya kolom, tanpa FK
    v_kategori_penelitian VARCHAR(100)
);

CREATE TABLE stg_prosiding_dr (
    v_id_publikasi INT PRIMARY KEY, -- hanya kolom, tanpa FK
    v_nama_konferensi VARCHAR(255),
    f_terindeks_scopus BOOLEAN DEFAULT FALSE -- publikasi terindeks scopus atau tidak
);

-- ========================
-- 6. Relasi Many-to-Many Publikasi - Dosen dengan timestamp
-- ========================
CREATE TABLE stg_publikasi_dosen_dt (
    v_id_publikasi INT NOT NULL,
    v_id_dosen INT NOT NULL,
    v_author_order VARCHAR(100), -- 1 out of 4
    PRIMARY KEY (v_id_publikasi, v_id_dosen)
);

-- ========================
-- 7. Sitasi Tahunan per Publikasi dengan timestamp
-- ========================
CREATE TABLE stg_publikasi_sitasi_tahunan_dr (
    v_id_sitasi SERIAL PRIMARY KEY,
    v_id_publikasi INT NOT NULL, -- hanya kolom, tanpa FK
    v_tahun INT NOT NULL,
    n_total_sitasi_tahun INT DEFAULT 0,
    v_sumber VARCHAR(100),
    t_tanggal_unduh DATE DEFAULT CURRENT_DATE
);

-- ========================
-- 8. Tabel Users dengan timestamp
-- ========================
CREATE TABLE users (
    v_id_user SERIAL PRIMARY KEY,
    v_username VARCHAR(64) NOT NULL,
    v_email VARCHAR(120) NOT NULL,
    v_password_hash VARCHAR(256) NOT NULL,
    f_is_admin BOOLEAN DEFAULT FALSE,
    t_tanggal_bikin TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- ========================
-- 9. TRIGGER FUNCTIONS UNTUK AUTO UPDATE t_updated_at
-- ========================

-- Function untuk update timestamp
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.t_updated_at = CURRENT_TIMESTAMP;
    RETURN NEW;
END;
$$ language 'plpgsql';

-- ========================
-- 10. BUAT TRIGGERS UNTUK SETIAP TABEL
-- ========================

-- Trigger untuk stg_jurusan
CREATE TRIGGER update_stg_jurusan_updated_at
    BEFORE UPDATE ON stg_jurusan_mt
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();

-- Trigger untuk tmp_dosen
CREATE TRIGGER update_tmp_dosen_updated_at
    BEFORE UPDATE ON tmp_dosen_dt
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();

-- Trigger untuk stg_jurnal
CREATE TRIGGER update_stg_jurnal_updated_at
    BEFORE UPDATE ON stg_jurnal_mt
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();

-- Trigger untuk stg_publikasi
CREATE TRIGGER update_stg_publikasi_updated_at
    BEFORE UPDATE ON stg_publikasi_tr
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();

-- Trigger untuk stg_artikel
CREATE TRIGGER update_stg_artikel_updated_at
    BEFORE UPDATE ON stg_artikel_dr
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();

-- Trigger untuk stg_buku
CREATE TRIGGER update_stg_buku_updated_at
    BEFORE UPDATE ON stg_buku_dr
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();

-- Trigger untuk stg_penelitian
CREATE TRIGGER update_stg_penelitian_updated_at
    BEFORE UPDATE ON stg_penelitian_dr
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();

-- Trigger untuk stg_prosiding
CREATE TRIGGER update_stg_prosiding_updated_at
    BEFORE UPDATE ON stg_prosiding_dr
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();

-- Trigger untuk stg_publikasi_dosen
CREATE TRIGGER update_stg_publikasi_dosen_updated_at
    BEFORE UPDATE ON stg_publikasi_dosen_dt
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();

-- Trigger untuk stg_publikasi_sitasi_tahunan
CREATE TRIGGER update_stg_publikasi_sitasi_tahunan_updated_at
    BEFORE UPDATE ON stg_publikasi_sitasi_tahunan_dr
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();


-- ========================
-- 11. INDEXES UNTUK PERFORMA (OPSIONAL)
-- ========================

-- Index untuk timestamp columns (berguna untuk query berdasarkan waktu)
CREATE INDEX idx_stg_jurusan_created_at ON stg_jurusan_mt(t_created_at);
CREATE INDEX idx_stg_jurusan_updated_at ON stg_jurusan_mt(t_updated_at);

CREATE INDEX idx_tmp_dosen_created_at ON tmp_dosen_dt(t_created_at);
CREATE INDEX idx_tmp_dosen_updated_at ON tmp_dosen_dt(t_updated_at);

CREATE INDEX idx_stg_publikasi_created_at ON stg_publikasi_tr(t_created_at);
CREATE INDEX idx_stg_publikasi_updated_at ON stg_publikasi_tr(t_updated_at);

-- Index untuk kolom yang sering digunakan untuk join
CREATE INDEX idx_tmp_dosen_jurusan ON tmp_dosen_dt(v_id_jurusan);
CREATE INDEX idx_stg_artikel_jurnal ON stg_artikel_dr(v_id_jurnal);

-- ========================
-- 12. SAMPLE QUERIES UNTUK MONITORING
-- ========================

-- Contoh query untuk melihat data yang baru ditambahkan hari ini
-- SELECT * FROM tmp_dosen WHERE DATE(t_created_at) = CURRENT_DATE;

-- Contoh query untuk melihat data yang diupdate dalam 1 jam terakhir
-- SELECT * FROM stg_publikasi WHERE t_updated_at >= NOW() - INTERVAL '1 hour';

-- Contoh query untuk audit trail
-- SELECT 
--     'tmp_dosen' as table_name,
--     COUNT(*) as total_records,
--     COUNT(*) FILTER (WHERE DATE(t_created_at) = CURRENT_DATE) as created_today,
--     COUNT(*) FILTER (WHERE DATE(t_updated_at) = CURRENT_DATE AND DATE(t_created_at) != CURRENT_DATE) as updated_today
-- FROM tmp_dosen
-- UNION ALL
-- SELECT 
--     'stg_publikasi' as table_name,
--     COUNT(*) as total_records,
--     COUNT(*) FILTER (WHERE DATE(t_created_at) = CURRENT_DATE) as created_today,
--     COUNT(*) FILTER (WHERE DATE(t_updated_at) = CURRENT_DATE AND DATE(t_created_at) != CURRENT_DATE) as updated_today
-- FROM stg_publikasi;