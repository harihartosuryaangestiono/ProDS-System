# -*- coding: utf-8 -*-
"""
SINTA Garuda Publications Scraper - Fixed for Existing Database Schema
Created on Tue May 20 07:40:01 2025

@author: harih

Perbaikan: Menambahkan selector CSS yang lebih beragam untuk scraping nama jurnal 
dan menambahkan logging untuk debugging jika nama jurnal tidak ditemukan.
"""

import requests
from bs4 import BeautifulSoup
import pandas as pd
import csv
from time import sleep
import random
import os
from urllib.parse import urljoin
from datetime import datetime
import logging
import re
import psycopg2
from psycopg2 import sql
from psycopg2.extras import execute_batch
import json

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler("sinta_garuda_scraper.log"),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger("SintaGarudaScraper")

class DatabaseManager:
    def __init__(self, dbname, user, password, host='localhost', port='5432'):
        self.conn_params = {
            'dbname': dbname,
            'user': user,
            'password': password,
            'host': host,
            'port': port
        }
        self.connection = None
        self.cursor = None
        self.current_batch_id = None
        
    def connect(self):
        try:
            self.connection = psycopg2.connect(**self.conn_params)
            self.cursor = self.connection.cursor()
            logger.info("Connected to PostgreSQL database successfully")
            return True
        except Exception as e:
            logger.error(f"Error connecting to database: {e}")
            return False
            
    def disconnect(self):
        if self.connection:
            self.connection.close()
            logger.info("Disconnected from database")
    
    def generate_batch_id(self):
        """Generate a new batch ID for tracking data extraction"""
        import time
        self.current_batch_id = int(time.time() * 1000)  # millisecond timestamp
        logger.info(f"Generated new batch ID: {self.current_batch_id}")
        return self.current_batch_id
    
    def get_jurusan_id(self, nama_jurusan):
        """Get jurusan ID from stg_jurusan_mt"""
        try:
            query = "SELECT v_id_jurusan FROM stg_jurusan_mt WHERE LOWER(v_nama_jurusan) = LOWER(%s)"
            self.cursor.execute(query, (nama_jurusan,))
            result = self.cursor.fetchone()
            
            if result:
                return result[0]
            
            logger.warning(f"Jurusan '{nama_jurusan}' not found in database")
            return None
            
        except Exception as e:
            logger.error(f"Error getting jurusan: {e}")
            return None
    
    def get_dosen_by_sinta_id(self, sinta_id):
        """Get dosen data by Sinta ID from tmp_dosen_dt"""
        try:
            query = """
                SELECT v_id_dosen, v_nama_dosen, v_id_jurusan 
                FROM tmp_dosen_dt 
                WHERE v_id_sinta = %s
            """
            self.cursor.execute(query, (sinta_id,))
            result = self.cursor.fetchone()
            
            if result:
                return {
                    'id_dosen': result[0],
                    'nama': result[1],
                    'id_jurusan': result[2]
                }
            
            logger.warning(f"Dosen with Sinta ID '{sinta_id}' not found in database")
            return None
            
        except Exception as e:
            logger.error(f"Error getting dosen by Sinta ID: {e}")
            return None
    
    def get_jurnal_id(self, nama_jurnal):
        """Get jurnal ID from stg_jurnal_mt"""
        try:
            query = "SELECT v_id_jurnal FROM stg_jurnal_mt WHERE LOWER(v_nama_jurnal) = LOWER(%s)"
            self.cursor.execute(query, (nama_jurnal,))
            result = self.cursor.fetchone()
            
            if result:
                return result[0]
            
            # Create new jurnal if not exists
            insert_query = "INSERT INTO stg_jurnal_mt (v_nama_jurnal) VALUES (%s) RETURNING v_id_jurnal"
            self.cursor.execute(insert_query, (nama_jurnal,))
            self.connection.commit()
            
            result = self.cursor.fetchone()
            logger.info(f"Created new jurnal: {nama_jurnal}")
            return result[0]
            
        except Exception as e:
            logger.error(f"Error getting/creating jurnal: {e}")
            self.connection.rollback()
            return None
    
    def create_publikasi(self, judul, jenis, tahun, total_sitasi=0, link_url=None):
        """Create publikasi record in stg_publikasi_tr"""
        try:
            # Validate jenis
            valid_jenis = ['artikel', 'buku', 'penelitian', 'prosiding']
            if jenis.lower() not in valid_jenis:
                jenis = 'artikel'  # default
            
            insert_query = """
                INSERT INTO stg_publikasi_tr 
                (v_judul, v_jenis, v_tahun_publikasi, n_total_sitasi, v_sumber, v_link_url) 
                VALUES (%s, %s, %s, %s, %s, %s) RETURNING v_id_publikasi
            """
            self.cursor.execute(insert_query, (judul, jenis.lower(), tahun, total_sitasi, 'SINTA_Garuda', link_url))
            self.connection.commit()
            
            result = self.cursor.fetchone()
            logger.info(f"Created new publikasi: {judul[:50]}... ({jenis}, {tahun})")
            return result[0]
            
        except Exception as e:
            logger.error(f"Error creating publikasi: {e}")
            self.connection.rollback()
            return None
    
    def create_artikel_details(self, id_publikasi, id_jurnal=None, volume=None, issue=None, pages=None, terindeks=None, ranking=None):
        """Create artikel details in stg_artikel_dr"""
        try:
            insert_query = """
                INSERT INTO stg_artikel_dr 
                (v_id_publikasi, v_id_jurnal, v_volume, v_issue, v_pages, v_terindeks, v_ranking) 
                VALUES (%s, %s, %s, %s, %s, %s, %s)
            """
            self.cursor.execute(insert_query, (id_publikasi, id_jurnal, volume, issue, pages, terindeks, ranking))
            self.connection.commit()
            logger.info(f"Created artikel details for publikasi ID: {id_publikasi}")
            return True
            
        except Exception as e:
            logger.error(f"Error creating artikel details: {e}")
            self.connection.rollback()
            return False
    
    def link_publikasi_dosen(self, id_publikasi, id_dosen, author_order=None):
        """Link publikasi with dosen in stg_publikasi_dosen_dt"""
        try:
            # Check if relationship already exists
            check_query = "SELECT 1 FROM stg_publikasi_dosen_dt WHERE v_id_publikasi = %s AND v_id_dosen = %s"
            self.cursor.execute(check_query, (id_publikasi, id_dosen))
            
            if self.cursor.fetchone():
                logger.info(f"Publikasi-Dosen relationship already exists: {id_publikasi}-{id_dosen}")
                return True
            
            insert_query = """
                INSERT INTO stg_publikasi_dosen_dt (v_id_publikasi, v_id_dosen, v_author_order) 
                VALUES (%s, %s, %s)
            """
            self.cursor.execute(insert_query, (id_publikasi, id_dosen, author_order))
            self.connection.commit()
            logger.info(f"Linked publikasi {id_publikasi} with dosen {id_dosen}")
            return True
            
        except Exception as e:
            logger.error(f"Error linking publikasi-dosen: {e}")
            self.connection.rollback()
            return False
    
    def add_sitasi_tahunan(self, id_publikasi, tahun, total_sitasi, sumber="SINTA_Garuda"):
        """Add yearly citation data in stg_publikasi_sitasi_tahunan_dr"""
        try:
            # Check if record exists for this year
            check_query = """
                SELECT v_id_sitasi FROM stg_publikasi_sitasi_tahunan_dr 
                WHERE v_id_publikasi = %s AND v_tahun = %s AND v_sumber = %s
            """
            self.cursor.execute(check_query, (id_publikasi, tahun, sumber))
            existing = self.cursor.fetchone()
            
            if existing:
                # Update existing record
                update_query = """
                    UPDATE stg_publikasi_sitasi_tahunan_dr 
                    SET n_total_sitasi_tahun = %s, t_tanggal_unduh = CURRENT_DATE
                    WHERE v_id_sitasi = %s
                """
                self.cursor.execute(update_query, (total_sitasi, existing[0]))
                logger.info(f"Updated sitasi tahunan for publikasi {id_publikasi}, tahun {tahun}")
            else:
                # Insert new record
                insert_query = """
                    INSERT INTO stg_publikasi_sitasi_tahunan_dr 
                    (v_id_publikasi, v_tahun, n_total_sitasi_tahun, v_sumber) 
                    VALUES (%s, %s, %s, %s)
                """
                self.cursor.execute(insert_query, (id_publikasi, tahun, total_sitasi, sumber))
                logger.info(f"Added sitasi tahunan for publikasi {id_publikasi}, tahun {tahun}")
            
            self.connection.commit()
            return True
            
        except Exception as e:
            logger.error(f"Error adding sitasi tahunan: {e}")
            self.connection.rollback()
            return False
    
    def get_all_dosen_with_sinta(self):
        """Retrieve all dosen with SINTA IDs from tmp_dosen_dt"""
        try:
            query = """
                SELECT v_id_dosen, v_nama_dosen, v_id_sinta, v_id_jurusan
                FROM tmp_dosen_dt
                WHERE v_id_sinta IS NOT NULL AND v_id_sinta != ''
                ORDER BY v_nama_dosen
            """
            self.cursor.execute(query)
            result = self.cursor.fetchall()
            
            # Get jurusan names
            dosen_list = []
            for row in result:
                jurusan_name = "Unknown"
                if row[3]:  # v_id_jurusan
                    jurusan_query = "SELECT v_nama_jurusan FROM stg_jurusan_mt WHERE v_id_jurusan = %s"
                    self.cursor.execute(jurusan_query, (row[3],))
                    jurusan_result = self.cursor.fetchone()
                    if jurusan_result:
                        jurusan_name = jurusan_result[0]
                
                dosen_list.append({
                    'id_dosen': row[0], 
                    'nama': row[1], 
                    'sinta_id': row[2], 
                    'jurusan': jurusan_name
                })
            
            return dosen_list
        except Exception as e:
            logger.error(f"Error retrieving dosen with SINTA: {e}")
            return []


class SintaGarudaScraper:
    def __init__(self, db_manager):
        self.session = requests.Session()
        self.headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8',
            'Accept-Language': 'en-US,en;q=0.5',
            'Accept-Encoding': 'gzip, deflate, br',
            'DNT': '1',
            'Connection': 'keep-alive',
            'Upgrade-Insecure-Requests': '1',
            'Sec-Fetch-Dest': 'document',
            'Sec-Fetch-Mode': 'navigate',
            'Sec-Fetch-Site': 'same-origin'
        }
        self.logged_in = False
        self.today = datetime.now().strftime("%Y-%m-%d")
        self.username = None
        self.password = None
        self.db = db_manager

    def login(self, username, password):
        """Login to SINTA before scraping"""
        self.username = username
        self.password = password
            
        # Try the general login endpoint
        if self._try_login("https://sinta.kemdikbud.go.id/logins"):
            return True
            
        logger.error("All login attempts failed")
        return False
        
    def _try_login(self, login_url):
        """Try to log in using a specific endpoint"""
        logger.info(f"Attempting login at: {login_url}")
        
        try:
            # Get the login page
            response = self.session.get(login_url, headers=self.headers)
            response.raise_for_status()
            
            soup = BeautifulSoup(response.text, 'html.parser')
            
            # Extract CSRF token if present
            csrf_token = soup.find('input', {'name': '_token'})
            
            # Find the form
            form = soup.find('form', {'id': 'loginform'}) or soup.find('form', {'method': 'post'}) or soup.find('form', {'action': True})
            
            post_url = login_url
            if form and form.has_attr('action'):
                post_url = urljoin(login_url, form['action'])
                logger.info(f"Found form action URL: {post_url}")
            
            # Prepare login data
            login_data = {}
            
            # Add hidden inputs from the form
            if form:
                for input_tag in form.find_all('input'):
                    if input_tag.has_attr('name') and input_tag.has_attr('value') and input_tag.get('type') == 'hidden':
                        login_data[input_tag['name']] = input_tag['value']
            
            # Add credentials
            email_field = soup.find('input', {'type': 'email'}) or soup.find('input', {'name': 'email'})
            if email_field and email_field.has_attr('name'):
                login_data[email_field['name']] = self.username
            else:
                login_data['email'] = self.username
            
            # Add password
            password_field = soup.find('input', {'type': 'password'})
            if password_field and password_field.has_attr('name'):
                login_data[password_field['name']] = self.password
            else:
                login_data['password'] = self.password
            
            # Add CSRF token if found
            if csrf_token:
                login_data['_token'] = csrf_token['value']
            
            # Set headers
            login_headers = self.headers.copy()
            login_headers['Referer'] = login_url
            login_headers['Origin'] = 'https://sinta.kemdikbud.go.id'
            login_headers['Content-Type'] = 'application/x-www-form-urlencoded'
            
            logger.info(f"Posting to: {post_url}")
            
            # Perform login
            response = self.session.post(
                post_url, 
                data=login_data, 
                headers=login_headers, 
                allow_redirects=True
            )
            response.raise_for_status()
            
            # Check if login was successful
            success_indicators = ["dashboard", "authors/profile"]
            failure_indicators = ["logins", "login", "signin", "sign-in"]
            
            if any(indicator in response.url for indicator in success_indicators) or \
               not any(indicator in response.url for indicator in failure_indicators):
                self.logged_in = True
                logger.info(f"Login successful! Redirected to: {response.url}")
                return True
            else:
                logger.warning(f"Login attempt failed. Current URL: {response.url}")
                return False
                
        except Exception as e:
            logger.error(f"Login error at {login_url}: {e}")
            return False

    def extract_clean_text(self, element):
        """Extract clean text from HTML element"""
        if not element:
            return "N/A"
        
        if isinstance(element, str):
            soup = BeautifulSoup(element, 'html.parser')
            return soup.get_text().strip()
        
        return element.get_text().strip() if element else "N/A"

    def extract_year_from_text(self, text):
        """Extract year from text"""
        if not text or text == "N/A":
            return None
        
        # Look for 4-digit year
        year_match = re.search(r'(19|20)\d{2}', text)
        if year_match:
            try:
                return int(year_match.group())
            except ValueError:
                pass
        
        return None

    def extract_publication_link(self, item):
        """Extract publication link from HTML element"""
        try:
            # Try various selectors for links
            link_selectors = ['a[href*="garuda"]', 'a[href*="article"]', 'a.pub-link', 'a.title-link']
            
            for selector in link_selectors:
                link_elem = item.select_one(selector)
                if link_elem and link_elem.has_attr('href'):
                    href = link_elem['href']
                    if href.startswith('/'):
                        return f"https://sinta.kemdikbud.go.id{href}"
                    elif href.startswith('http'):
                        return href
                    else:
                        return f"https://sinta.kemdikbud.go.id/{href}"
            
            # If no specific link found, try any link in the publication item
            links = item.find_all('a', href=True)
            for link in links:
                href = link['href']
                if any(keyword in href for keyword in ['garuda', 'article', 'pub', 'detail']):
                    if href.startswith('/'):
                        return f"https://sinta.kemdikbud.go.id{href}"
                    elif href.startswith('http'):
                        return href
                    else:
                        return f"https://sinta.kemdikbud.go.id/{href}"
            
            return None
            
        except Exception as e:
            logger.error(f"Error extracting publication link: {e}")
            return None

    def scrape_author_publications(self, dosen_data):
        """Scrape Garuda publications for an author and save to database"""
        logger.info(f"Scraping publications for {dosen_data['nama']} (SINTA: {dosen_data['sinta_id']})")
        
        base_url = f"https://sinta.kemdikbud.go.id/authors/profile/{dosen_data['sinta_id']}"
        
        # Try different URL patterns for Garuda publications
        possible_urls = [
            f"{base_url}?view=garuda",
            f"{base_url}/garuda",
            f"{base_url}?tab=garuda"
        ]
        
        publications_saved = 0
        
        for url in possible_urls:
            try:
                logger.info(f"Trying URL: {url}")
                response = self.session.get(url, headers=self.headers)
                response.raise_for_status()
                
                soup = BeautifulSoup(response.text, 'html.parser')
                
                # Look for publication items with various possible selectors
                pub_selectors = [
                    'div.ar-list-item',
                    'div.publication-item',
                    'div.pub-item',
                    'tr.publication-row',
                    'div.article-item',
                    'div.paper-item'
                ]
                
                publications_found = False
                
                for selector in pub_selectors:
                    pub_items = soup.select(selector)
                    if pub_items:
                        logger.info(f"Found {len(pub_items)} publications using selector: {selector}")
                        saved_count = self.parse_and_save_publications(pub_items, dosen_data)
                        publications_saved += saved_count
                        publications_found = True
                        break
                
                if publications_found:
                    break
                    
            except Exception as e:
                logger.error(f"Error accessing {url}: {e}")
                continue
        
        if publications_saved == 0:
            logger.warning(f"No publications found/saved for {dosen_data['nama']}")
        
        return publications_saved

    def parse_and_save_publications(self, pub_items, dosen_data):
        """Parse publication items from HTML and save to database"""
        publications_saved = 0
        
        # Get dosen data from database
        dosen_db = self.db.get_dosen_by_sinta_id(dosen_data['sinta_id'])
        if not dosen_db:
            logger.error(f"Dosen with Sinta ID {dosen_data['sinta_id']} not found in database")
            return 0
        
        id_dosen = dosen_db['id_dosen']
        
        for item in pub_items:
            try:
                # Extract title
                title_selectors = ['.ar-title', '.pub-title', '.title', 'h3', 'h4', '.article-title', '.paper-title']
                title = "N/A"
                for selector in title_selectors:
                    title_elem = item.select_one(selector)
                    if title_elem:
                        title = self.extract_clean_text(title_elem)
                        break
                
                # If no title found with selectors, try getting first text content
                if title == "N/A":
                    texts = item.get_text().strip().split('\n')
                    for text in texts:
                        if len(text.strip()) > 20:  # Assume title is longer than 20 chars
                            title = text.strip()
                            break
                
                if title == "N/A" or not title.strip() or len(title.strip()) < 10:
                    logger.warning("Skipping publication with no valid title")
                    continue
                
                # Extract publication link
                link_url = self.extract_publication_link(item)
                
                # Extract year
                year_selectors = ['.ar-year', '.year', '.pub-year', '.publication-year']
                year_text = "N/A"
                for selector in year_selectors:
                    year_elem = item.select_one(selector)
                    if year_elem:
                        year_text = self.extract_clean_text(year_elem)
                        break
                
                # If no year found with selectors, look in the text content
                if year_text == "N/A":
                    full_text = item.get_text()
                    year_match = re.search(r'(19|20)\d{2}', full_text)
                    if year_match:
                        year_text = year_match.group()
                
                # Parse year from text
                year = self.extract_year_from_text(year_text)
                if not year:
                    year = datetime.now().year
                    logger.warning(f"Could not extract year for publication '{title[:50]}...', using current year")
                
                # --- PERBAIKAN ---
                # Menambahkan lebih banyak kemungkinan selector untuk nama jurnal.
                # Anda mungkin perlu memeriksa halaman SINTA (Inspect Element) untuk menemukan selector yang paling akurat.
                journal_selectors = [
                    '.journal-name', 
                    '.ar-journal', 
                    '.pub-journal',
                    'div.ar-detail > a',      # Selector jika jurnal adalah link di dalam detail
                    'span.journal-title',     # Kemungkinan selector lain
                    'div.publication-source'  # Kemungkinan selector lain
                ]
                journal_name = None
                for selector in journal_selectors:
                    journal_elem = item.select_one(selector)
                    if journal_elem:
                        journal_name = self.extract_clean_text(journal_elem)
                        # Hapus teks yang tidak perlu jika ada (misal: "Journal: Jurnal ABC")
                        if journal_name and ':' in journal_name:
                            journal_name = journal_name.split(':')[-1].strip()
                        break
                
                # --- PERBAIKAN ---
                # Tambahkan log peringatan jika nama jurnal tidak berhasil ditemukan
                if not journal_name or journal_name == "N/A":
                    logger.warning(f"Nama jurnal tidak ditemukan untuk publikasi: '{title[:50]}...'")

                # Extract journal details (volume, issue, pages)
                volume = issue = pages = terindeks = ranking = None
                
                # Look for details container
                detail_selectors = ['.ar-detail', '.pub-details', '.article-info']
                for selector in detail_selectors:
                    detail_elem = item.select_one(selector)
                    if detail_elem:
                        detail_text = self.extract_clean_text(detail_elem)
                        
                        # Extract volume
                        vol_match = re.search(r'[Vv]ol\.?\s*(\d+)', detail_text)
                        if vol_match:
                            volume = vol_match.group(1)
                        
                        # Extract issue
                        issue_match = re.search(r'[Ii]ssue\.?\s*(\d+)', detail_text)
                        if issue_match:
                            issue = issue_match.group(1)
                        
                        # Extract pages
                        pages_match = re.search(r'[Pp]\.?\s*(\d+-\d+)', detail_text)
                        if pages_match:
                            pages = pages_match.group(1)
                        
                        # Extract indexing
                        if 'scopus' in detail_text.lower():
                            terindeks = 'Scopus'
                        elif 'wos' in detail_text.lower() or 'web of science' in detail_text.lower():
                            terindeks = 'WoS'
                        elif 'doaj' in detail_text.lower():
                            terindeks = 'DOAJ'
                        
                        # Extract ranking
                        rank_match = re.search(r'[Qq]([1-4])', detail_text)
                        if rank_match:
                            ranking = f"Q{rank_match.group(1)}"
                        elif 'sinta' in detail_text.lower():
                            sinta_match = re.search(r'[Ss]inta\s*([1-6])', detail_text)
                            if sinta_match:
                                ranking = f"Sinta {sinta_match.group(1)}"
                
                # Extract total citations (if available)
                citation_selectors = ['.ar-cited', '.citations', '.cite-count', '.citation-count']
                total_sitasi = 0
                for selector in citation_selectors:
                    cite_elem = item.select_one(selector)
                    if cite_elem:
                        cite_text = self.extract_clean_text(cite_elem)
                        cite_match = re.search(r'(\d+)', cite_text)
                        if cite_match:
                            try:
                                total_sitasi = int(cite_match.group(1))
                            except ValueError:
                                pass
                        break
                
                # Create publikasi record
                id_publikasi = self.db.create_publikasi(title, 'artikel', year, total_sitasi, link_url)
                
                if not id_publikasi:
                    logger.error(f"Failed to create publikasi record for: {title[:50]}...")
                    continue
                
                # Create journal if available and link to artikel details
                id_jurnal = None
                if journal_name and journal_name != "N/A":
                    id_jurnal = self.db.get_jurnal_id(journal_name)
                
                # Create artikel details
                self.db.create_artikel_details(id_publikasi, id_jurnal, volume, issue, pages, terindeks, ranking)
                
                # Link publikasi with dosen
                self.db.link_publikasi_dosen(id_publikasi, id_dosen)
                
                # Add citation data if available
                if total_sitasi > 0:
                    self.db.add_sitasi_tahunan(id_publikasi, year, total_sitasi, "SINTA_Garuda")
                
                publications_saved += 1
                logger.info(f"Saved publication: {title[:50]}... ({year}) - Citations: {total_sitasi}")
                
            except Exception as e:
                logger.error(f"Error processing publication item: {e}")
                continue
        
        return publications_saved


def process_single_author(scraper, sinta_id, nama_dosen, jurusan="Unknown"):
    """Process a single author and save to database"""
    logger.info(f"Processing author: {nama_dosen} (SINTA: {sinta_id})")
    
    try:
        dosen_data = {
            'nama': nama_dosen,
            'sinta_id': sinta_id,
            'jurusan': jurusan
        }
        
        # Scrape and save publications
        publications_saved = scraper.scrape_author_publications(dosen_data)
        
        if publications_saved > 0:
            logger.info(f"Saved {publications_saved} publications for {nama_dosen}")
        else:
            logger.info(f"No publications saved for {nama_dosen}")
        
        return publications_saved
            
    except Exception as e:
        logger.error(f"Error processing author {sinta_id}: {e}")
        return 0


def process_authors_from_csv(scraper, input_csv):
    """Process all authors from a CSV file"""
    if not os.path.exists(input_csv):
        logger.error(f"Input file '{input_csv}' not found.")
        return
    
    try:
        df = pd.read_csv(input_csv)
        
        # Handle different possible column names
        id_col = None
        name_col = None
        jurusan_col = None
        
        for col in df.columns:
            col_upper = col.upper()
            if any(x in col_upper for x in ['ID', 'SINTA']):
                id_col = col
            elif any(x in col_upper for x in ['NAMA', 'NAME']):
                name_col = col
            elif any(x in col_upper for x in ['JURUSAN', 'PROGRAM', 'DEPARTMENT']):
                jurusan_col = col
        
        if not id_col or not name_col:
            logger.error(f"Could not find required columns in CSV. Available columns: {df.columns.tolist()}")
            return
        
        # Generate batch ID for this processing session
        scraper.db.generate_batch_id()
        
        authors_processed = 0
        total_publications = 0
        
        for index, row in df.iterrows():
            try:
                sinta_id = str(row[id_col]).strip()
                nama_dosen = str(row[name_col]).strip()
                jurusan = str(row[jurusan_col]).strip() if jurusan_col else "Unknown"
                
                if not sinta_id or sinta_id.lower() in ['nan', 'none', '']:
                    logger.warning(f"Skipping row {index}: Invalid SINTA ID")
                    continue
                
                logger.info(f"Processing {index+1}/{len(df)}: {nama_dosen} (SINTA: {sinta_id})")
                
                pub_count = process_single_author(scraper, sinta_id, nama_dosen, jurusan)
                authors_processed += 1
                total_publications += pub_count
                
                # Add delay between authors
                if index < len(df) - 1:
                    delay = random.uniform(2, 5)
                    logger.info(f"Waiting {delay:.1f} seconds...")
                    sleep(delay)
                
            except Exception as e:
                logger.error(f"Error processing row {index}: {e}")
                continue
        
        logger.info(f"Batch processing completed. Authors: {authors_processed}, Publications: {total_publications}")
        
    except Exception as e:
        logger.error(f"Error reading CSV file: {e}")


def process_all_authors_from_db(scraper):
    """Process all authors already in the database"""
    logger.info("Retrieving all authors from database...")
    
    authors = scraper.db.get_all_dosen_with_sinta()
    if not authors:
        logger.warning("No authors with SINTA IDs found in database")
        return
    
    logger.info(f"Found {len(authors)} authors with SINTA IDs in database")
    
    # Generate batch ID for this processing session
    scraper.db.generate_batch_id()
    
    authors_processed = 0
    total_publications = 0
    
    for i, author in enumerate(authors):
        try:
            sinta_id = author['sinta_id']
            nama_dosen = author['nama']
            jurusan = author['jurusan']
            
            logger.info(f"Processing {i+1}/{len(authors)}: {nama_dosen} (SINTA: {sinta_id})")
            
            pub_count = process_single_author(scraper, sinta_id, nama_dosen, jurusan)
            authors_processed += 1
            total_publications += pub_count
            
            # Add delay between authors
            if i < len(authors) - 1:
                delay = random.uniform(2, 5)
                logger.info(f"Waiting {delay:.1f} seconds...")
                sleep(delay)
            
        except Exception as e:
            logger.error(f"Error processing author {sinta_id}: {e}")
            continue
    
    logger.info(f"Database processing completed. Authors: {authors_processed}, Publications: {total_publications}")


def main():
    """Main function with improved menu system"""
    print("SINTA GARUDA PUBLICATIONS SCRAPER - Fixed Database Integration")
    print("=" * 60)
    
    # Database configuration
    print("Database Configuration:")
    dbname = input("Database name (default: ProDSGabungan): ").strip() or "ProDSGabungan"
    user = input("Database user (default: postgres): ").strip() or "postgres"
    password = input("Database password: ").strip() or "password123"
    host = input("Database host (default: localhost): ").strip() or "localhost"
    port = input("Database port (default: 5432): ").strip() or "5432"
    
    # Initialize database
    db_manager = DatabaseManager(dbname, user, password, host, port)
    if not db_manager.connect():
        logger.error("Failed to connect to database. Exiting.")
        return
    
    # Initialize scraper
    scraper = SintaGarudaScraper(db_manager)
    
    # Login credentials
    print("\nSINTA Login Credentials:")
    username = input("Email: ").strip()
    password_input = input("Password: ").strip()
    
    if username and password_input:
        logger.info("Attempting to login to SINTA...")
        if scraper.login(username, password_input):
            logger.info("Login successful!")
        else:
            logger.warning("Login failed. Continuing without login (limited access).")
    else:
        logger.warning("No credentials provided. Continuing without login.")
    
    # Main menu loop
    while True:
        print("\n" + "=" * 60)
        print("MAIN MENU")
        print("=" * 60)
        print("1. Scrape single author")
        print("2. Batch scrape from CSV file")
        print("3. Process all authors from database")
        print("4. View database statistics")
        print("5. Test database connection")
        print("6. Clean up database tables")
        print("7. Exit")
        print("=" * 60)
        
        choice = input("Select option (1-7): ").strip()
        
        if choice == "1":
            print("\nSINGLE AUTHOR MODE")
            sinta_id = input("Enter SINTA ID: ").strip()
            nama_dosen = input("Enter author name: ").strip()
            jurusan = input("Enter jurusan (default: Unknown): ").strip() or "Unknown"
            
            if sinta_id and nama_dosen:
                # Generate batch ID for single author processing
                scraper.db.generate_batch_id()
                pub_count = process_single_author(scraper, sinta_id, nama_dosen, jurusan)
                print(f"Completed! Found {pub_count} publications.")
            else:
                print("Error: SINTA ID and name are required.")
        
        elif choice == "2":
            print("\nBATCH PROCESSING FROM CSV")
            csv_file = input("Enter CSV filename: ").strip()
            
            if csv_file and os.path.exists(csv_file):
                process_authors_from_csv(scraper, csv_file)
            else:
                print("Error: CSV file not found.")
        
        elif choice == "3":
            print("\nPROCESSING ALL AUTHORS FROM DATABASE")
            confirm = input("This will process all authors in database. Continue? (y/n): ").lower()
            
            if confirm == 'y':
                process_all_authors_from_db(scraper)
            else:
                print("Operation cancelled.")
        
        elif choice == "4":
            print("\nDATABASE STATISTICS")
            try:
                # Count records in each table
                tables_stats = [
                    ("stg_jurusan_mt", "Jurusan"),
                    ("tmp_dosen_dt", "Dosen"),
                    ("stg_jurnal_mt", "Jurnal"),
                    ("stg_publikasi_tr", "Publikasi"),
                    ("stg_artikel_dr", "Artikel Details"),
                    ("stg_publikasi_dosen_dt", "Publikasi-Dosen Links"),
                    ("stg_publikasi_sitasi_tahunan_dr", "Citation Data")
                ]
                
                for table_name, display_name in tables_stats:
                    try:
                        db_manager.cursor.execute(f"SELECT COUNT(*) FROM {table_name}")
                        count = db_manager.cursor.fetchone()[0]
                        print(f"{display_name}: {count} records")
                    except Exception as e:
                        print(f"{display_name}: Error - {e}")
                
                # Show recent publications
                print("\n--- Recent Publications ---")
                try:
                    db_manager.cursor.execute("""
                        SELECT 
                            d.v_nama_dosen,
                            p.v_judul,
                            p.v_tahun_publikasi,
                            p.n_total_sitasi
                        FROM stg_publikasi_tr p
                        JOIN stg_publikasi_dosen_dt pd ON p.v_id_publikasi = pd.v_id_publikasi
                        JOIN tmp_dosen_dt d ON pd.v_id_dosen = d.v_id_dosen
                        ORDER BY p.v_tahun_publikasi DESC, p.n_total_sitasi DESC
                        LIMIT 10
                    """)
                    recent_pubs = db_manager.cursor.fetchall()
                    
                    for pub in recent_pubs:
                        print(f"- {pub[0]}: {pub[1][:50]}... ({pub[2]}) - {pub[3]} citations")
                        
                except Exception as e:
                    print(f"Error fetching recent publications: {e}")
                    
            except Exception as e:
                print(f"Error generating statistics: {e}")
        
        elif choice == "5":
            print("\nDATABASE CONNECTION TEST")
            try:
                db_manager.cursor.execute("SELECT version();")
                version = db_manager.cursor.fetchone()[0]
                print(f"✓ Database connected successfully")
                print(f"PostgreSQL version: {version}")
                
                # Test table access
                test_tables = ["tmp_dosen_dt", "stg_publikasi_tr", "stg_jurusan_mt"]
                for table in test_tables:
                    try:
                        db_manager.cursor.execute(f"SELECT COUNT(*) FROM {table}")
                        count = db_manager.cursor.fetchone()[0]
                        print(f"✓ {table}: {count} records")
                    except Exception as e:
                        print(f"✗ {table}: Error - {e}")
                        
            except Exception as e:
                print(f"✗ Database connection failed: {e}")
        
        elif choice == "6":
            print("\nDATABASE CLEANUP")
            print("WARNING: This will delete all scraped data!")
            confirm = input("Type 'DELETE' to confirm: ")
            
            if confirm == "DELETE":
                try:
                    # Delete in correct order to respect foreign keys
                    tables_to_clean = [
                        "stg_publikasi_sitasi_tahunan_dr",
                        "stg_artikel_dr",
                        "stg_publikasi_dosen_dt",
                        "stg_publikasi_tr"
                    ]
                    
                    for table in tables_to_clean:
                        db_manager.cursor.execute(f"DELETE FROM {table}")
                        count = db_manager.cursor.rowcount
                        db_manager.connection.commit()
                        print(f"Cleaned {table}: {count} records deleted")
                    
                    print("Database cleanup completed successfully.")
                    
                except Exception as e:
                    print(f"Error during cleanup: {e}")
                    db_manager.connection.rollback()
            else:
                print("Cleanup cancelled.")
        
        elif choice == "7":
            print("Exiting program...")
            break
        
        else:
            print("Invalid option. Please choose 1-7.")
        
        # Pause before showing menu again
        input("\nPress Enter to continue...")
    
    # Cleanup
    db_manager.disconnect()
    logger.info("Program terminated successfully.")


if __name__ == "__main__":
    main()