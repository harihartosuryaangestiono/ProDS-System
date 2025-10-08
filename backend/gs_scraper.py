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
            
            # Save publications
            pubs_csv = 'all_dosen_data_publications.csv'
            pubs_df = pd.DataFrame(profile_data['publications'])
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
            
            # Import/update dosen
            cursor.execute(
                "SELECT v_id_dosen FROM tmp_dosen_dt WHERE v_id_googleScholar = %s",
                (profile_data['scholar_id'],)
            )
            result = cursor.fetchone()
            
            if result:
                dosen_id = result[0]
                cursor.execute("""
                    UPDATE tmp_dosen_dt SET 
                    v_nama_dosen = %s,
                    n_total_publikasi = %s,
                    n_total_sitasi_gs = %s,
                    v_sumber = 'Google Scholar',
                    t_tanggal_unduh = %s,
                    v_link_url = %s
                    WHERE v_id_dosen = %s
                """, (
                    profile_data['name'],
                    len(profile_data['publications']),
                    profile_data['citation_stats'].get('Citations_all', 0),
                    datetime.datetime.now(),
                    profile_data['profile_url'],
                    dosen_id
                ))
            else:
                cursor.execute("""
                    INSERT INTO tmp_dosen_dt (
                        v_nama_dosen, n_total_publikasi, n_total_sitasi_gs,
                        v_id_googleScholar, v_sumber, t_tanggal_unduh, v_link_url
                    ) VALUES (%s, %s, %s, %s, %s, %s, %s)
                    RETURNING v_id_dosen
                """, (
                    profile_data['name'],
                    len(profile_data['publications']),
                    profile_data['citation_stats'].get('Citations_all', 0),
                    profile_data['scholar_id'],
                    'Google Scholar',
                    datetime.datetime.now(),
                    profile_data['profile_url']
                ))
                dosen_id = cursor.fetchone()[0]
            
            # Import publications (simplified)
            for pub in profile_data['publications']:
                cursor.execute(
                    "SELECT v_id_publikasi FROM stg_publikasi_tr WHERE v_judul = %s",
                    (pub['title'],)
                )
                if not cursor.fetchone():
                    cursor.execute("""
                        INSERT INTO stg_publikasi_tr (
                            v_judul, v_tahun_publikasi, n_total_sitasi,
                            v_sumber, v_link_url, t_tanggal_unduh, v_authors
                        ) VALUES (%s, %s, %s, %s, %s, %s, %s)
                    """, (
                        pub['title'],
                        pub['year'] if pub['year'] != 'N/A' else None,
                        pub['citations'],
                        'Google Scholar',
                        pub['link'],
                        datetime.datetime.now(),
                        pub['authors']
                    ))
            
            self.conn.commit()
            print(f"✓ Imported to database: {dosen_id}")
            
        except Exception as e:
            self.conn.rollback()
            print(f"Error importing to database: {e}")
        finally:
            if cursor:
                cursor.close()
    
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