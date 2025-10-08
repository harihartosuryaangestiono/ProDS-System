#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Google Scholar Scraper untuk Web Application
"""

import selenium
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

class GoogleScholarScraper:
    def __init__(self, db_config, job_id=None, progress_callback=None):
        """
        Initialize scraper
        
        Args:
            db_config: Dictionary dengan konfigurasi database
            job_id: ID untuk job tracking
            progress_callback: Function untuk update progress
        """
        self.db_config = db_config
        self.job_id = job_id
        self.progress_callback = progress_callback
        self.driver = None
        self.conn = None
        
    def emit_progress(self, status, message, current=0, total=0, **kwargs):
        """Emit progress update"""
        if self.progress_callback:
            data = {
                'status': status,
                'message': message,
                'current': current,
                'total': total,
                **kwargs
            }
            self.progress_callback(data)
    
    def connect_db(self):
        """Connect to database"""
        try:
            self.conn = psycopg2.connect(**self.db_config)
            return True
        except Exception as e:
            self.emit_progress('error', f'Database connection failed: {str(e)}')
            return False
    
    def setup_driver(self):
        """Setup Chrome WebDriver"""
        self.emit_progress('running', 'Setting up Chrome driver...')
        
        chrome_options = Options()
        chrome_options.add_argument("--no-sandbox")
        chrome_options.add_argument("--disable-dev-shm-usage")
        chrome_options.add_argument("--disable-gpu")
        chrome_options.add_argument("--window-size=1920,1080")
        chrome_options.add_argument("--disable-extensions")
        chrome_options.add_argument("--disable-blink-features=AutomationControlled")
        chrome_options.add_experimental_option("excludeSwitches", ["enable-automation"])
        chrome_options.add_experimental_option('useAutomationExtension', False)
        
        user_agents = [
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        ]
        chrome_options.add_argument(f"--user-agent={random.choice(user_agents)}")
        
        prefs = {
            "profile.default_content_setting_values.notifications": 2,
            "profile.default_content_settings.popups": 0,
            "profile.managed_default_content_settings.images": 2,
        }
        chrome_options.add_experimental_option("prefs", prefs)
        
        try:
            service = Service(ChromeDriverManager().install())
            self.driver = webdriver.Chrome(service=service, options=chrome_options)
            self.driver.set_page_load_timeout(120)
            self.driver.implicitly_wait(30)
            
            # Initial login page
            self.driver.get("https://scholar.google.com")
            time.sleep(3)
            
            return True
        except Exception as e:
            self.emit_progress('error', f'Failed to setup driver: {str(e)}')
            return False
    
    def wait_for_manual_login(self):
        """Wait for manual login"""
        self.emit_progress('waiting_login', 
                          'Browser terbuka. Silakan login ke Google Scholar secara manual, lalu klik Continue di browser.')
        
        # Wait for user confirmation (check for logged in state)
        max_wait = 300  # 5 minutes
        start_time = time.time()
        
        while time.time() - start_time < max_wait:
            try:
                # Check if user is on scholar.google.com and potentially logged in
                current_url = self.driver.current_url
                if 'scholar.google.com' in current_url:
                    # Try to detect login by checking for profile icon or other indicators
                    time.sleep(2)
                    # For now, we'll just proceed after a short wait
                    break
            except:
                pass
            time.sleep(2)
        
        self.emit_progress('ready', 'Login verification completed')
        return True
    
    def get_authors_from_db(self, scrape_from_beginning=False):
        """Get authors from database"""
        cursor = self.conn.cursor()
        
        try:
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
            return df
            
        except Exception as e:
            self.emit_progress('error', f'Error fetching authors: {str(e)}')
            return pd.DataFrame()
        finally:
            cursor.close()
    
    def update_scraping_status(self, author_name, status, error_message=None):
        """Update scraping status in database"""
        cursor = self.conn.cursor()
        
        try:
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
            cursor.close()
    
    def scrape_profile(self, profile_url, author_name):
        """Scrape single Google Scholar profile"""
        try:
            self.driver.get(profile_url)
            time.sleep(random.uniform(5, 8))
            
            scholar_id = ""
            if "user=" in profile_url:
                scholar_id = profile_url.split("user=")[1].split("&")[0]
            
            name = WebDriverWait(self.driver, 20).until(
                EC.presence_of_element_located((By.CSS_SELECTOR, '#gsc_prf_in'))
            ).text
            
            try:
                affiliation = self.driver.find_element(By.CSS_SELECTOR, '.gsc_prf_il').text
            except:
                affiliation = ""
            
            citation_stats = self.driver.find_elements(By.CSS_SELECTOR, '#gsc_rsb_st tbody tr')
            citation_data = {}
            
            for stat in citation_stats:
                metric_name = stat.find_element(By.CSS_SELECTOR, 'td:nth-of-type(1)').text
                all_citations = stat.find_element(By.CSS_SELECTOR, 'td:nth-of-type(2)').text
                recent_citations = stat.find_element(By.CSS_SELECTOR, 'td:nth-of-type(3)').text
                citation_data[f"{metric_name}_all"] = all_citations
                citation_data[f"{metric_name}_since2020"] = recent_citations
            
            # Get publications
            publications = []
            
            # Click show more until all loaded
            while True:
                try:
                    show_more_button = self.driver.find_element(By.ID, 'gsc_bpf_more')
                    if show_more_button.get_attribute('disabled'):
                        break
                    show_more_button.click()
                    time.sleep(random.uniform(2, 3))
                except:
                    break
            
            pub_items = self.driver.find_elements(By.CSS_SELECTOR, '#gsc_a_b .gsc_a_tr')
            
            for item in pub_items:
                try:
                    title_element = item.find_element(By.CSS_SELECTOR, '.gsc_a_t a')
                    title = title_element.text
                    pub_link = title_element.get_attribute('href')
                    
                    authors = item.find_element(By.CSS_SELECTOR, '.gs_gray:nth-of-type(1)').text
                    venue = item.find_element(By.CSS_SELECTOR, '.gs_gray:nth-of-type(2)').text
                    citations = item.find_element(By.CSS_SELECTOR, '.gsc_a_c a').text or "0"
                    year = item.find_element(By.CSS_SELECTOR, '.gsc_a_y span').text or "N/A"
                    
                    pub_data = {
                        'title': title,
                        'authors': authors,
                        'venue': venue,
                        'year': year,
                        'citations': citations,
                        'link': pub_link,
                        'Author': author_name
                    }
                    
                    publications.append(pub_data)
                    time.sleep(random.uniform(1, 2))
                except:
                    continue
            
            profile_data = {
                'name': name,
                'affiliation': affiliation,
                'profile_url': profile_url,
                'scholar_id': scholar_id,
                'citation_stats': citation_data,
                'publications': publications
            }
            
            return profile_data
            
        except Exception as e:
            raise Exception(f"Error scraping profile: {str(e)}")
    
    def save_to_database(self, profiles_data, publications_data):
        """Save scraped data to database"""
        cursor = self.conn.cursor()
        
        try:
            for profile in profiles_data:
                # Insert or update dosen
                cursor.execute("""
                    INSERT INTO tmp_dosen_dt (
                        v_nama_dosen, v_id_googleScholar, n_total_publikasi,
                        n_total_sitasi_gs, n_h_index_gs, n_i10_index_gs,
                        v_sumber, t_tanggal_unduh, v_link_url
                    ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                    ON CONFLICT (v_id_googleScholar) 
                    DO UPDATE SET
                        v_nama_dosen = EXCLUDED.v_nama_dosen,
                        n_total_publikasi = EXCLUDED.n_total_publikasi,
                        n_total_sitasi_gs = EXCLUDED.n_total_sitasi_gs,
                        n_h_index_gs = EXCLUDED.n_h_index_gs,
                        n_i10_index_gs = EXCLUDED.n_i10_index_gs,
                        t_tanggal_unduh = EXCLUDED.t_tanggal_unduh
                """, (
                    profile['name'],
                    profile['scholar_id'],
                    len(profile['publications']),
                    profile['citation_stats'].get('Citations_all', 0),
                    profile['citation_stats'].get('h-index_all', 0),
                    profile['citation_stats'].get('i10-index_all', 0),
                    'Google Scholar',
                    datetime.datetime.now(),
                    profile['profile_url']
                ))
            
            # Insert publications
            for pub in publications_data:
                cursor.execute("""
                    INSERT INTO stg_publikasi_tr (
                        v_judul, v_authors, v_tahun_publikasi,
                        n_total_sitasi, v_sumber, v_link_url,
                        t_tanggal_unduh
                    ) VALUES (%s, %s, %s, %s, %s, %s, %s)
                    ON CONFLICT (v_judul) DO NOTHING
                """, (
                    pub['title'],
                    pub['authors'],
                    pub['year'] if pub['year'] != 'N/A' else None,
                    int(pub['citations']) if pub['citations'].isdigit() else 0,
                    'Google Scholar',
                    pub['link'],
                    datetime.datetime.now()
                ))
            
            self.conn.commit()
            return True
            
        except Exception as e:
            self.conn.rollback()
            raise Exception(f"Error saving to database: {str(e)}")
        finally:
            cursor.close()
    
    def run(self, max_authors=10, scrape_from_beginning=False):
        """Main scraping execution"""
        try:
            # Connect to database
            if not self.connect_db():
                return {'success': False, 'error': 'Database connection failed'}
            
            # Setup driver
            if not self.setup_driver():
                return {'success': False, 'error': 'Driver setup failed'}
            
            # Wait for manual login
            self.emit_progress('waiting_login', 
                             'Silakan login ke Google Scholar di browser yang terbuka')
            
            # Give user time to login
            time.sleep(10)  # Wait 10 seconds for user to see the message
            
            # Get authors
            self.emit_progress('running', 'Mengambil daftar dosen dari database...')
            df = self.get_authors_from_db(scrape_from_beginning)
            
            if df.empty:
                return {
                    'success': True,
                    'message': 'Tidak ada dosen yang perlu di-scrape',
                    'summary': {'total_scraped': 0}
                }
            
            max_authors = min(max_authors, len(df))
            self.emit_progress('running', f'Memulai scraping {max_authors} dosen...', 0, max_authors)
            
            profiles_data = []
            publications_data = []
            success_count = 0
            error_count = 0
            
            for index, row in df.head(max_authors).iterrows():
                author_name = row['Name']
                profile_url = row['Profile URL']
                
                self.emit_progress('running', 
                                 f'Scraping: {author_name}',
                                 success_count + error_count,
                                 max_authors)
                
                self.update_scraping_status(author_name, 'processing')
                
                try:
                    profile_data = self.scrape_profile(profile_url, author_name)
                    
                    if profile_data and profile_data['publications']:
                        profiles_data.append(profile_data)
                        publications_data.extend(profile_data['publications'])
                        
                        self.update_scraping_status(author_name, 'completed')
                        success_count += 1
                        
                        self.emit_progress('running',
                                         f'Berhasil: {author_name} ({len(profile_data["publications"])} publikasi)',
                                         success_count + error_count,
                                         max_authors)
                    else:
                        self.update_scraping_status(author_name, 'error', 'Tidak ada publikasi')
                        error_count += 1
                
                except Exception as e:
                    error_msg = str(e)
                    self.update_scraping_status(author_name, 'error', error_msg)
                    error_count += 1
                    self.emit_progress('running',
                                     f'Error: {author_name} - {error_msg}',
                                     success_count + error_count,
                                     max_authors)
                
                # Delay between requests
                if success_count + error_count < max_authors:
                    time.sleep(random.uniform(5, 10))
            
            # Save to database
            if profiles_data:
                self.emit_progress('running', 'Menyimpan data ke database...')
                self.save_to_database(profiles_data, publications_data)
            
            return {
                'success': True,
                'message': f'Scraping selesai: {success_count} berhasil, {error_count} error',
                'summary': {
                    'total_scraped': success_count,
                    'total_errors': error_count,
                    'total_publications': len(publications_data)
                }
            }
            
        except Exception as e:
            return {
                'success': False,
                'error': str(e)
            }
        
        finally:
            if self.driver:
                try:
                    self.driver.quit()
                except:
                    pass
            
            if self.conn:
                try:
                    self.conn.close()
                except:
                    pass