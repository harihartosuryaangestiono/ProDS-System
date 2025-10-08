# -*- coding: utf-8 -*-
"""
Updated SINTA Dosen Scraper with G-Index extraction
Created on Tue Sep 23 11:01:48 2025

@author: harih
"""

import time
import psycopg2
from bs4 import BeautifulSoup
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from webdriver_manager.chrome import ChromeDriverManager
import logging
from datetime import datetime
import uuid
import psycopg2.extras
import re

# Setup logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class SintaDosenScraper:
    def __init__(self, db_config):
        self.db_config = db_config
        self.conn = None
        self.cur = None
        self.driver = None
        self.extraction_batch_id = self._generate_batch_id()
        self.extraction_timestamp = datetime.now()
        
        self._connect_db()
        self._init_driver()
        self._ensure_default_data()

    def _generate_batch_id(self):
        """Generate unique batch ID untuk tracking extraction batch"""
        return int(str(int(time.time()))[-8:] + str(uuid.uuid4().int)[-4:])

    def _connect_db(self):
        """Koneksi ke database PostgreSQL"""
        try:
            self.conn = psycopg2.connect(**self.db_config)
            self.cur = self.conn.cursor()
            logger.info("Berhasil terhubung ke database PostgreSQL")
        except Exception as e:
            logger.error(f"Gagal terhubung ke database: {e}")
            raise

    def _init_driver(self):
        """Inisialisasi WebDriver Chrome"""
        try:
            options = webdriver.ChromeOptions()
            options.add_argument("--headless")
            options.add_argument("--disable-gpu")
            options.add_argument("--no-sandbox")
            options.add_argument("--disable-dev-shm-usage")
            options.add_argument("--window-size=1920,1080")
            options.add_argument("--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36")
            
            self.driver = webdriver.Chrome(
                service=Service(ChromeDriverManager().install()), 
                options=options
            )
            logger.info("WebDriver Chrome berhasil diinisialisasi")
        except Exception as e:
            logger.error(f"Gagal menginisialisasi WebDriver: {e}")
            raise

    def _ensure_default_data(self):
        """Pastikan data default ada di tabel jurusan"""
        try:
            # Insert default jurusan jika belum ada
            self.cur.execute("""
                INSERT INTO stg_jurusan_mt (v_nama_jurusan) 
                VALUES ('Jurusan Tidak Diketahui') 
                ON CONFLICT DO NOTHING
            """)
            
            self.conn.commit()
            logger.info("Data default berhasil dipastikan")
            
        except Exception as e:
            logger.error(f"Gagal memastikan data default: {e}")
            self.conn.rollback()

    def _get_default_jurusan_id(self):
        """Mendapatkan ID jurusan default"""
        try:
            self.cur.execute("""
                SELECT v_id_jurusan FROM stg_jurusan_mt 
                WHERE v_nama_jurusan = 'Jurusan Tidak Diketahui'
                LIMIT 1
            """)
            
            result = self.cur.fetchone()
            return result[0] if result else None
            
        except Exception as e:
            logger.error(f"Gagal mendapatkan jurusan default ID: {e}")
            return None

    def _get_current_dosen_count(self):
        """Mendapatkan jumlah dosen unik yang sudah ada di database"""
        try:
            self.cur.execute("""
                SELECT COUNT(DISTINCT v_id_sinta) as total_dosen
                FROM tmp_dosen_dt 
                WHERE v_id_sinta IS NOT NULL
            """)
            
            result = self.cur.fetchone()
            return result[0] if result else 0
            
        except Exception as e:
            logger.error(f"Gagal mendapatkan jumlah dosen saat ini: {e}")
            return 0

    def _is_dosen_exists(self, sinta_id):
        """Cek apakah dosen dengan SINTA ID tertentu sudah ada di database"""
        try:
            self.cur.execute("""
                SELECT COUNT(*) FROM tmp_dosen_dt WHERE v_id_sinta = %s
            """, (sinta_id,))
            
            result = self.cur.fetchone()
            return result[0] > 0 if result else False
            
        except Exception as e:
            logger.error(f"Gagal mengecek keberadaan dosen {sinta_id}: {e}")
            return False

    def _insert_or_update_dosen(self, nama, sinta_id, profile_url, stats_data):
        """Insert dosen baru atau update existing dosen ke tabel tmp_dosen_dt"""
        try:
            # Cek apakah dosen sudah ada berdasarkan SINTA ID
            self.cur.execute("""
                SELECT v_id_dosen FROM tmp_dosen_dt WHERE v_id_sinta = %s
            """, (sinta_id,))
            
            result = self.cur.fetchone()
            default_jurusan_id = self._get_default_jurusan_id()
            
            if result:
                # Update existing dosen dengan data terbaru
                dosen_id = result[0]
                self.cur.execute("""
                    UPDATE tmp_dosen_dt SET
                        v_nama_dosen = %s,
                        n_total_sitasi_gs = %s,
                        n_h_index_gs = %s,
                        n_h_index_gs_sinta = %s,
                        n_h_index_scopus = %s,
                        n_g_index_gs_sinta = %s,
                        n_g_index_scopus = %s,
                        n_artikel_gs = %s,
                        n_artikel_scopus = %s,
                        n_sitasi_gs = %s,
                        n_sitasi_scopus = %s,
                        n_sitasi_dokumen_gs = %s,
                        n_sitasi_dokumen_scopus = %s,
                        n_i10_index_gs = %s,
                        n_skor_sinta = %s,
                        n_skor_sinta_3yr = %s,
                        v_sumber = %s,
                        v_link_url = %s,
                        t_tanggal_unduh = %s
                    WHERE v_id_dosen = %s
                """, (
                    nama,
                    stats_data.get('citations_gs', 0),
                    stats_data.get('hindex_gs', 0),
                    stats_data.get('hindex_gs', 0),  # Gunakan GS untuk SINTA juga
                    stats_data.get('hindex_scopus', 0),
                    stats_data.get('gindex_gs_sinta', 0),  # NEW: G-Index GS SINTA
                    stats_data.get('gindex_scopus', 0),    # NEW: G-Index Scopus
                    stats_data.get('articles_gs', 0),
                    stats_data.get('articles_scopus', 0),
                    stats_data.get('citations_gs', 0),
                    stats_data.get('citations_scopus', 0),
                    stats_data.get('cited_docs_gs', 0),
                    stats_data.get('cited_docs_scopus', 0),
                    stats_data.get('i10_index_gs', 0),
                    stats_data.get('skor_sinta_overall', 0),
                    stats_data.get('skor_sinta_3yr', 0),
                    'SINTA',
                    profile_url,
                    self.extraction_timestamp,
                    dosen_id
                ))
                logger.info(f"Dosen berhasil diupdate: {nama} (ID: {dosen_id}) - SUDAH ADA")
                return dosen_id, False
            else:
                # Insert dosen baru
                self.cur.execute("""
                    INSERT INTO tmp_dosen_dt (
                        v_nama_dosen, v_id_jurusan, v_id_sinta,
                        n_total_sitasi_gs, n_h_index_gs, n_h_index_gs_sinta, n_h_index_scopus,
                        n_g_index_gs_sinta, n_g_index_scopus,
                        n_artikel_gs, n_artikel_scopus, n_sitasi_gs, n_sitasi_scopus,
                        n_sitasi_dokumen_gs, n_sitasi_dokumen_scopus, n_i10_index_gs,
                        n_skor_sinta, n_skor_sinta_3yr, v_sumber, v_link_url, t_tanggal_unduh
                    )
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                    RETURNING v_id_dosen
                """, (
                    nama, default_jurusan_id, sinta_id,
                    stats_data.get('citations_gs', 0),
                    stats_data.get('hindex_gs', 0),
                    stats_data.get('hindex_gs', 0),  # Gunakan GS untuk SINTA juga
                    stats_data.get('hindex_scopus', 0),
                    stats_data.get('gindex_gs_sinta', 0),  # NEW: G-Index GS SINTA
                    stats_data.get('gindex_scopus', 0),    # NEW: G-Index Scopus
                    stats_data.get('articles_gs', 0),
                    stats_data.get('articles_scopus', 0),
                    stats_data.get('citations_gs', 0),
                    stats_data.get('citations_scopus', 0),
                    stats_data.get('cited_docs_gs', 0),
                    stats_data.get('cited_docs_scopus', 0),
                    stats_data.get('i10_index_gs', 0),
                    stats_data.get('skor_sinta_overall', 0),
                    stats_data.get('skor_sinta_3yr', 0),
                    'SINTA',
                    profile_url,
                    self.extraction_timestamp
                ))
                
                dosen_id = self.cur.fetchone()[0]
                logger.info(f"Dosen baru berhasil diinsert: {nama} (ID: {dosen_id}) - BARU")
            
            self.conn.commit()
            return dosen_id, True
            
        except Exception as e:
            logger.error(f"Gagal insert/update dosen {nama}: {e}")
            self.conn.rollback()
            return None, False

    def _clean_sinta_id(self, sinta_id):
        """Membersihkan SINTA ID dari prefix 'profile/' dan karakter tidak diinginkan"""
        if not sinta_id:
            return None
            
        # Remove 'profile/' prefix if exists
        if sinta_id.startswith('profile/'):
            sinta_id = sinta_id[8:]
        
        # Remove any trailing parameters or fragments
        if '?' in sinta_id:
            sinta_id = sinta_id.split('?')[0]
        if '#' in sinta_id:
            sinta_id = sinta_id.split('#')[0]
            
        # Remove any leading/trailing whitespace
        sinta_id = sinta_id.strip()
        
        # Validate that it's numeric (SINTA IDs should be numeric)
        if sinta_id.isdigit():
            return sinta_id
        else:
            logger.warning(f"SINTA ID tidak valid (bukan numerik): {sinta_id}")
            return None

    def _extract_profile_details(self, profile_url):
        """Ekstrak detail profil dari halaman individu dosen"""
        stats = {
            "articles_scopus": 0, "articles_gs": 0,
            "citations_scopus": 0, "citations_gs": 0,
            "cited_docs_scopus": 0, "cited_docs_gs": 0,
            "hindex_scopus": 0, "hindex_gs": 0,
            "gindex_scopus": 0, "gindex_gs_sinta": 0,  # NEW: G-Index values
            "i10_index_gs": 0,
            "skor_sinta_overall": 0,
            "skor_sinta_3yr": 0
        }
        
        try:
            self.driver.get(profile_url)
            time.sleep(3)
            
            # Wait for page to load
            WebDriverWait(self.driver, 10).until(
                EC.presence_of_element_located((By.TAG_NAME, "body"))
            )
            
            profile_soup = BeautifulSoup(self.driver.page_source, "html.parser")
            
            # Ekstrak i10-Index dari tabel
            self._extract_i10_index(profile_soup, stats)
            
            # Ekstrak G-Index dari tabel (NEW)
            self._extract_g_index(profile_soup, stats)
            
            # Ekstrak SINTA Scores
            self._extract_sinta_scores(profile_soup, stats)
            
            # Cari tabel statistik untuk data lainnya
            stats_table = profile_soup.find("table", class_="table")
            if not stats_table:
                stats_table = profile_soup.find("div", class_="table-responsive")
                if stats_table:
                    stats_table = stats_table.find("table")
            
            if stats_table:
                rows = stats_table.find_all("tr")
                for row in rows:
                    cols = row.find_all("td")
                    if len(cols) >= 3:
                        key = cols[0].text.strip().lower()
                        scopus_value = self._parse_number(cols[1].text.strip())
                        gs_value = self._parse_number(cols[2].text.strip())
                        
                        if "article" in key or "artikel" in key:
                            stats["articles_scopus"] = scopus_value
                            stats["articles_gs"] = gs_value
                        elif "citation" in key or "sitasi" in key:
                            stats["citations_scopus"] = scopus_value
                            stats["citations_gs"] = gs_value
                        elif "cited document" in key or "dokumen tersitasi" in key:
                            stats["cited_docs_scopus"] = scopus_value
                            stats["cited_docs_gs"] = gs_value
                        elif "h-index" in key or "hindex" in key:
                            stats["hindex_scopus"] = scopus_value
                            stats["hindex_gs"] = gs_value
            
            logger.info(f"Berhasil mengekstrak detail profil dari {profile_url}")
            logger.info(f"Stats: {stats}")
            
        except Exception as e:
            logger.warning(f"Gagal mengekstrak detail profil dari {profile_url}: {e}")
        
        return stats

    def _extract_g_index(self, soup, stats):
        """Ekstrak nilai G-Index dari HTML (NEW FUNCTION)"""
        try:
            # Cari semua row dalam tabel
            all_rows = soup.find_all("tr")
            
            for row in all_rows:
                # Cari td pertama yang mengandung "G-Index"
                first_td = row.find("td", class_="text-left")
                if first_td and "g-index" in first_td.text.lower():
                    all_tds = row.find_all("td")
                    
                    if len(all_tds) >= 3:
                        # Kolom kedua (index 1) = Scopus (text-warning) = n_g_index_scopus
                        scopus_td = all_tds[1]
                        if scopus_td and "text-warning" in scopus_td.get('class', []):
                            scopus_gindex = self._parse_number(scopus_td.text.strip())
                            stats["gindex_scopus"] = scopus_gindex
                            logger.info(f"G-Index Scopus ditemukan: {scopus_gindex}")
                        
                        # Kolom ketiga (index 2) = Google Scholar (text-success) = n_g_index_gs_sinta
                        gs_td = all_tds[2]
                        if gs_td and "text-success" in gs_td.get('class', []):
                            gs_gindex = self._parse_number(gs_td.text.strip())
                            stats["gindex_gs_sinta"] = gs_gindex
                            logger.info(f"G-Index GS SINTA ditemukan: {gs_gindex}")
                    
                    # Setelah menemukan G-Index row, keluar dari loop
                    break
                    
        except Exception as e:
            logger.warning(f"Gagal ekstrak G-Index: {e}")

    def _extract_i10_index(self, soup, stats):
        """Ekstrak nilai i10-Index dari HTML"""
        try:
            # Cari row yang mengandung "i10-Index"
            i10_rows = soup.find_all("tr")
            for row in i10_rows:
                first_td = row.find("td")
                if first_td and "i10-index" in first_td.text.lower():
                    # Cari td dengan class "text-success" (kolom Google Scholar)
                    gs_td = row.find("td", class_="text-success")
                    if gs_td:
                        i10_value = self._parse_number(gs_td.text.strip())
                        stats["i10_index_gs"] = i10_value
                        logger.info(f"i10-Index GS ditemukan: {i10_value}")
                        break
        except Exception as e:
            logger.warning(f"Gagal ekstrak i10-Index: {e}")

    def _extract_sinta_scores(self, soup, stats):
        """Ekstrak SINTA Score Overall dan SINTA Score 3Yr"""
        try:
            # Cari div yang mengandung SINTA Score
            score_divs = soup.find_all("div", class_="col-4")
            if not score_divs:
                score_divs = soup.find_all("div", class_=re.compile(r"col.*"))
            
            for div in score_divs:
                pr_txt = div.find("div", class_="pr-txt")
                pr_num = div.find("div", class_="pr-num")
                
                if pr_txt and pr_num:
                    score_type = pr_txt.text.strip().lower()
                    score_value = self._parse_float(pr_num.text.strip())
                    
                    if "sinta score overall" in score_type:
                        stats["skor_sinta_overall"] = score_value
                        logger.info(f"SINTA Score Overall ditemukan: {score_value}")
                    elif "sinta score 3yr" in score_type:
                        stats["skor_sinta_3yr"] = score_value
                        logger.info(f"SINTA Score 3Yr ditemukan: {score_value}")
                        
        except Exception as e:
            logger.warning(f"Gagal ekstrak SINTA Scores: {e}")

    def _parse_number(self, text):
        """Parse text ke number, return 0 jika gagal"""
        try:
            # Remove non-numeric characters except dots and commas
            cleaned = re.sub(r'[^\d.,]', '', text)
            if not cleaned:
                return 0
            # Handle comma as thousand separator
            if ',' in cleaned and '.' in cleaned:
                cleaned = cleaned.replace(',', '')
            elif ',' in cleaned:
                cleaned = cleaned.replace(',', '')
            return int(float(cleaned))
        except:
            return 0

    def _parse_float(self, text):
        """Parse text ke float, return 0.0 jika gagal"""
        try:
            # Remove non-numeric characters except dots and commas
            cleaned = re.sub(r'[^\d.,]', '', text)
            if not cleaned:
                return 0.0
            # Handle different decimal separators
            if ',' in cleaned and '.' in cleaned:
                # Assume comma is thousand separator, dot is decimal
                cleaned = cleaned.replace(',', '')
            elif ',' in cleaned and len(cleaned.split(',')[1]) <= 3:
                # Comma might be decimal separator
                cleaned = cleaned.replace(',', '.')
            return float(cleaned)
        except:
            return 0.0

    def scrape_until_target_reached(self, affiliation_id, target_dosen=473, max_pages=100, max_cycles=10):
        """
        Scraping data dosen hingga mencapai target jumlah dosen unik
        
        Args:
            affiliation_id: ID afiliasi di SINTA
            target_dosen: Target jumlah dosen yang ingin dicapai (default: 473)
            max_pages: Maksimal halaman per cycle
            max_cycles: Maksimal siklus scraping
        """
        logger.info(f"🎯 TARGET: {target_dosen} dosen unik untuk afiliasi ID: {affiliation_id}")
        logger.info(f"Batch ID: {self.extraction_batch_id}, Extraction Time: {self.extraction_timestamp}")
        
        cycle = 1
        
        while cycle <= max_cycles:
            current_count = self._get_current_dosen_count()
            logger.info(f"\n🔄 CYCLE {cycle} - Saat ini: {current_count}/{target_dosen} dosen")
            
            if current_count >= target_dosen:
                logger.info(f"🎉 TARGET TERCAPAI! Total dosen unik: {current_count}")
                break
                
            remaining_needed = target_dosen - current_count
            logger.info(f"📊 Masih membutuhkan: {remaining_needed} dosen lagi")
            
            # Jalankan scraping untuk cycle ini
            new_dosen_count = self.scrape_and_store_dosen(
                affiliation_id=affiliation_id, 
                max_pages=max_pages,
                cycle=cycle
            )
            
            if new_dosen_count == 0:
                logger.warning(f"⚠️  Tidak ada dosen baru ditemukan di cycle {cycle}")
                if cycle >= 3:  # Jika sudah 3 cycle tidak ada dosen baru, hentikan
                    logger.info("🛑 Menghentikan scraping karena tidak ada dosen baru dalam 3 cycle terakhir")
                    break
            
            cycle += 1
            
            # Jeda antar cycle
            if cycle <= max_cycles:
                logger.info(f"⏳ Jeda 10 detik sebelum cycle berikutnya...")
                time.sleep(10)
        
        final_count = self._get_current_dosen_count()
        logger.info(f"\n✅ SCRAPING SELESAI!")
        logger.info(f"📈 Total dosen final: {final_count}/{target_dosen}")
        logger.info(f"🔢 Total cycle: {cycle-1}")
        
        return final_count

    def scrape_and_store_dosen(self, affiliation_id, max_pages=100, cycle=1):
        """Scraping data dosen dari SINTA dan simpan ke database (per cycle)"""
        base_url = f"https://sinta.kemdikbud.go.id/affiliations/authors/{affiliation_id}"
        logger.info(f"📖 Cycle {cycle} - Scraping hingga {max_pages} halaman")

        new_dosen_count = 0
        total_processed = 0

        for page in range(1, max_pages + 1):
            url = f"{base_url}?page={page}"
            logger.info(f"🔍 Cycle {cycle} - Halaman {page}")
            
            try:
                self.driver.get(url)
                time.sleep(3)
                
                # Wait for content to load
                WebDriverWait(self.driver, 10).until(
                    EC.presence_of_element_located((By.TAG_NAME, "body"))
                )
                
                # Scroll to bottom to load all content
                self.driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
                time.sleep(2)

                soup = BeautifulSoup(self.driver.page_source, "html.parser")
                
                # Cari daftar author/dosen
                author_blocks = []
                
                selectors = [
                    "div.au-item",
                    "div.author-item", 
                    "div.card.author-card",
                    "div[class*='author']",
                    "div.row div.col-md-12",
                    "div.profile-card"
                ]
                
                for selector in selectors:
                    author_blocks = soup.select(selector)
                    if author_blocks:
                        logger.info(f"Menggunakan selector: {selector}")
                        break
                
                # Fallback method
                if not author_blocks:
                    all_divs = soup.find_all("div")
                    for div in all_divs:
                        author_link = div.find("a", href=lambda x: x and "/authors/" in x)
                        if author_link:
                            author_blocks.append(div)
                
                if not author_blocks:
                    logger.warning(f"❌ Tidak ada author di halaman {page} - cycle {cycle}")
                    continue

                logger.info(f"📋 Ditemukan {len(author_blocks)} author di halaman {page}")

                page_new_count = 0
                
                for idx, block in enumerate(author_blocks):
                    try:
                        # Ekstrak nama dan URL profil
                        name_element = block.find("a", href=lambda x: x and "/authors/" in x)
                        
                        if not name_element:
                            all_links = block.find_all("a", href=True)
                            for link in all_links:
                                if "/authors/" in link.get("href", ""):
                                    name_element = link
                                    break
                        
                        if not name_element:
                            continue

                        name = name_element.text.strip()
                        profile_url = name_element.get("href", "")
                        
                        # Pastikan URL lengkap
                        if profile_url and not profile_url.startswith("http"):
                            profile_url = "https://sinta.kemdikbud.go.id" + profile_url
                        
                        # Ekstrak SINTA ID
                        sinta_id = None
                        if profile_url and "/authors/" in profile_url:
                            raw_id = profile_url.split("/authors/")[-1].split("?")[0]
                            sinta_id = self._clean_sinta_id(raw_id)
                        
                        if not sinta_id:
                            continue
                        
                        # Cek apakah sudah ada di database
                        if self._is_dosen_exists(sinta_id):
                            logger.info(f"⏭️  Skip (sudah ada): {name} (SINTA ID: {sinta_id})")
                            total_processed += 1
                            continue
                        
                        logger.info(f"🆕 Proses dosen baru: {name} (SINTA ID: {sinta_id})")

                        # Ekstrak detail dari halaman profil
                        profile_stats = self._extract_profile_details(profile_url)

                        # Insert/update dosen ke database
                        dosen_id, is_new = self._insert_or_update_dosen(name, sinta_id, profile_url, profile_stats)
                        
                        if dosen_id and is_new:
                            new_dosen_count += 1
                            page_new_count += 1
                            logger.info(f"✅ Dosen baru ditambahkan: {name} (ID: {dosen_id})")
                        
                        total_processed += 1

                    except Exception as e:
                        logger.error(f"❌ Error memproses author {idx+1}: {e}")
                        continue

                logger.info(f"📄 Halaman {page} selesai - {page_new_count} dosen baru")
                
                # Jika tidak ada dosen baru di halaman ini, lanjut ke halaman berikutnya
                if page_new_count == 0 and page > 5:
                    logger.info(f"⏩ Skip halaman selanjutnya karena tidak ada dosen baru")

            except Exception as e:
                logger.error(f"❌ Gagal scraping halaman {page}: {e}")
                continue

        logger.info(f"🏁 Cycle {cycle} selesai - {new_dosen_count} dosen baru, {total_processed} total diproses")
        return new_dosen_count

    def get_extraction_summary(self):
        """Mendapatkan ringkasan hasil extraction"""
        try:
            # Count dosen yang di-extract dalam batch ini
            self.cur.execute("""
                SELECT COUNT(*) as total_dosen
                FROM tmp_dosen_dt 
                WHERE DATE(t_tanggal_unduh) = CURRENT_DATE
            """)
            
            dosen_count = self.cur.fetchone()[0]
            
            # Total dosen unik berdasarkan SINTA ID
            self.cur.execute("""
                SELECT COUNT(DISTINCT v_id_sinta) as total_dosen_unik
                FROM tmp_dosen_dt 
                WHERE v_id_sinta IS NOT NULL
            """)
            
            dosen_unik = self.cur.fetchone()[0]
            
            # Total sitasi dan skor yang direkam
            self.cur.execute("""
                SELECT SUM(n_total_sitasi_gs) as total_sitasi_gs,
                       SUM(n_sitasi_scopus) as total_sitasi_scopus,
                       AVG(n_skor_sinta) as avg_skor_sinta,
                       AVG(n_skor_sinta_3yr) as avg_skor_sinta_3yr,
                       SUM(n_i10_index_gs) as total_i10_index,
                       SUM(n_g_index_gs_sinta) as total_gindex_gs_sinta,
                       SUM(n_g_index_scopus) as total_gindex_scopus
                FROM tmp_dosen_dt 
                WHERE DATE(t_tanggal_unduh) = CURRENT_DATE
            """)
            
            result = self.cur.fetchone()
            total_sitasi_gs = result[0] or 0
            total_sitasi_scopus = result[1] or 0
            avg_skor_sinta = result[2] or 0
            avg_skor_sinta_3yr = result[3] or 0
            total_i10_index = result[4] or 0
            total_gindex_gs_sinta = result[5] or 0  # NEW: Total G-Index GS SINTA
            total_gindex_scopus = result[6] or 0    # NEW: Total G-Index Scopus
            
            return {
                "batch_id": self.extraction_batch_id,
                "extraction_time": self.extraction_timestamp,
                "total_dosen": dosen_count,
                "total_dosen_unik": dosen_unik,
                "total_sitasi_gs": total_sitasi_gs,
                "total_sitasi_scopus": total_sitasi_scopus,
                "avg_skor_sinta": avg_skor_sinta,
                "avg_skor_sinta_3yr": avg_skor_sinta_3yr,
                "total_i10_index": total_i10_index,
                "total_gindex_gs_sinta": total_gindex_gs_sinta,  # NEW
                "total_gindex_scopus": total_gindex_scopus       # NEW
            }
            
        except Exception as e:
            logger.error(f"Gagal mendapatkan ringkasan extraction: {e}")
            return None

    def close(self):
        """Tutup koneksi database dan WebDriver"""
        try:
            if self.cur:
                self.cur.close()
            if self.conn:
                self.conn.close()
            if self.driver:
                self.driver.quit()
            logger.info("Koneksi database dan WebDriver ditutup")
        except Exception as e:
            logger.error(f"Error saat menutup koneksi: {e}")


# Contoh penggunaan
if __name__ == '__main__':
    # Konfigurasi database PostgreSQL - sesuai dengan database baru
    db_config = {
        'dbname': 'SKM_PUBLIKASI',  # Nama database baru
        'user': 'rayhanadjisantoso',        
        'password': 'rayhan123',    
        'host': 'localhost',            
        'port': '5432'                  
    }
    
    try:
        # Inisialisasi scraper
        scraper = SintaDosenScraper(db_config=db_config)
        
        # Scrape hingga mencapai target 473 dosen
        final_count = scraper.scrape_until_target_reached(
            affiliation_id='1397', 
            target_dosen=473,
            # max_pages=50,  # Maksimal 50 halaman per cycle
            # max_cycles=20  # Maksimal 20 cycle
            max_pages=1,
            max_cycles=1
        )
        
        # Tampilkan ringkasan hasil extraction
        summary = scraper.get_extraction_summary()
        if summary:
            print(f"\n📊 RINGKASAN EXTRACTION FINAL")
            print(f"=" * 60)
            print(f"🆔 Batch ID: {summary['batch_id']}")
            print(f"⏰ Waktu Extraction: {summary['extraction_time']}")
            print(f"👥 Total Dosen (Hari Ini): {summary['total_dosen']}")
            print(f"🎯 Total Dosen Unik: {summary['total_dosen_unik']}")
            print(f"📈 Total Sitasi GS: {summary['total_sitasi_gs']}")
            print(f"📈 Total Sitasi Scopus: {summary['total_sitasi_scopus']}")
            print(f"📊 Rata-rata SINTA Score Overall: {summary['avg_skor_sinta']:.3f}")
            print(f"📊 Rata-rata SINTA Score 3Yr: {summary['avg_skor_sinta_3yr']:.3f}")
            print(f"🔢 Total i10-Index: {summary['total_i10_index']}")
            print(f"📈 Total G-Index GS SINTA: {summary['total_gindex_gs_sinta']}")  # NEW
            print(f"📈 Total G-Index Scopus: {summary['total_gindex_scopus']}")      # NEW
            print(f"=" * 60)
            
            if summary['total_dosen_unik'] >= 473:
                print(f"✅ TARGET 473 DOSEN TERCAPAI!")
            else:
                print(f"⚠️  Target belum tercapai, kurang {473 - summary['total_dosen_unik']} dosen")
        
    except KeyboardInterrupt:
        logger.info("⏹️  Scraping dihentikan oleh user")
    except Exception as e:
        logger.error(f"❌ Error utama: {e}")
    
    finally:
        # Pastikan koneksi ditutup
        if 'scraper' in locals():
            scraper.close()
            print("\n🔒 Koneksi database dan WebDriver telah ditutup")