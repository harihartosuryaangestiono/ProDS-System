-- ========================
-- DROP TABLES (Dalam urutan yang benar untuk menghindari dependency issues)
-- ========================

DROP TABLE IF EXISTS stg_publikasi_sitasi_tahunan_dr;
DROP TABLE IF EXISTS stg_publikasi_dosen_dt;
DROP TABLE IF EXISTS stg_lainnya_dr;
DROP TABLE IF EXISTS stg_prosiding_dr;
DROP TABLE IF EXISTS stg_penelitian_dr;
DROP TABLE IF EXISTS stg_buku_dr;
DROP TABLE IF EXISTS stg_artikel_dr;
DROP TABLE IF EXISTS stg_publikasi_tr;
DROP TABLE IF EXISTS stg_jurnal_mt;
DROP TABLE IF EXISTS tmp_dosen_dt;
DROP TABLE IF EXISTS stg_jurusan_mt;
DROP TABLE IF EXISTS temp_dosengs_scraping;
DROP TABLE IF EXISTS datamaster;
DROP TABLE IF EXISTS users;

-- ========================
-- DROP FUNCTION
-- ========================
DROP FUNCTION IF EXISTS update_updated_at_column() CASCADE;

SELECT *
FROM tmp_dosen_dt

-- ========================
-- 1. Tabel DataMaster
-- ========================
CREATE TABLE datamaster (
    v_nip VARCHAR(20) PRIMARY KEY,
    v_nama_lengkap VARCHAR(150),
    v_nama_lengkap_gelar VARCHAR(200),
    v_homebase_unpar VARCHAR(100),
    v_nama_homebase_unpar VARCHAR(150),
    v_homebase_dikti VARCHAR(100),
    v_nama_homebase_dikti VARCHAR(150),
    v_ket_jns_pegawai VARCHAR(50),
    v_ket_kel_pegawai VARCHAR(50),
    v_ket_kategori_status_peg VARCHAR(50),
    id_sinta VARCHAR(20),
    id_gs VARCHAR(50),
    id_scopus VARCHAR(50)
);

-- ========================
-- 2. Tabel Jurusan
-- ========================
CREATE TABLE stg_jurusan_mt (
    v_id_jurusan SERIAL PRIMARY KEY,
    v_nama_jurusan VARCHAR(200) NOT NULL
);

-- ========================
-- 3. Tabel Dosen
-- ========================
CREATE TABLE tmp_dosen_dt (
    v_id_dosen SERIAL PRIMARY KEY,
    v_nama_dosen VARCHAR(200) NOT NULL,
    v_id_jurusan INT, -- hanya kolom, tanpa FK
    n_total_publikasi INT DEFAULT 0,
    n_total_sitasi_gs INT DEFAULT 0, -- dari Google Scholar
    n_total_sitasi_gs2020 INT,
    v_id_googlescholar VARCHAR(100),
    v_id_sinta VARCHAR(100),
    n_i10_index_gs INT,
    n_i10_index_gs2020 INT,
    n_h_index_gs INT, -- dari Google Scholar
    n_h_index_gs2020 INT, -- dari Google Scholar
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

-- ========================
-- 4. Tabel Jurnal
-- ========================
CREATE TABLE stg_jurnal_mt (
    v_id_jurnal SERIAL PRIMARY KEY,
    v_nama_jurnal VARCHAR(255) NOT NULL
);

-- ========================
-- 5. Tabel Temporary Dosen GS Scraping
-- ========================
CREATE TABLE temp_dosengs_scraping (
    v_id_gs VARCHAR(50) NOT NULL,
    v_nama VARCHAR(255) NOT NULL,
    v_affiliation VARCHAR(100),
    n_citations INT DEFAULT 0,
    v_link VARCHAR(255),
    v_status VARCHAR(200) DEFAULT 'pending',
    v_error_message TEXT,
    t_last_updated TIMESTAMP
);

-- ========================
-- 6. Tabel Publikasi (Superclass)
-- ========================
CREATE TABLE stg_publikasi_tr (
    v_id_publikasi SERIAL PRIMARY KEY,
    v_authors TEXT,
    v_judul TEXT NOT NULL,
    v_jenis VARCHAR(20) NOT NULL CHECK (v_jenis IN ('artikel','buku','penelitian','prosiding','lainnya')),
    v_tahun_publikasi INT,
    n_total_sitasi INT DEFAULT 0,
    v_sumber VARCHAR(50),
    v_publisher VARCHAR(200),
    v_link_url VARCHAR(255),
    t_tanggal_unduh TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    t_updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- ========================
-- 7. Subclass Publikasi
-- ========================
CREATE TABLE stg_artikel_dr (
    v_id_publikasi INT PRIMARY KEY,
    v_id_jurnal INT, -- hanya kolom, tanpa FK
    v_volume VARCHAR(50),
    v_issue VARCHAR(50),
    v_pages VARCHAR(50),
    v_terindeks VARCHAR(50), -- GARUDA, Google Scholar, Scopus, SINTA
    v_ranking VARCHAR(50), -- Scopus (Q1-Q4) atau SINTA (S1-S6)
    t_updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE stg_buku_dr (
    v_id_publikasi INT PRIMARY KEY, -- hanya kolom, tanpa FK
    v_isbn VARCHAR(50),
    t_updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE stg_penelitian_dr (
    v_id_publikasi INT PRIMARY KEY, -- hanya kolom, tanpa FK
    v_kategori_penelitian VARCHAR(100),
    t_updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE stg_prosiding_dr (
    v_id_publikasi INT PRIMARY KEY, -- hanya kolom, tanpa FK
    v_nama_konferensi VARCHAR(255),
    f_terindeks_scopus BOOLEAN DEFAULT FALSE, -- publikasi terindeks scopus atau tidak
    t_updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE stg_lainnya_dr (
    v_id_publikasi INT PRIMARY KEY, -- hanya kolom, tanpa FK
    v_keterangan TEXT, -- Untuk catatan tambahan tentang publikasi ini
    t_updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- ========================
-- 8. Relasi Many-to-Many tabel Publikasi dengan tabel Dosen 
-- ========================
CREATE TABLE stg_publikasi_dosen_dt (
    v_id_publikasi INT NOT NULL,
    v_id_dosen INT NOT NULL,
    v_author_order VARCHAR(100), -- misalnya 1 out of 4
    PRIMARY KEY (v_id_publikasi, v_id_dosen)
);

-- ========================
-- 9. Sitasi Tahunan per Publikasi
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
-- 10. Tabel Users
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
-- 11. TRIGGER FUNCTION UNTUK AUTO UPDATE t_updated_at
-- ========================
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    -- CRITICAL: Only execute on UPDATE operations
    IF TG_OP != 'UPDATE' THEN
        RETURN NEW;
    END IF;
    -- Try to update t_updated_at with exception handling
    BEGIN
        NEW.t_updated_at := CURRENT_TIMESTAMP;
    EXCEPTION 
        WHEN undefined_column THEN
            -- Column doesn't exist, silently continue
            RAISE NOTICE 'Table % does not have t_updated_at column', TG_TABLE_NAME;
        WHEN OTHERS THEN
            -- Any other error, log but continue
            RAISE NOTICE 'Error updating t_updated_at for table %: %', TG_TABLE_NAME, SQLERRM;
    END;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- ========================
-- 12. BUAT TRIGGERS UNTUK SETIAP TABEL
-- ========================

-- Trigger untuk stg_jurusan_mt
CREATE TRIGGER update_stg_jurusan_updated_at
    BEFORE UPDATE ON stg_jurusan_mt
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();

-- Trigger untuk tmp_dosen_dt
CREATE TRIGGER update_tmp_dosen_updated_at
    BEFORE UPDATE ON tmp_dosen_dt
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();

-- Trigger untuk stg_jurnal_mt
CREATE TRIGGER update_stg_jurnal_updated_at
    BEFORE UPDATE ON stg_jurnal_mt
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();

-- Trigger untuk stg_publikasi_tr
CREATE TRIGGER update_stg_publikasi_updated_at
    BEFORE UPDATE ON stg_publikasi_tr
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();

-- Trigger untuk stg_artikel_dr
CREATE TRIGGER update_stg_artikel_updated_at
    BEFORE UPDATE ON stg_artikel_dr
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();

-- Trigger untuk stg_buku_dr
CREATE TRIGGER update_stg_buku_updated_at
    BEFORE UPDATE ON stg_buku_dr
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();

-- Trigger untuk stg_penelitian_dr
CREATE TRIGGER update_stg_penelitian_updated_at
    BEFORE UPDATE ON stg_penelitian_dr
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();

-- Trigger untuk stg_prosiding_dr
CREATE TRIGGER update_stg_prosiding_updated_at
    BEFORE UPDATE ON stg_prosiding_dr
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();

-- Trigger untuk stg_lainnya_dr
CREATE TRIGGER update_stg_lainnya_updated_at
    BEFORE UPDATE ON stg_lainnya_dr
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();

-- Trigger untuk stg_publikasi_dosen_dt
CREATE TRIGGER update_stg_publikasi_dosen_updated_at
    BEFORE UPDATE ON stg_publikasi_dosen_dt
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();

-- Trigger untuk stg_publikasi_sitasi_tahunan_dr
CREATE TRIGGER update_stg_publikasi_sitasi_tahunan_updated_at
    BEFORE UPDATE ON stg_publikasi_sitasi_tahunan_dr
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();