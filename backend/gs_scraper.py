#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Google Scholar Scraper Module for Web Integration
"""

from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, NoSuchElementException
from webdriver_manager.chrome import ChromeDriverManager
import time
import random
from bs4 import BeautifulSoup
import pandas as pd
import re
import datetime
from roman import fromRoman
import psycopg2
from psycopg2 import sql
import os


class GoogleScholarScraper:
    """Google Scholar Scraper with database integration"""
    
    def __init__(self, db_config, job_id, progress_callback=None):
        self.db_config = db_config
        self.job_id = job_id
        self.progress_callback = progress_callback
        self.driver = None
        self.conn = None
        
    def emit_progress(self, data):
        """Emit progress update"""
        if self.progress_callback:
            try:
                self.progress_callback(data)
            except Exception as e:
                print(f"Error emitting progress: {e}")
    
    def connect_to_db(self):
        """Establish connection to PostgreSQL database"""
        try:
            self.conn = psycopg2.connect(**self.db_config)
            print("✓ Connected to database successfully!")
            return self.conn
        except Exception as e:
            print(f"✗ Error connecting to database: {e}")
            return None
    
    def setup_driver(self):
        """Setup and return WebDriver with appropriate configuration"""
        chrome_options = Options()
        
        # Basic configuration
        chrome_options.add_argument("--no-sandbox")
        chrome_options.add_argument("--disable-dev-shm-usage")
        chrome_options.add_argument("--disable-gpu")
        chrome_options.add_argument("--window-size=1920,1080")
        chrome_options.add_argument("--disable-extensions")
        chrome_options.add_argument("--disable-infobars")
        
        # User agent rotation
        user_agents = [
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        ]
        chrome_options.add_argument(f"--user-agent={random.choice(user_agents)}")
        
        # Anti-bot detection
        chrome_options.add_argument("--disable-blink-features=AutomationControlled")
        chrome_options.add_experimental_option("excludeSwitches", ["enable-automation"])
        chrome_options.add_experimental_option('useAutomationExtension', False)
        
        # Preferences
        prefs = {
            "profile.default_content_setting_values.notifications": 2,
            "profile.default_content_settings.popups": 0,
            "profile.managed_default_content_settings.images": 2,
        }
        chrome_options.add_experimental_option("prefs", prefs)
        
        try:
            service = Service(ChromeDriverManager().install())
            driver = webdriver.Chrome(service=service, options=chrome_options)
        except Exception as e:
            print(f"Error creating driver: {e}")
            driver = webdriver.Chrome(options=chrome_options)
        
        # Remove webdriver property
        try:
            driver.execute_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")
        except:
            pass
        
        driver.set_page_load_timeout(120)
        driver.implicitly_wait(30)
        
        # Add cookies
        try:
            driver.get("https://scholar.google.com")
            time.sleep(5)
        except:
            pass
        
        return driver
    
    def setup_driver_with_auto_login(self):
        """Setup driver and handle automatic login"""
        self.driver = self.setup_driver()
        
        try:
            self.driver.get("https://scholar.google.com")
            
            self.emit_progress({
                'message': 'Browser opened. Waiting for automatic navigation...',
                'status': 'waiting_login'
            })
            
            # Wait a bit for page to load
            time.sleep(10)
            
            # Check if we're logged in by looking for profile indicators
            try:
                # Look for sign-in button - if present, not logged in
                sign_in = self.driver.find_element(By.LINK_TEXT, "Sign in")
                print("⚠️  Not logged in. You may encounter CAPTCHA issues.")
            except:
                print("✓ Appears to be logged in or no sign-in required")
            
            self.emit_progress({
                'message': 'Ready to start scraping...',
                'status': 'ready'
            })
            
            return self.driver
            
        except Exception as e:
            print(f"Error during setup: {e}")
            return self.driver
    
    def get_authors_from_db(self, scrape_from_beginning=False):
        """Get list of authors from database"""
        cursor = None
        try:
            cursor = self.conn.cursor()
            
            if scrape_from_beginning:
                query = """
                    SELECT v_nama, v_link, COALESCE(v_status, 'pending') as status
                    FROM temp_dosenGS_scraping
                    WHERE v_link IS NOT NULL
                    ORDER BY v_nama
                """
            else:
                query = """
                    SELECT v_nama, v_link, COALESCE(v_status, 'pending') as status
                    FROM temp_dosenGS_scraping
                    WHERE v_link IS NOT NULL
                    AND (v_status IS NULL OR v_status IN ('pending', 'error', 'processing'))
                    ORDER BY 
                        CASE 
                            WHEN v_status = 'processing' THEN 1
                            WHEN v_status = 'error' THEN 2
                            ELSE 3
                        END,
                        v_nama
                """
            
            cursor.execute(query)
            results = cursor.fetchall()
            
            df = pd.DataFrame(results, columns=['Name', 'Profile URL', 'Status'])
            print(f"✓ Retrieved {len(df)} authors from database")
            
            return df
            
        except Exception as e:
            print(f"Error getting authors: {e}")
            return pd.DataFrame()
        finally:
            if cursor:
                cursor.close()
    
    def update_scraping_status(self, author_name, status, error_message=None):
        """Update scraping status for an author"""
        cursor = None
        try:
            cursor = self.conn.cursor()
            
            if status == 'error' and error_message:
                query = """
                    UPDATE temp_dosenGS_scraping
                    SET v_status = %s,
                        v_error_message = %s,
                        t_last_updated = NOW()
                    WHERE v_nama = %s
                """
                cursor.execute(query, (status, error_message, author_name))
            else:
                query = """
                    UPDATE temp_dosenGS_scraping
                    SET v_status = %s,
                        t_last_updated = NOW()
                    WHERE v_nama = %s
                """
                cursor.execute(query, (status, author_name))
            
            self.conn.commit()
            
        except Exception as e:
            self.conn.rollback()
            print(f"Error updating status: {e}")
        finally:
            if cursor:
                cursor.close()
    
    def get_publication_details(self, pub_url):
        """Extract detailed publication information from publication page"""
        original_window = self.driver.current_window_handle
        new_tab_created = False
        
        details = {
            'authors': '',
            'journal': 'N/A',
            'conference': 'N/A',
            'publisher': '',
            'volume': '',
            'issue': '',
            'pages': ''
        }
        
        try:
            try:
                self.driver.execute_script("window.open('');")
                new_tab_created = True
                
                if len(self.driver.window_handles) < 2:
                    return details
                    
                self.driver.switch_to.window(self.driver.window_handles[1])
            except Exception as e:
                print(f"Error opening new tab: {e}")
                return details
            
            try:
                self.driver.get(pub_url)
                time.sleep(random.uniform(4, 6))
            except Exception as e:
                print(f"Error loading publication page: {e}")
                return details
            
            try:
                WebDriverWait(self.driver, 25).until(
                    EC.presence_of_element_located((By.CSS_SELECTOR, '.gsc_oci_main, .gs_scl'))
                )
            except TimeoutException:
                print(f"Timeout waiting for main content at {pub_url}")
            
            # Scroll to load all content
            self.driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
            time.sleep(1.5)
            self.driver.execute_script("window.scrollTo(0, 0);")
            time.sleep(1.5)
            
            # Parse with BeautifulSoup
            page_source = self.driver.page_source
            soup = BeautifulSoup(page_source, 'html.parser')
            
            author_fields = soup.find_all('div', class_='gsc_oci_field')
            author_values = soup.find_all('div', class_='gsc_oci_value')
            
            for field, value in zip(author_fields, author_values):
                field_text = field.get_text().strip().lower()
                value_text = value.get_text().strip()
                
                if field_text == 'authors' or field_text == 'author':
                    details['authors'] = value_text
                elif field_text == 'journal':
                    details['journal'] = value_text
                    details['conference'] = 'N/A'
                elif field_text == 'conference':
                    details['conference'] = value_text
                    details['journal'] = 'N/A'
                elif field_text == 'publisher':
                    details['publisher'] = value_text
                elif field_text == 'source':
                    value_lower = value_text.lower()
                    if any(keyword in value_lower for keyword in ['journal', 'jurnal', 'acta', 'review', 'letters']):
                        details['journal'] = value_text
                        details['conference'] = 'N/A'
                    elif any(keyword in value_lower for keyword in ['conference', 'proceedings', 'symposium', 'workshop', 'konferensi', 'prosiding']):
                        details['conference'] = value_text
                        details['journal'] = 'N/A'
                    else:
                        if not details['publisher']:
                            details['publisher'] = value_text
                elif field_text == 'volume':
                    details['volume'] = value_text
                elif field_text == 'issue':
                    details['issue'] = value_text
                elif field_text == 'pages':
                    details['pages'] = value_text
            
            return details
            
        except Exception as e:
            print(f"Error retrieving details for publication {pub_url}: {str(e)}")
            return details
            
        finally:
            if new_tab_created:
                try:
                    if self.driver.session_id:
                        if len(self.driver.window_handles) > 1:
                            if self.driver.current_window_handle != original_window:
                                self.driver.close()
                            if original_window in self.driver.window_handles:
                                self.driver.switch_to.window(original_window)
                except Exception as e:
                    print(f"Error handling browser tabs: {e}")
    
    def classify_publication_type(self, journal, conference, publisher, title=""):
        """
        Klasifikasi jenis publikasi berdasarkan prioritas:
        1. Jika journal memiliki nilai (bukan N/A atau kosong) → artikel
        2. Jika conference memiliki nilai (bukan N/A atau kosong) → prosiding
        3. Jika keduanya tidak memiliki nilai → gunakan regex pada publisher dan title
        
        Return values sesuai database: 'artikel', 'prosiding', 'buku', 'penelitian', 'lainnya'
        """
        
        # Prioritas 1: Jika journal memiliki nilai (bukan N/A atau kosong)
        if journal and journal.strip() and journal != 'N/A':
            return 'artikel'
        
        # Prioritas 2: Jika conference memiliki nilai (bukan N/A atau kosong)
        if conference and conference.strip() and conference != 'N/A':
            return 'prosiding'
        
        # Prioritas 3: Jika kedua kolom tidak memiliki nilai, gunakan regex
        return self.classify_by_regex(publisher, title)
    
    def classify_by_regex(self, publisher, title=""):
        """
        Klasifikasi menggunakan regex jika journal dan conference tidak tersedia.
        Return values: 'artikel', 'prosiding', 'buku', 'penelitian', 'lainnya'
        """
        
        # Gabungkan publisher dan title untuk analisis
        combined_text = f"{publisher} {title}".lower()
        
        if pd.isna(combined_text) or combined_text.strip() == "":
            return 'lainnya'
        
        # Daftar penerbit buku terkenal
        book_publishers = ['nuansa aulia', 'citra aditya bakti', 'yrama widya', 
                          'pustaka belajar', 'pustaka pelajar', 'erlangga', 
                          'andpublisher', 'prenadamedia', 'gramedia', 'grasindo',
                          'media', 'prenhalindo', 'prenhallindo', 'wiley', 'springer']
        
        # Deteksi penerbit buku
        if any(pub in combined_text for pub in book_publishers):
            return 'buku'
        
        # Prioritas untuk buku jika ada kata "edisi"
        if 'edisi' in combined_text:
            return 'buku'
        
        # Deteksi jurnal/artikel
        if any(keyword in combined_text for keyword in ['jurnal', 'journal', 'jou.', 'j.', 'acta', 'review', 'letters']):
            return 'artikel'
        
        # Deteksi prosiding konferensi
        if any(keyword in combined_text for keyword in ['prosiding', 'proceedings', 'proc.', 'konferensi', 'conference', 
                                                       'conf.', 'simposium', 'symposium', 'workshop', 'pertemuan', 'meeting']):
            return 'prosiding'
        
        # Deteksi buku
        if any(keyword in combined_text for keyword in ['buku', 'book', 'bab buku', 'chapter', 'handbook', 'ensiklopedia', 
                                                       'encyclopedia', 'buku teks', 'textbook', 'penerbit', 'publisher', 'press', 
                                                       'books']):
            return 'buku'
        
        # Deteksi tesis/disertasi - masuk kategori 'penelitian'
        if any(keyword in combined_text for keyword in ['tesis', 'thesis', 'disertasi', 'dissertation', 'skripsi', 'program doktor',
                                                       'program pascasarjana', 'phd', 'master', 'doctoral', 'program studi', 'fakultas']):
            return 'penelitian'
        
        # Deteksi laporan penelitian - masuk kategori 'penelitian'
        if any(keyword in combined_text for keyword in ['analisis', 'analysis', 'penelitian', 'research']):
            return 'penelitian'
        
        # Deteksi preprint/laporan teknis - masuk kategori 'penelitian'
        if any(keyword in combined_text for keyword in ['arxiv', 'preprint', 'laporan teknis', 'technical report', 
                                                       'naskah awal', 'working paper', 'teknis']):
            return 'penelitian'
        
        # Deteksi paten - masuk kategori 'penelitian'
        if 'paten' in combined_text or 'patent' in combined_text:
            return 'penelitian'
        
        # Deteksi referensi hukum/undang-undang - masuk kategori 'buku'
        if re.search(r'\bUU\s*No\.\s*\d+|Undang-undang\s*Nomor\s*\d+|Peraturan\s*(Pemerintah|Presiden)\s*No\.\s*\d+', 
                    combined_text):
            return 'buku'
        
        # Deteksi berdasarkan format volume/issue - indikasi jurnal
        if re.search(r'vol\.|\bvol\b|\bedisi\b|\bno\.|\bhal\.|\bhalaman\b', combined_text) or \
           re.search(r'\bvol\.\s*\d+\s*(\(\s*\d+\s*\))?', combined_text) or \
           re.search(r'\d+\s*\(\d+\)', combined_text):
            return 'artikel'
        
        # Default: Jika tidak terdeteksi sebagai tipe apapun
        return 'lainnya'
    
    def scrape_profile(self, profile_url, author_name):
        """Scrape Google Scholar profile"""
        try:
            print(f"Accessing profile: {author_name}")
            
            self.driver.get(profile_url)
            time.sleep(random.uniform(5, 8))
            
            # Extract Scholar ID
            scholar_id = ""
            if "user=" in profile_url:
                scholar_id = profile_url.split("user=")[1].split("&")[0]
            
            # Extract profile information
            try:
                name = WebDriverWait(self.driver, 20).until(
                    EC.presence_of_element_located((By.CSS_SELECTOR, '#gsc_prf_in'))
                ).text
            except TimeoutException:
                return None
            
            try:
                affiliation = self.driver.find_element(By.CSS_SELECTOR, '.gsc_prf_il').text
            except:
                affiliation = ""
            
            # Extract citation stats
            citation_stats = self.driver.find_elements(By.CSS_SELECTOR, '#gsc_rsb_st tbody tr')
            citation_data = {}
            
            for stat in citation_stats:
                metric_name = stat.find_element(By.CSS_SELECTOR, 'td:nth-of-type(1)').text
                all_citations = stat.find_element(By.CSS_SELECTOR, 'td:nth-of-type(2)').text
                recent_citations = stat.find_element(By.CSS_SELECTOR, 'td:nth-of-type(3)').text
                citation_data[f"{metric_name}_all"] = all_citations
                citation_data[f"{metric_name}_since2020"] = recent_citations
            
            # Extract citations per year
            citations_per_year = {}
            try:
                chart = self.driver.find_element(By.CSS_SELECTOR, '#gsc_g')
                years = chart.find_elements(By.CSS_SELECTOR, '.gsc_g_t')
                values = chart.find_elements(By.CSS_SELECTOR, '.gsc_g_al')
                
                for year_element, value_element in zip(years, values):
                    year = year_element.text.strip()
                    if year.isdigit() and 2015 <= int(year) <= 2024:
                        style = value_element.get_attribute('style')
                        citations = style.split(':')[-1].strip('%') if style else '0'
                        citations_per_year[year] = int(citations) if citations.isdigit() else 0
            except:
                pass
            
            # Extract publications
            publications = []
        
            # Click "Show more" until all loaded
            while True:
                try:
                    show_more = self.driver.find_element(By.ID, 'gsc_bpf_more')
                    if show_more.get_attribute('disabled'):
                        break
                    show_more.click()
                    time.sleep(random.uniform(2, 3))
                except:
                    break
            
            # Scrape publications
            pub_items = self.driver.find_elements(By.CSS_SELECTOR, '#gsc_a_b .gsc_a_tr')
            
            for item in pub_items:
                try:
                    title_element = item.find_element(By.CSS_SELECTOR, '.gsc_a_t a')
                    title = title_element.text
                    pub_link = title_element.get_attribute('href')
                    
                    # Get detailed publication info
                    pub_details = self.get_publication_details(pub_link)
                    
                    authors = item.find_element(By.CSS_SELECTOR, '.gs_gray:nth-of-type(1)').text
                    venue_fallback = item.find_element(By.CSS_SELECTOR, '.gs_gray:nth-of-type(2)').text
                    citations = item.find_element(By.CSS_SELECTOR, '.gsc_a_c a').text or "0"
                    year = item.find_element(By.CSS_SELECTOR, '.gsc_a_y span').text or "N/A"
                    
                    # **TAMBAHKAN INI**: Get citations per year untuk publikasi ini
                    pub_citations_per_year = self.get_publication_citations_per_year(pub_link)
                    
                    # Classify publication type using the improved method
                    pub_type = self.classify_publication_type(
                        pub_details.get('journal', 'N/A'),
                        pub_details.get('conference', 'N/A'),
                        pub_details.get('publisher', ''),
                        title
                    )
                    
                    pub_data = {
                        'title': title,
                        'authors': pub_details.get('authors') or authors,
                        'venue': venue_fallback,
                        'journal': pub_details.get('journal', 'N/A'),
                        'conference': pub_details.get('conference', 'N/A'),
                        'publisher': pub_details.get('publisher', ''),
                        'year': year,
                        'citations': citations,
                        'link': pub_link,
                        'Author': author_name,
                        'publication_type': pub_type,
                        'volume': pub_details.get('volume', ''),
                        'issue': pub_details.get('issue', ''),
                        'pages': pub_details.get('pages', ''),
                        'citations_per_year': pub_citations_per_year  # **TAMBAHKAN INI**
                    }
                    
                    publications.append(pub_data)
                    time.sleep(random.uniform(1, 2))  # Delay antar publikasi
                    
                except Exception as e:
                    print(f"Error extracting publication: {e}")
            
            profile_data = {
                'name': name,
                'affiliation': affiliation,
                'profile_url': profile_url,
                'scholar_id': scholar_id,
                'citation_stats': citation_data,
                'citations_per_year': citations_per_year,
                'publications': publications
            }
            
            return profile_data
            
        except Exception as e:
            print(f"Error scraping profile: {e}")
            return None
        
    def get_publication_citations_per_year(self, pub_url):
        """Extract citations per year for a specific publication"""
        original_window = self.driver.current_window_handle
        new_tab_created = False
        
        try:
            try:
                self.driver.execute_script("window.open('');")
                new_tab_created = True
                
                if len(self.driver.window_handles) < 2:
                    return {}
                    
                self.driver.switch_to.window(self.driver.window_handles[1])
            except Exception as e:
                print(f"Error opening new tab: {e}")
                return {}
            
            try:
                self.driver.get(pub_url)
                time.sleep(random.uniform(4, 6))
            except Exception as e:
                print(f"Error loading publication page: {e}")
                return {}
            
            try:
                WebDriverWait(self.driver, 25).until(
                    EC.presence_of_element_located((By.CSS_SELECTOR, '.gsc_oci_main, .gs_scl'))
                )
            except TimeoutException:
                print(f"Timeout waiting for main content at {pub_url}")
            
            # Scroll to load all content
            self.driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
            time.sleep(1.5)
            self.driver.execute_script("window.scrollTo(0, 0);")
            time.sleep(1.5)
            
            # Parse with BeautifulSoup
            page_source = self.driver.page_source
            soup = BeautifulSoup(page_source, 'html.parser')
            
            citations_per_year = {}
            
            # Extract year elements
            year_elements = soup.select('.gsc_oci_g_t')
            citation_elements = soup.select('.gsc_oci_g_a')
            
            # Initialize years with 0 citations
            for year_element in year_elements:
                year = year_element.text.strip()
                if year.isdigit() and 2000 <= int(year) <= 2030:
                    citations_per_year[year] = 0
            
            # Map citation values to years based on position
            for citation_element in citation_elements:
                style = citation_element.get('style', '')
                left_match = re.search(r'left:([0-9]+)px', style)
                if not left_match:
                    continue
                    
                left_pos = int(left_match.group(1))
                closest_year = None
                min_distance = float('inf')
                
                for year_element in year_elements:
                    year_style = year_element.get('style', '')
                    year_left_match = re.search(r'left:([0-9]+)px', year_style)
                    if not year_left_match:
                        continue
                        
                    year_left_pos = int(year_left_match.group(1))
                    distance = abs(year_left_pos - left_pos)
                    
                    if distance < min_distance:
                        min_distance = distance
                        closest_year = year_element.text.strip()
                
                if closest_year and closest_year.isdigit() and 2000 <= int(closest_year) <= 2030:
                    citation_value_element = citation_element.select_one('.gsc_oci_g_al')
                    if citation_value_element:
                        citation_value = citation_value_element.text.strip()
                        if citation_value.isdigit():
                            citations_per_year[closest_year] = int(citation_value)
            
            return citations_per_year
            
        except Exception as e:
            print(f"Error retrieving citations per year: {e}")
            return {}
            
        finally:
            if new_tab_created:
                try:
                    if self.driver.session_id:
                        if len(self.driver.window_handles) > 1:
                            if self.driver.current_window_handle != original_window:
                                self.driver.close()
                            if original_window in self.driver.window_handles:
                                self.driver.switch_to.window(original_window)
                except Exception as e:
                    print(f"Error handling browser tabs: {e}")
    
    def save_to_csv(self, profile_data):
        """Save profile and publications to CSV"""
        try:
            # Save profile
            profile_entry = {
                'Name': profile_data['name'],
                'Affiliation': profile_data['affiliation'],
                'Profile URL': profile_data['profile_url'],
                'ID Google Scholar': profile_data['scholar_id'],
                **profile_data['citation_stats'],
                'Total_Publikasi': len(profile_data['publications']),
                'Tanggal_Unduh': datetime.datetime.now().strftime('%Y-%m-%d')
            }
            
            profile_df = pd.DataFrame([profile_entry])
            
            profiles_csv = 'all_dosen_data_profiles.csv'
            header_needed = not os.path.exists(profiles_csv) or os.path.getsize(profiles_csv) == 0
            profile_df.to_csv(profiles_csv, mode='a', header=header_needed, index=False, encoding='utf-8')
            
            # Save publications with all fields
            pubs_csv = 'all_dosen_data_publications.csv'
            
            # Add publication_type for CSV if not exists
            pubs_data = []
            for pub in profile_data['publications']:
                pub_entry = {
                    'title': pub.get('title', ''),
                    'authors': pub.get('authors', ''),
                    'venue': pub.get('venue', ''),
                    'journal': pub.get('journal', 'N/A'),
                    'conference': pub.get('conference', 'N/A'),
                    'publisher': pub.get('publisher', ''),
                    'publication_type': pub.get('publication_type', 'lainnya'),
                    'volume': pub.get('volume', ''),
                    'issue': pub.get('issue', ''),
                    'pages': pub.get('pages', ''),
                    'year': pub.get('year', 'N/A'),
                    'citations': pub.get('citations', '0'),
                    'link': pub.get('link', ''),
                    'Author': pub.get('Author', '')
                }
                pubs_data.append(pub_entry)
            
            pubs_df = pd.DataFrame(pubs_data)
            header_needed = not os.path.exists(pubs_csv) or os.path.getsize(pubs_csv) == 0
            pubs_df.to_csv(pubs_csv, mode='a', header=header_needed, index=False, encoding='utf-8')
            
            print(f"✓ Saved to CSV: {len(profile_data['publications'])} publications")
            
        except Exception as e:
            print(f"Error saving to CSV: {e}")
    
    def import_to_database(self, profile_data):
        """Import profile and publications to database"""
        cursor = None
        try:
            cursor = self.conn.cursor()
            
            # Import dosen profile
            scholar_id = profile_data.get('scholar_id', '')
            
            cursor.execute(
                "SELECT v_id_dosen FROM tmp_dosen_dt WHERE v_id_googlescholar = %s",
                (scholar_id,)
            )
            result = cursor.fetchone()
            
            if result:
                # Update existing
                dosen_id = result[0]
                cursor.execute(sql.SQL("""
                    UPDATE tmp_dosen_dt SET 
                    v_nama_dosen = %s,
                    n_total_publikasi = %s,
                    n_total_sitasi_gs = %s,
                    n_h_index_gs = %s,
                    n_h_index_gs2020 = %s,
                    n_i10_index_gs = %s,
                    n_i10_index_gs2020 = %s,
                    v_sumber = %s,
                    t_tanggal_unduh = %s,
                    v_link_url = %s
                    WHERE v_id_dosen = %s
                """), (
                    profile_data.get('name', ''),
                    len(profile_data.get('publications', [])),
                    int(profile_data['citation_stats'].get('Citations_all', 0)) if 'Citations_all' in profile_data['citation_stats'] else 0,
                    int(profile_data['citation_stats'].get('h-index_all', 0)) if 'h-index_all' in profile_data['citation_stats'] else 0,
                    int(profile_data['citation_stats'].get('h-index_since2020', 0)) if 'h-index_since2020' in profile_data['citation_stats'] else 0,
                    int(profile_data['citation_stats'].get('i10-index_all', 0)) if 'i10-index_all' in profile_data['citation_stats'] else 0,
                    int(profile_data['citation_stats'].get('i10-index_since2020', 0)) if 'i10-index_since2020' in profile_data['citation_stats'] else 0,
                    'Google Scholar',
                    datetime.datetime.now(),
                    profile_data.get('profile_url', ''),
                    dosen_id
                ))
            else:
                # Insert new
                cursor.execute(sql.SQL("""
                    INSERT INTO tmp_dosen_dt (
                        v_nama_dosen, n_total_publikasi, n_total_sitasi_gs,
                        v_id_googlescholar, n_h_index_gs, n_h_index_gs2020,
                        n_i10_index_gs, n_i10_index_gs2020, v_sumber, t_tanggal_unduh,
                        v_link_url
                    ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                    RETURNING v_id_dosen
                """), (
                    profile_data.get('name', ''),
                    len(profile_data.get('publications', [])),
                    int(profile_data['citation_stats'].get('Citations_all', 0)) if 'Citations_all' in profile_data['citation_stats'] else 0,
                    scholar_id,
                    int(profile_data['citation_stats'].get('h-index_all', 0)) if 'h-index_all' in profile_data['citation_stats'] else 0,
                    int(profile_data['citation_stats'].get('h-index_since2020', 0)) if 'h-index_since2020' in profile_data['citation_stats'] else 0,
                    int(profile_data['citation_stats'].get('i10-index_all', 0)) if 'i10-index_all' in profile_data['citation_stats'] else 0,
                    int(profile_data['citation_stats'].get('i10-index_since2020', 0)) if 'i10-index_since2020' in profile_data['citation_stats'] else 0,
                    'Google Scholar',
                    datetime.datetime.now(),
                    profile_data.get('profile_url', '')
                ))
                dosen_id = cursor.fetchone()[0]
            
            # Import publications
            imported_count = 0
            for pub in profile_data.get('publications', []):
                try:
                    # Normalize publication type
                    pub_type_raw = pub.get('publication_type', 'lainnya')
                    pub_type = normalize_publication_type(pub_type_raw)
                    
                    # Parse year
                    try:
                        year = int(pub.get('year', 'N/A')) if pub.get('year') != 'N/A' else None
                    except:
                        year = None
                    
                    # Insert to main table
                    cursor.execute(sql.SQL("""
                        INSERT INTO stg_publikasi_tr (
                            v_judul, v_jenis, v_tahun_publikasi, n_total_sitasi,
                            v_sumber, v_link_url, t_tanggal_unduh, v_authors, v_publisher
                        ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                        RETURNING v_id_publikasi
                    """), (
                        pub.get('title', ''),
                        pub_type,
                        year,
                        int(pub.get('citations', 0)) if pub.get('citations') else 0,
                        'Google Scholar',
                        pub.get('link', ''),
                        datetime.datetime.now(),
                        pub.get('authors', ''),
                        pub.get('publisher', '')
                    ))
                    pub_id = cursor.fetchone()[0]
                    
                    # Insert to specific type table using helper methods
                    if pub_type == 'artikel':
                        self._insert_artikel_data(cursor, pub_id, pub)
                    elif pub_type == 'prosiding':
                        self._insert_prosiding_data(cursor, pub_id, pub)
                    elif pub_type == 'buku':
                        self._insert_buku_data(cursor, pub_id, pub)
                    elif pub_type == 'penelitian':
                        self._insert_penelitian_data(cursor, pub_id, pub)
                    else:
                        self._insert_lainnya_data(cursor, pub_id, pub)
                    
                    # **TAMBAHKAN INI**: Insert sitasi per tahun jika ada
                    if 'citations_per_year' in pub and pub['citations_per_year']:
                        self._insert_sitasi_tahunan_batch(cursor, pub_id, pub['citations_per_year'])
                    
                    # Link dosen to publication
                    cursor.execute(sql.SQL("""
                        SELECT 1 FROM stg_publikasi_dosen_dt 
                        WHERE v_id_publikasi = %s AND v_id_dosen = %s
                    """), (pub_id, dosen_id))
                    
                    if not cursor.fetchone():
                        cursor.execute(sql.SQL("""
                            INSERT INTO stg_publikasi_dosen_dt (
                                v_id_publikasi, v_id_dosen, v_author_order
                            ) VALUES (%s, %s, %s)
                        """), (pub_id, dosen_id, "1"))
                    
                    imported_count += 1
                
                except Exception as e:
                    print(f"   Error importing publication: {e}")
                    continue
            
            self.conn.commit()
            print(f"✓ Successfully imported: {imported_count} publications")
            return imported_count
            
        except Exception as e:
            self.conn.rollback()
            print(f"Error importing to database: {e}")
            raise
        finally:
            if cursor:
                cursor.close()

    def _insert_artikel_data(self, cursor, pub_id, pub):
        """Insert data spesifik artikel/jurnal"""
        try:
            # Ambil nama jurnal dari pub data
            journal_name = pub.get('journal', '')
            
            # Jika tidak ada nama jurnal, skip insert ke stg_artikel_dr
            if not journal_name or journal_name == 'N/A':
                print(f"    Warning: Artikel tanpa nama jurnal, skip insert artikel data")
                return
            
            # Cek apakah jurnal sudah ada di stg_jurnal_mt
            check_journal_query = sql.SQL("""
                SELECT v_id_jurnal FROM stg_jurnal_mt WHERE v_nama_jurnal = %s
            """)
            cursor.execute(check_journal_query, (journal_name,))
            result = cursor.fetchone()
            
            if result:
                # Jurnal sudah ada, ambil ID-nya
                journal_id = result[0]
            else:
                # Jurnal belum ada, insert baru
                insert_journal_query = sql.SQL("""
                    INSERT INTO stg_jurnal_mt (v_nama_jurnal)
                    VALUES (%s)
                    RETURNING v_id_jurnal
                """)
                cursor.execute(insert_journal_query, (journal_name,))
                journal_id = cursor.fetchone()[0]
            
            # Insert ke stg_artikel_dr dengan v_id_jurnal
            insert_artikel_query = sql.SQL("""
                INSERT INTO stg_artikel_dr (v_id_publikasi, v_id_jurnal, v_volume, v_issue, v_pages, t_updated_at)
                VALUES (%s, %s, %s, %s, %s, %s)
            """)
            
            values = (
                pub_id,
                journal_id,
                pub.get('volume', ''),
                pub.get('issue', ''),
                pub.get('pages', ''),
                datetime.datetime.now()
            )
            
            cursor.execute(insert_artikel_query, values)
        
        except Exception as e:
            print(f"    Error insert artikel data: {e}")

    def _insert_prosiding_data(self, cursor, pub_id, pub):
        """Insert data spesifik prosiding"""
        try:
            insert_query = sql.SQL("""
                INSERT INTO stg_prosiding_dr (v_id_publikasi, v_nama_konferensi, f_terindeks_scopus, t_updated_at)
                VALUES (%s, %s, %s, %s)
            """)
            
            values = (
                pub_id,
                pub.get('conference', ''),
                False,
                datetime.datetime.now()
            )
            
            cursor.execute(insert_query, values)
        except Exception as e:
            print(f"    Error insert prosiding data: {e}")

    def _insert_buku_data(self, cursor, pub_id, pub):
        """Insert data spesifik buku"""
        try:
            insert_query = sql.SQL("""
                INSERT INTO stg_buku_dr (v_id_publikasi, v_isbn, t_updated_at)
                VALUES (%s, %s, %s)
            """)
            
            values = (
                pub_id,
                '',
                datetime.datetime.now()
            )
            
            cursor.execute(insert_query, values)
        except Exception as e:
            print(f"    Error insert buku data: {e}")

    def _insert_penelitian_data(self, cursor, pub_id, pub):
        """Insert data publikasi penelitian (tesis/disertasi)"""
        try:
            insert_query = sql.SQL("""
                INSERT INTO stg_penelitian_dr (v_id_publikasi, v_kategori_penelitian, t_updated_at)
                VALUES (%s, %s, %s)
            """)
            
            pub_type_raw = str(pub.get('publication_type', '')).lower()
            if 'tesis' in pub_type_raw:
                kategori = 'Tesis'
            elif 'disertasi' in pub_type_raw:
                kategori = 'Disertasi'
            else:
                kategori = 'Penelitian'
            
            values = (
                pub_id,
                kategori,
                datetime.datetime.now()
            )
            
            cursor.execute(insert_query, values)
        except Exception as e:
            print(f"    Error insert penelitian data: {e}")

    def _insert_lainnya_data(self, cursor, pub_id, pub):
        """Insert data publikasi lainnya"""
        try:
            insert_query = sql.SQL("""
                INSERT INTO stg_lainnya_dr (v_id_publikasi, v_keterangan, t_updated_at)
                VALUES (%s, %s, %s)
            """)
            
            values = (
                pub_id,
                None,
                datetime.datetime.now()
            )
            
            cursor.execute(insert_query, values)
        except Exception as e:
            print(f"    Error insert lainnya data: {e}")

    def _insert_sitasi_tahunan_batch(self, cursor, pub_id, citations_per_year):
        """Insert data sitasi per tahun untuk satu publikasi (batch insert)"""
        try:
            if not citations_per_year or not isinstance(citations_per_year, dict):
                return
            
            # Insert setiap tahun
            for year, citations in citations_per_year.items():
                try:
                    # Validasi tahun
                    if not str(year).isdigit():
                        continue
                    
                    year_int = int(year)
                    citations_int = int(citations) if citations else 0
                    
                    # Skip jika tahun tidak valid
                    if year_int < 2000 or year_int > 2030:
                        continue
                    
                    insert_query = sql.SQL("""
                        INSERT INTO stg_publikasi_sitasi_tahunan_dr 
                        (v_id_publikasi, v_tahun, n_total_sitasi_tahun, v_sumber, t_tanggal_unduh)
                        VALUES (%s, %s, %s, %s, %s)
                    """)
                    
                    values = (
                        pub_id,
                        year_int,
                        citations_int,
                        'Google Scholar',
                        datetime.datetime.now().date()
                    )
                    
                    cursor.execute(insert_query, values)
                    
                except Exception as e:
                    print(f"    Error insert sitasi untuk tahun {year}: {e}")
                    continue
            
        except Exception as e:
            print(f"    Error insert sitasi tahunan batch: {e}")

    def run(self, max_authors=10, scrape_from_beginning=False):
        """Main scraping execution"""
        try:
            # Connect to database
            if not self.connect_to_db():
                raise Exception("Failed to connect to database")
            
            # Get authors
            df = self.get_authors_from_db(scrape_from_beginning)
            if df.empty:
                raise Exception("No authors to scrape")
            
            max_authors = min(max_authors, len(df))
            
            # Setup driver
            self.emit_progress({
                'message': 'Setting up browser...',
                'current': 0,
                'total': max_authors
            })
            
            self.setup_driver_with_auto_login()
            
            if not self.driver:
                raise Exception("Failed to setup driver")
            
            # Start scraping
            successful = 0
            failed = 0
            
            try:
                for index, row in df.head(max_authors).iterrows():
                    author_name = row['Name']
                    profile_url = row['Profile URL']
                    
                    self.emit_progress({
                        'message': f'Scraping {author_name} ({index + 1}/{max_authors})...',
                        'current': index + 1,
                        'total': max_authors,
                        'status': 'running'
                    })
                    
                    self.update_scraping_status(author_name, 'processing')
                    
                    try:
                        profile_data = self.scrape_profile(profile_url, author_name)
                        
                        if profile_data and profile_data['publications']:
                            self.save_to_csv(profile_data)
                            self.import_to_database(profile_data)
                            self.update_scraping_status(author_name, 'completed')
                            successful += 1
                        else:
                            self.update_scraping_status(author_name, 'error', 'No publications found')
                            failed += 1
                    
                    except Exception as e:
                        self.update_scraping_status(author_name, 'error', str(e))
                        failed += 1
                    
                    # Delay between scrapes
                    if index < max_authors - 1:
                        delay = random.uniform(60, 120)
                        self.emit_progress({
                            'message': f'Waiting {delay:.1f}s before next scrape...',
                            'current': index + 1,
                            'total': max_authors
                        })
                        time.sleep(delay)
            
            finally:
                if self.driver:
                    self.driver.quit()
            
            return {
                'success': True,
                'message': f'Completed scraping {successful + failed} authors',
                'summary': {
                    'total_attempted': successful + failed,
                    'successful': successful,
                    'failed': failed
                }
            }
            
        except Exception as e:
            print(f"Error in main run: {e}")
            raise
        finally:
            if self.conn:
                self.conn.close()

def normalize_publication_type(pub_type):
    """
    Normalisasi tipe publikasi ke format yang sesuai dengan constraint database
    Database menerima: 'artikel', 'buku', 'penelitian', 'prosiding', 'lainnya'
    """
    pub_type_lower = str(pub_type).lower().strip()

    if 'jurnal' in pub_type_lower or 'artikel' in pub_type_lower:
        return 'artikel'
    elif 'prosiding' in pub_type_lower or 'conference' in pub_type_lower:
        return 'prosiding'
    elif 'buku' in pub_type_lower or 'book' in pub_type_lower:
        return 'buku'
    elif 'penelitian' in pub_type_lower or 'tesis' in pub_type_lower or 'disertasi' in pub_type_lower:
        return 'penelitian'
    else:
        return 'lainnya'