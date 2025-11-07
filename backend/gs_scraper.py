#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Google Scholar Scraper Module with Auto-Login and Account Rotation
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
    """Google Scholar Scraper with auto-login and database integration"""
    
    # Multi-account pool
    ACCOUNT_POOL = [
        {"email": "6182101017@student.unpar.ac.id", "password": "618017SH"},
        {"email": "6182101045@student.unpar.ac.id", "password": "6180145CD"},
        {"email": "61821010559@student.unpar.ac.id", "password": "618059SJ"},
        {"email": "6182101063@student.unpar.ac.id", "password": "618063XJ"},
    ]
    
    def __init__(self, db_config, job_id=None, progress_callback=None, email=None, password=None):
        self.db_config = db_config
        self.job_id = job_id
        self.progress_callback = progress_callback
        self.driver = None
        self.conn = None
        self.current_account_index = 0
        self.failed_accounts = set()
        self.restart_count = 0
        self.max_restarts = 3
        
        # Tambahkan email dan password
        self.email = email
        self.password = password
        
        # Jika email/password tidak diberikan, ambil dari ACCOUNT_POOL (index 0)
        if not self.email or not self.password:
            self.email = self.ACCOUNT_POOL[0]['email']
            self.password = self.ACCOUNT_POOL[0]['password']
            self.current_account_index = 0
        
    def get_next_account(self):
        """Get next available account that hasn't failed (random selection)"""
        # Get list of indices that haven't failed
        available_indices = [i for i in range(len(self.ACCOUNT_POOL)) if i not in self.failed_accounts]
        
        if not available_indices:
            # All accounts have failed
            return None, None
        
        # Random selection from available accounts
        selected_index = random.choice(available_indices)
        account = self.ACCOUNT_POOL[selected_index]
        
        return account, selected_index
    
    def mark_account_failed(self, account_index):
        """Mark an account as failed (hit CAPTCHA)"""
        self.failed_accounts.add(account_index)
        print(f"⚠️  Account {account_index + 1} ({self.ACCOUNT_POOL[account_index]['email']}) marked as failed (CAPTCHA detected)")
        print(f"   Failed accounts: {len(self.failed_accounts)}/{len(self.ACCOUNT_POOL)}")
    
    def reset_failed_accounts(self):
        """Reset failed accounts (for retry after all failed)"""
        self.failed_accounts.clear()
        print("♻️  All accounts reset for new attempt")
        
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
            
            import platform
            import subprocess
            if platform.system() == 'Darwin':
                driver_path = service.path
                try:
                    subprocess.run(['xattr', '-d', 'com.apple.quarantine', driver_path], 
                                 capture_output=True, check=False)
                    subprocess.run(['chmod', '+x', driver_path], 
                                 capture_output=True, check=False)
                    print(f"✓ Fixed ChromeDriver permissions for macOS")
                except Exception as perm_error:
                    print(f"Warning: Could not fix permissions: {perm_error}")
            
            driver = webdriver.Chrome(service=service, options=chrome_options)
            
        except Exception as e:
            print(f"Error with ChromeDriverManager: {e}")
            print("Trying alternative method...")
            
            try:
                driver = webdriver.Chrome(options=chrome_options)
            except Exception as e2:
                print(f"Error with system ChromeDriver: {e2}")
                
                try:
                    import shutil
                    chromedriver_path = shutil.which('chromedriver')
                    if chromedriver_path:
                        service = Service(chromedriver_path)
                        driver = webdriver.Chrome(service=service, options=chrome_options)
                    else:
                        raise Exception("ChromeDriver not found in system PATH")
                except Exception as e3:
                    print(f"All methods failed: {e3}")
                    raise Exception("Could not initialize ChromeDriver. Please install manually.")
        
        try:
            driver.execute_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")
        except:
            pass
        
        driver.set_page_load_timeout(120)
        driver.implicitly_wait(30)
        
        return driver
    
    def perform_auto_login(self):
        """Perform automatic login to Google Scholar through SSO with account rotation"""
        
        while self.restart_count < self.max_restarts:
            # Try login with available accounts
            while True:
                # Check if all accounts failed
                if len(self.failed_accounts) >= len(self.ACCOUNT_POOL):
                    print(f"\n⚠️  All {len(self.ACCOUNT_POOL)} accounts have failed!")
                    self.restart_count += 1
                    
                    if self.restart_count >= self.max_restarts:
                        raise Exception(f"Login failed after {self.max_restarts} complete restarts. All accounts hit CAPTCHA.")
                    
                    # Delay 2-5 minutes before restart
                    delay = random.uniform(120, 300)
                    print(f"\n🔄 Restart attempt {self.restart_count}/{self.max_restarts}")
                    print(f"⏳ Waiting {delay/60:.1f} minutes before restarting from Step 1...")
                    self.emit_progress({
                        'message': f'All accounts failed. Waiting {delay/60:.1f} minutes before restart {self.restart_count}/{self.max_restarts}...',
                        'status': 'restart_delay'
                    })
                    time.sleep(delay)
                    
                    # Reset all accounts and close driver
                    self.reset_failed_accounts()
                    if self.driver:
                        try:
                            self.driver.quit()
                        except:
                            pass
                    
                    # Setup new driver
                    self.driver = self.setup_driver()
                    
                    # Select random account for restart
                    account, idx = self.get_next_account()
                    if account:
                        self.email = account['email']
                        self.password = account['password']
                        self.current_account_index = idx
                        print(f"\n🔄 Restarting with random account: {self.email}")
                    break
                
                # Get next available account
                account, idx = self.get_next_account()
                if not account:
                    # This shouldn't happen, but just in case
                    break
                
                self.email = account['email']
                self.password = account['password']
                self.current_account_index = idx
                
                print(f"\n🔐 Attempting login with account {idx + 1}: {self.email}")
                
                try:
                    # Step 1: Open Google Scholar
                    self.emit_progress({
                        'message': f'Step 1: Opening Google Scholar (Account {idx + 1})...',
                        'status': 'login_in_progress'
                    })
                    print("Step 1: Opening https://scholar.google.com/")
                    self.driver.get("https://scholar.google.com/")
                    time.sleep(random.uniform(11, 29))
                    
                    # Step 2: Click Login button
                    self.emit_progress({
                        'message': 'Step 2: Clicking Login button...',
                        'status': 'login_in_progress'
                    })
                    print("Step 2: Clicking Login button")
                    try:
                        login_button = WebDriverWait(self.driver, 10).until(
                            EC.element_to_be_clickable((By.ID, "gs_hdr_act_s"))
                        )
                        login_button.click()
                        time.sleep(random.uniform(21, 25))
                    except Exception as e:
                        print(f"Could not find login button: {e}")
                        if self.check_if_logged_in():
                            print("✓ Already logged in!")
                            return True
                        raise
                    
                    # Step 3: Enter email on Google login page
                    self.emit_progress({
                        'message': 'Step 3: Entering email...',
                        'status': 'login_in_progress'
                    })
                    print("Step 3: Entering email on Google login page")
                    
                    email_input = WebDriverWait(self.driver, 15).until(
                        EC.presence_of_element_located((By.ID, "identifierId"))
                    )
                    email_input.clear()
                    email_input.send_keys(self.email)
                    time.sleep(random.uniform(21, 23))
                    
                    # Step 4: Click Next button (Google)
                    self.emit_progress({
                        'message': 'Step 4: Clicking Next...',
                        'status': 'login_in_progress'
                    })
                    print("Step 4: Clicking Next button")
                    
                    next_button = WebDriverWait(self.driver, 10).until(
                        EC.element_to_be_clickable((By.XPATH, "//span[contains(text(), 'Selanjutnya')]"))
                    )
                    next_button.click()
                    time.sleep(random.uniform(13, 28))
                    
                    # Step 5: Check for CAPTCHA
                    self.emit_progress({
                        'message': 'Step 5: Checking for CAPTCHA...',
                        'status': 'login_in_progress'
                    })
                    print("Step 5: Checking for CAPTCHA")
                    
                    try:
                        captcha = self.driver.find_element(By.ID, "captchaimg")
                        if captcha.is_displayed():
                            print(f"⚠️  CAPTCHA detected for account {idx + 1}!")
                            self.mark_account_failed(idx)
                            
                            # Continue to try next account
                            continue
                    except NoSuchElementException:
                        print("✓ No CAPTCHA detected, continuing...")
                    
                    # Step 6: Enter email on SSO page
                    self.emit_progress({
                        'message': 'Step 6: Entering email on SSO...',
                        'status': 'login_in_progress'
                    })
                    print("Step 6: Entering email on UNPAR SSO page")
                    
                    sso_email_input = WebDriverWait(self.driver, 15).until(
                        EC.presence_of_element_located((By.ID, "username"))
                    )
                    sso_email_input.clear()
                    sso_email_input.send_keys(self.email)
                    time.sleep(random.uniform(13, 25))
                    
                    # Step 7: Click Next on SSO
                    self.emit_progress({
                        'message': 'Step 7: Clicking Next on SSO...',
                        'status': 'login_in_progress'
                    })
                    print("Step 7: Clicking Next button on SSO")
                    
                    sso_next_button = WebDriverWait(self.driver, 10).until(
                        EC.element_to_be_clickable((By.ID, "next_login"))
                    )
                    sso_next_button.click()
                    time.sleep(random.uniform(14, 27))
                    
                    # Step 8: Enter password
                    self.emit_progress({
                        'message': 'Step 8: Entering password...',
                        'status': 'login_in_progress'
                    })
                    print("Step 8: Entering password")
                    
                    password_input = WebDriverWait(self.driver, 10).until(
                        EC.presence_of_element_located((By.ID, "password"))
                    )
                    password_input.clear()
                    password_input.send_keys(self.password)
                    time.sleep(random.uniform(10, 23))
                    
                    # Step 9: Click Login button
                    self.emit_progress({
                        'message': 'Step 9: Clicking Login...',
                        'status': 'login_in_progress'
                    })
                    print("Step 9: Clicking Login button")
                    
                    login_submit = WebDriverWait(self.driver, 10).until(
                        EC.element_to_be_clickable((By.CSS_SELECTOR, "button.login__submit2"))
                    )
                    login_submit.click()
                    time.sleep(random.uniform(13, 27))
                    
                    # Step 10: Click Continue on confirmation page
                    self.emit_progress({
                        'message': 'Step 10: Clicking Continue...',
                        'status': 'login_in_progress'
                    })
                    print("Step 10: Clicking Continue button")
                    
                    try:
                        continue_button = WebDriverWait(self.driver, 10).until(
                            EC.element_to_be_clickable((By.XPATH, "//span[contains(text(), 'Lanjutkan')]"))
                        )
                        continue_button.click()
                        time.sleep(random.uniform(12, 18))
                    except TimeoutException:
                        print("Continue button not found or already passed")
                    
                    # Verify login success
                    self.emit_progress({
                        'message': 'Verifying login...',
                        'status': 'login_in_progress'
                    })
                    print("Verifying login success...")
                    
                    if self.check_if_logged_in():
                        self.emit_progress({
                            'message': f'✓ Login successful with account {idx + 1}!',
                            'status': 'login_success'
                        })
                        print(f"✓ Login successful with {self.email}!")
                        return True
                    else:
                        raise Exception("Login verification failed")
                    
                except Exception as e:
                    print(f"Error during login with account {idx + 1}: {e}")
                    self.mark_account_failed(idx)
                    continue
        
        # If we've exhausted all restarts
        raise Exception(f"Login failed after {self.max_restarts} complete restarts. Unable to bypass CAPTCHA.")
    
    def check_if_logged_in(self):
        """Check if successfully logged in to Google Scholar"""
        try:
            time.sleep(3)
            
            try:
                self.driver.find_element(By.ID, "gs_hdr_act_s")
                return False
            except NoSuchElementException:
                try:
                    profile_element = self.driver.find_element(By.CSS_SELECTOR, '#gs_gb_rt a')
                    return True
                except:
                    pass
                
                current_url = self.driver.current_url
                if 'scholar.google.com' in current_url and 'accounts.google.com' not in current_url:
                    return True
            
            return False
            
        except Exception as e:
            print(f"Error checking login status: {e}")
            return False
    
    def setup_driver_with_auto_login(self):
        """Setup driver and perform automatic login"""
        self.driver = self.setup_driver()
        
        try:
            if self.perform_auto_login():
                self.emit_progress({
                    'message': 'Ready to start scraping...',
                    'status': 'ready'
                })
                return self.driver
            else:
                raise Exception("Auto-login failed")
            
        except Exception as e:
            print(f"Error during setup with auto-login: {e}")
            self.emit_progress({
                'message': f'Setup failed: {e}',
                'status': 'error'
            })
            raise
    
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
            if not self.driver or not self.driver.session_id:
                print(f"Driver session invalid for {pub_url}")
                return details
            
            try:
                self.driver.execute_script("window.open('');")
                new_tab_created = True
                time.sleep(random.uniform(0.5, 1))
                
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
            
            self.driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
            time.sleep(1.5)
            self.driver.execute_script("window.scrollTo(0, 0);")
            time.sleep(1.5)
            
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
                    if self.driver and hasattr(self.driver, 'session_id') and self.driver.session_id:
                        current_handles = self.driver.window_handles
                        
                        if len(current_handles) > 1:
                            current_window = self.driver.current_window_handle
                            if current_window != original_window and current_window in current_handles:
                                self.driver.close()
                                time.sleep(0.5)
                            
                            if original_window in self.driver.window_handles:
                                self.driver.switch_to.window(original_window)
                                time.sleep(0.5)
                except Exception as e:
                    print(f"Error in finally block (details): {e}")
                    try:
                        if self.driver and hasattr(self.driver, 'window_handles'):
                            handles = self.driver.window_handles
                            if handles:
                                self.driver.switch_to.window(handles[0])
                    except:
                        pass
    
    def classify_publication_type(self, journal, conference, publisher, title=""):
        """Classify publication type"""
        if journal and journal.strip() and journal != 'N/A':
            return 'artikel'
        
        if conference and conference.strip() and conference != 'N/A':
            return 'prosiding'
        
        return self.classify_by_regex(publisher, title)
    
    def classify_by_regex(self, publisher, title=""):
        """Classify using regex if journal and conference not available"""
        combined_text = f"{publisher} {title}".lower()
        
        if pd.isna(combined_text) or combined_text.strip() == "":
            return 'lainnya'
        
        book_publishers = ['nuansa aulia', 'citra aditya bakti', 'yrama widya', 
                          'pustaka belajar', 'pustaka pelajar', 'erlangga', 
                          'andpublisher', 'prenadamedia', 'gramedia', 'grasindo',
                          'media', 'prenhalindo', 'prenhallindo', 'wiley', 'springer']
        
        if any(pub in combined_text for pub in book_publishers):
            return 'buku'
        
        if 'edisi' in combined_text:
            return 'buku'
        
        if any(keyword in combined_text for keyword in ['jurnal', 'journal', 'jou.', 'j.', 'acta', 'review', 'letters']):
            return 'artikel'
        
        if any(keyword in combined_text for keyword in ['prosiding', 'proceedings', 'proc.', 'konferensi', 'conference', 
                                                       'conf.', 'simposium', 'symposium', 'workshop', 'pertemuan', 'meeting']):
            return 'prosiding'
        
        if any(keyword in combined_text for keyword in ['buku', 'book', 'bab buku', 'chapter', 'handbook', 'ensiklopedia', 
                                                       'encyclopedia', 'buku teks', 'textbook', 'penerbit', 'publisher', 'press', 
                                                       'books']):
            return 'buku'
        
        if any(keyword in combined_text for keyword in ['tesis', 'thesis', 'disertasi', 'dissertation', 'skripsi', 'program doktor',
                                                       'program pascasarjana', 'phd', 'master', 'doctoral', 'program studi', 'fakultas']):
            return 'penelitian'
        
        if any(keyword in combined_text for keyword in ['analisis', 'analysis', 'penelitian', 'research']):
            return 'penelitian'
        
        if any(keyword in combined_text for keyword in ['arxiv', 'preprint', 'laporan teknis', 'technical report', 
                                                       'naskah awal', 'working paper', 'teknis']):
            return 'penelitian'
        
        if 'paten' in combined_text or 'patent' in combined_text:
            return 'penelitian'
        
        if re.search(r'\bUU\s*No\.\s*\d+|Undang-undang\s*Nomor\s*\d+|Peraturan\s*(Pemerintah|Presiden)\s*No\.\s*\d+', 
                    combined_text):
            return 'buku'
        
        if re.search(r'vol\.|\bvol\b|\bedisi\b|\bno\.|\bhal\.|\bhalaman\b', combined_text) or \
           re.search(r'\bvol\.\s*\d+\s*(\(\s*\d+\s*\))?', combined_text) or \
           re.search(r'\d+\s*\(\d+\)', combined_text):
            return 'artikel'
        
        return 'lainnya'
    
    def scrape_profile(self, profile_url, author_name):
        """Scrape Google Scholar profile"""
        try:
            print(f"Accessing profile: {author_name}")
            
            self.driver.get(profile_url)
            time.sleep(random.uniform(5, 8))
            
            scholar_id = ""
            if "user=" in profile_url:
                scholar_id = profile_url.split("user=")[1].split("&")[0]
            
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
            
            citation_data = {
                'Citations_all': '0',
                'Citations_since2020': '0',
                'h-index_all': '0',
                'h-index_since2020': '0',
                'i10-index_all': '0',
                'i10-index_since2020': '0'
            }
            
            try:
                citation_stats = self.driver.find_elements(By.CSS_SELECTOR, '#gsc_rsb_st tbody tr')
                
                if citation_stats:
                    for stat in citation_stats:
                        try:
                            metric_name = stat.find_element(By.CSS_SELECTOR, 'td:nth-of-type(1)').text
                            all_citations = stat.find_element(By.CSS_SELECTOR, 'td:nth-of-type(2)').text
                            recent_citations = stat.find_element(By.CSS_SELECTOR, 'td:nth-of-type(3)').text
                            
                            citation_data[f"{metric_name}_all"] = all_citations if all_citations else '0'
                            citation_data[f"{metric_name}_since2020"] = recent_citations if recent_citations else '0'
                        except Exception as e:
                            print(f"Warning: Error extracting metric: {e}")
                            continue
            except Exception as e:
                print(f"Warning: Cannot get citation stats for {author_name}: {e}")
            
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
            
            publications = []
        
            while True:
                try:
                    show_more = self.driver.find_element(By.ID, 'gsc_bpf_more')
                    if show_more.get_attribute('disabled'):
                        break
                    show_more.click()
                    time.sleep(random.uniform(2, 3))
                except:
                    break
            
            pub_items = self.driver.find_elements(By.CSS_SELECTOR, '#gsc_a_b .gsc_a_tr')
            
            for item in pub_items:
                try:
                    title_element = item.find_element(By.CSS_SELECTOR, '.gsc_a_t a')
                    title = title_element.text
                    pub_link = title_element.get_attribute('href')
                    
                    pub_details = self.get_publication_details(pub_link)
                    
                    authors = item.find_element(By.CSS_SELECTOR, '.gs_gray:nth-of-type(1)').text
                    venue_fallback = item.find_element(By.CSS_SELECTOR, '.gs_gray:nth-of-type(2)').text
                    citations = item.find_element(By.CSS_SELECTOR, '.gsc_a_c a').text or "0"
                    year = item.find_element(By.CSS_SELECTOR, '.gsc_a_y span').text or "N/A"
                    
                    pub_citations_per_year = self.get_publication_citations_per_year(pub_link)
                    
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
                        'citations_per_year': pub_citations_per_year
                    }
                    
                    publications.append(pub_data)
                    time.sleep(random.uniform(1, 2))
                    
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
            if not self.driver or not self.driver.session_id:
                print(f"Driver session invalid for {pub_url}")
                return {}
            
            try:
                self.driver.execute_script("window.open('');")
                new_tab_created = True
                time.sleep(random.uniform(0.5, 1))
                
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
            
            self.driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
            time.sleep(1.5)
            self.driver.execute_script("window.scrollTo(0, 0);")
            time.sleep(1.5)
            
            page_source = self.driver.page_source
            soup = BeautifulSoup(page_source, 'html.parser')
            
            citations_per_year = {}
            
            year_elements = soup.select('.gsc_oci_g_t')
            citation_elements = soup.select('.gsc_oci_g_a')
            
            for year_element in year_elements:
                year = year_element.text.strip()
                if year.isdigit() and 2000 <= int(year) <= 2030:
                    citations_per_year[year] = 0
            
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
                    if self.driver and hasattr(self.driver, 'session_id') and self.driver.session_id:
                        current_handles = self.driver.window_handles
                        
                        if len(current_handles) > 1:
                            current_window = self.driver.current_window_handle
                            if current_window != original_window and current_window in current_handles:
                                self.driver.close()
                                time.sleep(0.5)
                            
                            if original_window in self.driver.window_handles:
                                self.driver.switch_to.window(original_window)
                                time.sleep(0.5)
                except Exception as e:
                    print(f"Error in finally block (citations): {e}")
                    try:
                        if self.driver and hasattr(self.driver, 'window_handles'):
                            handles = self.driver.window_handles
                            if handles:
                                self.driver.switch_to.window(handles[0])
                    except:
                        pass
    
    def save_to_csv(self, profile_data):
        """Save profile and publications to CSV"""
        try:
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
            
            pubs_csv = 'all_dosen_data_publications.csv'
            
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
            
            scholar_id = profile_data.get('scholar_id', '')
            
            cursor.execute(sql.SQL("""
                INSERT INTO tmp_dosen_dt (
                    v_nama_dosen, n_total_publikasi, n_total_sitasi_gs, n_total_sitasi_gs2020,
                    v_id_googlescholar, n_h_index_gs, n_h_index_gs2020,
                    n_i10_index_gs, n_i10_index_gs2020, v_sumber, t_tanggal_unduh,
                    v_link_url
                ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                RETURNING v_id_dosen
            """), (
                profile_data.get('name', ''),
                len(profile_data.get('publications', [])),
                int(profile_data['citation_stats'].get('Citations_all', 0)) if 'Citations_all' in profile_data['citation_stats'] else 0,
                int(profile_data['citation_stats'].get('Citations_since2020', 0)) if 'Citations_since2020' in profile_data['citation_stats'] else 0,
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
            
            print(f"✓ Inserted new dosen record with ID: {dosen_id}")
            
            imported_count = 0
            for pub in profile_data.get('publications', []):
                try:
                    pub_type_raw = pub.get('publication_type', 'lainnya')
                    pub_type = normalize_publication_type(pub_type_raw)
                    
                    try:
                        year = int(pub.get('year', 'N/A')) if pub.get('year') != 'N/A' else None
                    except:
                        year = None
                    
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
                    
                    if 'citations_per_year' in pub and pub['citations_per_year']:
                        self._insert_sitasi_tahunan_batch(cursor, pub_id, pub['citations_per_year'])
                    
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
            journal_name = pub.get('journal', '')
            
            if not journal_name or journal_name == 'N/A':
                print(f"    Warning: Artikel tanpa nama jurnal, skip insert artikel data")
                return
            
            check_journal_query = sql.SQL("""
                SELECT v_id_jurnal FROM stg_jurnal_mt WHERE v_nama_jurnal = %s
            """)
            cursor.execute(check_journal_query, (journal_name,))
            result = cursor.fetchone()
            
            if result:
                journal_id = result[0]
            else:
                insert_journal_query = sql.SQL("""
                    INSERT INTO stg_jurnal_mt (v_nama_jurnal)
                    VALUES (%s)
                    RETURNING v_id_jurnal
                """)
                cursor.execute(insert_journal_query, (journal_name,))
                journal_id = cursor.fetchone()[0]
            
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
            
            for year, citations in citations_per_year.items():
                try:
                    if not str(year).isdigit():
                        continue
                    
                    year_int = int(year)
                    citations_int = int(citations) if citations else 0
                    
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
            if not self.connect_to_db():
                raise Exception("Failed to connect to database")
            
            df = self.get_authors_from_db(scrape_from_beginning)
            if df.empty:
                raise Exception("No authors to scrape")
            
            max_authors = min(max_authors, len(df))
            
            self.emit_progress({
                'message': 'Setting up browser...',
                'current': 0,
                'total': max_authors
            })
            
            self.setup_driver_with_auto_login()
            
            if not self.driver:
                raise Exception("Failed to setup driver")
            
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
    """Normalize publication type to database format"""
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


# Example usage
if __name__ == "__main__":
    DB_CONFIG = {
        'dbname': 'SKM_PUBLIKASI',
        'user': 'rayhanadjisantoso',
        'password': 'rayhan123',
        'host': 'localhost',
        'port': '5432'
    }
    
    scraper = GoogleScholarScraper(
        db_config=DB_CONFIG,
        email="6182101017@student.unpar.ac.id",
        password="618017SH"
    )
    
    result = scraper.run(max_authors=5, scrape_from_beginning=False)
    print(result)