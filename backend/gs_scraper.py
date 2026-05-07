#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Google Scholar Scraper - FIXED v3
Root cause: Chrome headless menampilkan error page saat load sso.unpar.ac.id
(terlihat dari page source berisi CSS Chrome error page, bukan HTML SSO).
Penyebab: certificate chain SSO UNPAR tidak dipercaya Chrome headless Linux.

Fix:
1. Tambah --test-type flag (paling ampuh bypass cert error di headless)
2. Tambah acceptInsecureCerts via desired_capabilities
3. Deteksi Chrome error page dan log error code-nya
4. Coba navigate ulang jika error page terdeteksi
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
import logging
import sys
import signal

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
    handlers=[
        logging.FileHandler('/var/log/prods-gs-scraper.log'),
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger(__name__)


class GoogleScholarScraper:

    ACCOUNT_POOL = [
        {"email": "6182101017@student.unpar.ac.id", "password": "618017SH"},
        {"email": "6182101045@student.unpar.ac.id", "password": "hariharto123"},
        {"email": "6182101059@student.unpar.ac.id", "password": "618059SJ"},
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
        self.email = email
        self.password = password
        if not self.email or not self.password:
            self.email = self.ACCOUNT_POOL[0]['email']
            self.password = self.ACCOUNT_POOL[0]['password']
            self.current_account_index = 0

    # =========================================================================
    # CANCEL CHECK
    # =========================================================================

    def is_cancelled(self):
        if not self.job_id:
            return False
        try:
            from routes.scraping_routes import active_jobs
            job_info = active_jobs.get(self.job_id, {})
            return job_info.get('cancel_requested', False)
        except Exception:
            return False

    def raise_if_cancelled(self):
        if self.is_cancelled():
            raise InterruptedError(f"Job {self.job_id} dibatalkan oleh user")

    # =========================================================================
    # ACCOUNT POOL
    # =========================================================================

    def get_next_account(self):
        available_indices = [i for i in range(len(self.ACCOUNT_POOL)) if i not in self.failed_accounts]
        if not available_indices:
            return None, None
        selected_index = random.choice(available_indices)
        return self.ACCOUNT_POOL[selected_index], selected_index

    def mark_account_failed(self, account_index):
        self.failed_accounts.add(account_index)
        logger.warning(f"Account {account_index + 1} ({self.ACCOUNT_POOL[account_index]['email']}) marked as failed")

    def reset_failed_accounts(self):
        self.failed_accounts.clear()
        logger.info("All accounts reset for new attempt")

    # =========================================================================
    # PROGRESS
    # =========================================================================

    def emit_progress(self, data):
        if self.progress_callback:
            try:
                self.progress_callback(data)
            except Exception as e:
                logger.error(f"Error emitting progress: {e}")

    # =========================================================================
    # DATABASE
    # =========================================================================

    def connect_to_db(self):
        try:
            self.conn = psycopg2.connect(**self.db_config)
            logger.info("Connected to database successfully!")
            return self.conn
        except Exception as e:
            logger.error(f"Error connecting to database: {e}")
            return None

    # =========================================================================
    # CHROME ERROR PAGE DETECTION
    # =========================================================================

    def _is_chrome_error_page(self):
        """
        Deteksi apakah halaman saat ini adalah Chrome error page
        (bukan halaman web yang sebenarnya).
        Chrome error page mengandung CSS khas dan tidak punya konten web.
        """
        try:
            # Cek via JavaScript — Chrome error page punya property khusus
            is_error = self.driver.execute_script(
                "return document.querySelector('body') !== null && "
                "document.querySelector('#main-message') !== null;"
            )
            if is_error:
                return True

            # Cek page source — Chrome error page mengandung string khas ini
            src = self.driver.page_source
            chrome_error_indicators = [
                '--google-blue-600',   # CSS variable khas Chrome error page
                'ERR_',                # Error code Chrome
                '--error-code-color',  # CSS variable error page
                'id="error-information-popup-container"',
            ]
            if any(indicator in src for indicator in chrome_error_indicators):
                # Coba ambil error code dari JavaScript
                try:
                    error_code = self.driver.execute_script(
                        "return window.errorCode || "
                        "document.getElementById('error-code')?.textContent || 'UNKNOWN';"
                    )
                    logger.error(f"Chrome error page detected! Error code: {error_code}")
                except Exception:
                    logger.error("Chrome error page detected! (error code unknown)")
                return True

            return False
        except Exception:
            return False

    def _get_chrome_error_code(self):
        """Ambil error code dari Chrome error page"""
        try:
            src = self.driver.page_source
            match = re.search(r'ERR_[A-Z_]+', src)
            if match:
                return match.group(0)
            return "UNKNOWN_ERROR"
        except Exception:
            return "UNKNOWN_ERROR"

    # =========================================================================
    # DRIVER SETUP  ← PERBAIKAN V3
    # =========================================================================

    def setup_driver(self):
        """
        PERBAIKAN V3:
        Menggunakan selenium 4 capabilities untuk acceptInsecureCerts = True,
        yang merupakan cara RESMI W3C WebDriver untuk bypass SSL.
        Ini berbeda dengan flag Chrome (--ignore-certificate-errors) yang
        tidak selalu efektif untuk semua jenis cert error.
        """
        chrome_options = Options()

        # ── W3C capability: accept semua SSL cert ─────────────────────────
        # Ini cara RESMI yang direkomendasikan W3C WebDriver spec
        chrome_options.set_capability("acceptInsecureCerts", True)

        # ── Mode headless ──────────────────────────────────────────────────
        chrome_options.add_argument("--headless=new")
        chrome_options.add_argument("--no-sandbox")
        chrome_options.add_argument("--disable-dev-shm-usage")
        chrome_options.add_argument("--window-size=1920,1080")
        chrome_options.add_argument("--disable-gpu")

        # ── SSL/Certificate bypass (multi-layer) ──────────────────────────
        chrome_options.add_argument("--ignore-certificate-errors")
        chrome_options.add_argument("--ignore-ssl-errors")
        chrome_options.add_argument("--ignore-certificate-errors-spki-list")
        chrome_options.add_argument("--allow-insecure-localhost")
        chrome_options.add_argument("--allow-running-insecure-content")
        # --test-type: flag internal Chrome yang menonaktifkan banyak
        # security check termasuk certificate validation
        chrome_options.add_argument("--test-type")

        # ── Networking ─────────────────────────────────────────────────────
        chrome_options.add_argument("--disable-web-security")
        chrome_options.add_argument("--disable-features=IsolateOrigins,site-per-process,BlockInsecurePrivateNetworkRequests")
        # Eksplisit izinkan semua origin
        chrome_options.add_argument("--disable-site-isolation-trials")

        # ── Flag ringan yang aman ──────────────────────────────────────────
        chrome_options.add_argument("--disable-extensions")
        chrome_options.add_argument("--disable-infobars")
        chrome_options.add_argument("--disable-popup-blocking")
        chrome_options.add_argument("--disable-translate")
        chrome_options.add_argument("--no-first-run")
        chrome_options.add_argument("--mute-audio")
        chrome_options.add_argument("--hide-scrollbars")
        chrome_options.add_argument("--remote-debugging-port=0")

        # ── Anti-bot detection ─────────────────────────────────────────────
        chrome_options.add_argument("--disable-blink-features=AutomationControlled")
        chrome_options.add_experimental_option("excludeSwitches", ["enable-automation"])
        chrome_options.add_experimental_option('useAutomationExtension', False)

        user_agents = [
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        ]
        chrome_options.add_argument(f"--user-agent={random.choice(user_agents)}")

        prefs = {"profile.managed_default_content_settings.images": 2}
        chrome_options.add_experimental_option("prefs", prefs)

        import uuid
        user_data_dir = f"/tmp/chrome_profile_{uuid.uuid4().hex}"
        os.makedirs(user_data_dir, exist_ok=True)
        self._chrome_user_data_dir = user_data_dir
        chrome_options.add_argument(f"--user-data-dir={user_data_dir}")

        try:
            driver_path = ChromeDriverManager().install()
            if os.path.basename(driver_path) != 'chromedriver':
                candidate_path = os.path.join(os.path.dirname(driver_path), 'chromedriver')
                if os.path.exists(candidate_path):
                    driver_path = candidate_path
            import platform, subprocess
            try:
                os.chmod(driver_path, 0o755)
            except Exception as e:
                logger.warning(f"Could not set chromedriver permissions: {e}")
            if platform.system() == 'Darwin':
                try:
                    subprocess.run(['xattr', '-d', 'com.apple.quarantine', driver_path], capture_output=True, check=False)
                except Exception:
                    pass
            driver = webdriver.Chrome(service=Service(driver_path), options=chrome_options)
        except Exception as e:
            logger.warning(f"ChromeDriverManager failed: {e}, trying fallback...")
            try:
                driver = webdriver.Chrome(options=chrome_options)
            except Exception as e2:
                logger.warning(f"System ChromeDriver failed: {e2}, trying PATH...")
                import shutil
                chromedriver_path = shutil.which('chromedriver') or '/usr/local/bin/chromedriver'
                if not chromedriver_path:
                    raise Exception("ChromeDriver not found in system PATH")
                driver = webdriver.Chrome(service=Service(chromedriver_path), options=chrome_options)

        try:
            driver.execute_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")
        except Exception:
            pass

        driver.set_page_load_timeout(120)
        driver.implicitly_wait(30)

        return driver

    # =========================================================================
    # HELPER: Tunggu SSO page dengan deteksi error page
    # =========================================================================

    def _wait_for_sso_page(self, timeout=90):
        """
        Tunggu SSO UNPAR dengan deteksi Chrome error page.
        Jika error page terdeteksi, log error code dan raise exception.
        """
        start = time.time()
        logger.info(f"Step 6: Waiting for SSO — URL: {self.driver.current_url}")

        # Cek apakah ini Chrome error page
        if self._is_chrome_error_page():
            error_code = self._get_chrome_error_code()
            raise Exception(
                f"Chrome error page saat load SSO UNPAR! "
                f"Error: {error_code}. "
                f"URL: {self.driver.current_url}"
            )

        # Tunggu document.readyState = complete
        try:
            WebDriverWait(self.driver, 30).until(
                lambda d: d.execute_script("return document.readyState") == "complete"
            )
            logger.info(f"Step 6: document.readyState = complete setelah {time.time()-start:.1f}s")
        except Exception:
            logger.warning("Step 6: readyState timeout, melanjutkan...")

        # Cek ulang setelah readyState complete
        if self._is_chrome_error_page():
            error_code = self._get_chrome_error_code()
            raise Exception(
                f"Chrome error page setelah readyState complete! "
                f"Error: {error_code}"
            )

        # Tunggu elemen #username
        elapsed = time.time() - start
        remaining = max(timeout - elapsed, 10)
        try:
            elem = WebDriverWait(self.driver, remaining).until(
                EC.presence_of_element_located((By.ID, "username"))
            )
            logger.info(f"Step 6: Found #username setelah {time.time()-start:.1f}s")
            return elem
        except TimeoutException:
            # Log page source untuk diagnosis final
            try:
                src = self.driver.page_source
                logger.error(f"Step 6 TIMEOUT: page_source length = {len(src)}")
                logger.error(f"Step 6 TIMEOUT: page_source[:3000] =\n{src[:3000]}")
            except Exception as e:
                logger.error(f"Step 6: Cannot read page_source: {e}")
            raise TimeoutException(
                f"Elemen #username tidak ditemukan setelah {timeout}s. "
                f"URL: {self.driver.current_url}"
            )

    # =========================================================================
    # LOGIN  ← PERBAIKAN V3
    # =========================================================================

    def perform_auto_login(self):
        while self.restart_count < self.max_restarts:
            while True:
                self.raise_if_cancelled()

                if len(self.failed_accounts) >= len(self.ACCOUNT_POOL):
                    logger.warning(f"All {len(self.ACCOUNT_POOL)} accounts have failed!")
                    self.restart_count += 1
                    if self.restart_count >= self.max_restarts:
                        raise Exception(f"Login failed after {self.max_restarts} complete restarts.")
                    delay = random.uniform(120, 300)
                    self.emit_progress({'message': f'All accounts failed. Waiting {delay/60:.1f} minutes...', 'status': 'restart_delay'})
                    time.sleep(delay)
                    self.reset_failed_accounts()
                    if self.driver:
                        try:
                            self.driver.quit()
                        except Exception:
                            pass
                        if hasattr(self, '_chrome_user_data_dir') and os.path.exists(self._chrome_user_data_dir):
                            import shutil
                            shutil.rmtree(self._chrome_user_data_dir, ignore_errors=True)
                    self.driver = self.setup_driver()
                    account, idx = self.get_next_account()
                    if account:
                        self.email = account['email']
                        self.password = account['password']
                        self.current_account_index = idx
                    break

                account, idx = self.get_next_account()
                if not account:
                    break

                self.email = account['email']
                self.password = account['password']
                self.current_account_index = idx
                logger.info(f"Attempting login with account {idx + 1}: {self.email}")

                try:
                    # ── Step 1 ─────────────────────────────────────────────
                    self.emit_progress({'message': f'Step 1: Opening Google Scholar (Account {idx + 1})...', 'status': 'login_in_progress'})
                    logger.info("Step 1: Opening https://scholar.google.com/")
                    self.driver.get("https://scholar.google.com/")
                    time.sleep(random.uniform(11, 29))
                    self.raise_if_cancelled()

                    # ── Step 2 ─────────────────────────────────────────────
                    self.emit_progress({'message': 'Step 2: Clicking Login button...', 'status': 'login_in_progress'})
                    logger.info("Step 2: Clicking Login button")
                    try:
                        login_button = WebDriverWait(self.driver, 10).until(
                            EC.element_to_be_clickable((By.ID, "gs_hdr_act_s"))
                        )
                        login_button.click()
                        time.sleep(random.uniform(21, 25))
                    except Exception as e:
                        logger.info(f"Could not find login button: {e}")
                        if self.check_if_logged_in():
                            logger.info("Already logged in!")
                            return True
                        raise
                    self.raise_if_cancelled()

                    # ── Step 3 ─────────────────────────────────────────────
                    self.emit_progress({'message': 'Step 3: Entering email...', 'status': 'login_in_progress'})
                    logger.info("Step 3: Entering email on Google login page")
                    email_input = WebDriverWait(self.driver, 15).until(
                        EC.presence_of_element_located((By.ID, "identifierId"))
                    )
                    email_input.clear()
                    email_input.send_keys(self.email)
                    time.sleep(random.uniform(21, 23))
                    self.raise_if_cancelled()

                    # ── Step 4 ─────────────────────────────────────────────
                    self.emit_progress({'message': 'Step 4: Clicking Next...', 'status': 'login_in_progress'})
                    logger.info(f"Step 4: URL = {self.driver.current_url}")
                    time.sleep(random.uniform(3, 5))
                    try:
                        next_button = WebDriverWait(self.driver, 15).until(
                            EC.element_to_be_clickable((By.XPATH, "//*[@id='identifierNext']/div/button"))
                        )
                    except TimeoutException:
                        try:
                            next_button = WebDriverWait(self.driver, 10).until(
                                EC.element_to_be_clickable((By.XPATH, "//*[@jsname='LgbsSe']"))
                            )
                        except TimeoutException:
                            next_button = WebDriverWait(self.driver, 10).until(
                                EC.element_to_be_clickable((By.XPATH, "//span[contains(text(), 'Berikutnya') or contains(text(), 'Next')]"))
                            )
                    next_button.click()
                    time.sleep(random.uniform(13, 28))
                    self.raise_if_cancelled()

                    # ── Step 5: Cek CAPTCHA (implicitly_wait pendek) ───────
                    self.emit_progress({'message': 'Step 5: Checking for CAPTCHA...', 'status': 'login_in_progress'})
                    logger.info(f"Step 5: URL = {self.driver.current_url}")
                    logger.info(f"Step 5: Title = {self.driver.title}")

                    self.driver.implicitly_wait(2)
                    try:
                        captcha = self.driver.find_element(By.ID, "captchaimg")
                        if captcha.is_displayed():
                            logger.warning(f"CAPTCHA detected for account {idx + 1}!")
                            self.driver.implicitly_wait(30)
                            self.mark_account_failed(idx)
                            continue
                    except NoSuchElementException:
                        logger.info("No CAPTCHA detected, continuing...")
                    finally:
                        self.driver.implicitly_wait(30)
                    self.raise_if_cancelled()

                    # ── Step 6: Masukkan email di SSO ─────────────────────
                    self.emit_progress({'message': 'Step 6: Entering email on SSO...', 'status': 'login_in_progress'})
                    logger.info(f"Step 6: URL = {self.driver.current_url}")

                    # PERBAIKAN V3: Deteksi Chrome error page sebelum tunggu SSO
                    if self._is_chrome_error_page():
                        error_code = self._get_chrome_error_code()
                        logger.error(f"Step 6: Chrome error page terdeteksi! Error: {error_code}")
                        raise Exception(f"Chrome error page di SSO: {error_code}")

                    sso_email_input = self._wait_for_sso_page(timeout=90)
                    sso_email_input.clear()
                    sso_email_input.send_keys(self.email)
                    time.sleep(random.uniform(13, 25))
                    self.raise_if_cancelled()

                    # ── Step 7 ─────────────────────────────────────────────
                    self.emit_progress({'message': 'Step 7: Clicking Next on SSO...', 'status': 'login_in_progress'})
                    logger.info("Step 7: Clicking Next button on SSO")
                    sso_next_button = WebDriverWait(self.driver, 30).until(
                        EC.element_to_be_clickable((By.ID, "next_login"))
                    )
                    sso_next_button.click()
                    time.sleep(random.uniform(14, 27))
                    self.raise_if_cancelled()

                    # ── Step 8 ─────────────────────────────────────────────
                    self.emit_progress({'message': 'Step 8: Entering password...', 'status': 'login_in_progress'})
                    logger.info(f"Step 8: URL = {self.driver.current_url}")
                    try:
                        password_input = WebDriverWait(self.driver, 60).until(
                            EC.presence_of_element_located((By.ID, "password"))
                        )
                    except TimeoutException:
                        logger.error(f"Step 8 TIMEOUT: URL = {self.driver.current_url}")
                        raise
                    password_input.clear()
                    password_input.send_keys(self.password)
                    time.sleep(random.uniform(10, 23))
                    self.raise_if_cancelled()

                    # ── Step 9 ─────────────────────────────────────────────
                    self.emit_progress({'message': 'Step 9: Clicking Login...', 'status': 'login_in_progress'})
                    logger.info("Step 9: Clicking Login button")
                    login_submit = WebDriverWait(self.driver, 30).until(
                        EC.element_to_be_clickable((By.CSS_SELECTOR, "button.login__submit2"))
                    )
                    login_submit.click()
                    time.sleep(random.uniform(13, 27))
                    self.raise_if_cancelled()

                    # ── Step 10 ────────────────────────────────────────────
                    self.emit_progress({'message': 'Step 10: Clicking Continue...', 'status': 'login_in_progress'})
                    logger.info("Step 10: Clicking Continue button")
                    try:
                        continue_button = WebDriverWait(self.driver, 10).until(
                            EC.element_to_be_clickable((By.XPATH, "//span[contains(text(), 'Lanjutkan')]"))
                        )
                        continue_button.click()
                        time.sleep(random.uniform(12, 18))
                    except TimeoutException:
                        logger.info("Continue button not found or already passed")
                    self.raise_if_cancelled()

                    # ── Verifikasi ─────────────────────────────────────────
                    self.emit_progress({'message': 'Verifying login...', 'status': 'login_in_progress'})
                    if self.check_if_logged_in():
                        self.emit_progress({'message': f'Login successful with account {idx + 1}!', 'status': 'login_success'})
                        logger.info(f"Login successful with {self.email}!")
                        return True
                    else:
                        raise Exception("Login verification failed")

                except InterruptedError:
                    raise
                except Exception as e:
                    logger.error(f"Error during login with account {idx + 1}: {e}")
                    self.mark_account_failed(idx)
                    continue

        raise Exception(f"Login failed after {self.max_restarts} complete restarts.")

    def check_if_logged_in(self):
        try:
            time.sleep(3)
            try:
                self.driver.find_element(By.ID, "gs_hdr_act_s")
                return False
            except NoSuchElementException:
                try:
                    self.driver.find_element(By.CSS_SELECTOR, '#gs_gb_rt a')
                    return True
                except Exception:
                    pass
                current_url = self.driver.current_url
                if 'scholar.google.com' in current_url and 'accounts.google.com' not in current_url:
                    return True
            return False
        except Exception as e:
            logger.error(f"Error checking login status: {e}")
            return False

    def setup_driver_with_auto_login(self):
        self.driver = self.setup_driver()
        try:
            if self.perform_auto_login():
                self.emit_progress({'message': 'Ready to start scraping...', 'status': 'ready'})
                return self.driver
            else:
                raise Exception("Auto-login failed")
        except InterruptedError:
            raise
        except Exception as e:
            logger.error(f"Error during setup with auto-login: {e}")
            self.emit_progress({'message': f'Setup failed: {e}', 'status': 'error'})
            raise

    # =========================================================================
    # DATABASE HELPERS
    # =========================================================================

    def get_authors_from_db(self, scrape_from_beginning=False):
        cursor = None
        try:
            cursor = self.conn.cursor()
            if scrape_from_beginning:
                query = "SELECT v_nama, v_link, COALESCE(v_status, 'pending') as status FROM temp_dosenGS_scraping WHERE v_link IS NOT NULL ORDER BY v_nama"
            else:
                query = """SELECT v_nama, v_link, COALESCE(v_status, 'pending') as status
                    FROM temp_dosenGS_scraping WHERE v_link IS NOT NULL
                    AND (v_status IS NULL OR v_status IN ('pending', 'error', 'processing'))
                    ORDER BY CASE WHEN v_status = 'processing' THEN 1 WHEN v_status = 'error' THEN 2 ELSE 3 END, v_nama"""
            cursor.execute(query)
            results = cursor.fetchall()
            df = pd.DataFrame(results, columns=['Name', 'Profile URL', 'Status'])
            logger.info(f"Retrieved {len(df)} authors from database")
            return df
        except Exception as e:
            logger.error(f"Error getting authors: {e}")
            return pd.DataFrame()
        finally:
            if cursor:
                cursor.close()

    def update_scraping_status(self, author_name, status, error_message=None):
        cursor = None
        try:
            cursor = self.conn.cursor()
            if status == 'error' and error_message:
                cursor.execute("UPDATE temp_dosenGS_scraping SET v_status=%s, v_error_message=%s, t_last_updated=NOW() WHERE v_nama=%s", (status, error_message, author_name))
            else:
                cursor.execute("UPDATE temp_dosenGS_scraping SET v_status=%s, t_last_updated=NOW() WHERE v_nama=%s", (status, author_name))
            self.conn.commit()
        except Exception as e:
            self.conn.rollback()
            logger.error(f"Error updating status: {e}")
        finally:
            if cursor:
                cursor.close()

    # =========================================================================
    # PUBLICATION DETAILS
    # =========================================================================

    def get_publication_details(self, pub_url):
        original_window = self.driver.current_window_handle
        new_tab_created = False
        details = {'authors': '', 'journal': 'N/A', 'conference': 'N/A', 'publisher': '', 'volume': '', 'issue': '', 'pages': ''}
        try:
            if not self.driver or not self.driver.session_id:
                return details
            if self.is_cancelled():
                return details
            self.driver.execute_script("window.open('');")
            new_tab_created = True
            time.sleep(random.uniform(0.5, 1))
            if len(self.driver.window_handles) < 2:
                return details
            self.driver.switch_to.window(self.driver.window_handles[1])
            self.driver.get(pub_url)
            time.sleep(random.uniform(4, 6))
            try:
                WebDriverWait(self.driver, 25).until(EC.presence_of_element_located((By.CSS_SELECTOR, '.gsc_oci_main, .gs_scl')))
            except TimeoutException:
                pass
            self.driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
            time.sleep(1.5)
            self.driver.execute_script("window.scrollTo(0, 0);")
            time.sleep(1.5)
            soup = BeautifulSoup(self.driver.page_source, 'html.parser')
            for field, value in zip(soup.find_all('div', class_='gsc_oci_field'), soup.find_all('div', class_='gsc_oci_value')):
                ft = field.get_text().strip().lower()
                vt = value.get_text().strip()
                if ft in ('authors', 'author'):
                    details['authors'] = vt
                elif ft == 'journal':
                    details['journal'] = vt; details['conference'] = 'N/A'
                elif ft == 'conference':
                    details['conference'] = vt; details['journal'] = 'N/A'
                elif ft == 'publisher':
                    details['publisher'] = vt
                elif ft == 'source':
                    vl = vt.lower()
                    if any(k in vl for k in ['journal', 'jurnal', 'acta', 'review', 'letters']):
                        details['journal'] = vt; details['conference'] = 'N/A'
                    elif any(k in vl for k in ['conference', 'proceedings', 'symposium', 'workshop', 'konferensi', 'prosiding']):
                        details['conference'] = vt; details['journal'] = 'N/A'
                    else:
                        if not details['publisher']:
                            details['publisher'] = vt
                elif ft == 'volume':
                    details['volume'] = vt
                elif ft == 'issue':
                    details['issue'] = vt
                elif ft == 'pages':
                    details['pages'] = vt
            return details
        except Exception as e:
            logger.error(f"Error retrieving publication details {pub_url}: {e}")
            return details
        finally:
            if new_tab_created:
                try:
                    handles = self.driver.window_handles
                    if len(handles) > 1:
                        # Always keep the original, close everything else
                        for handle in handles:
                            if handle != original_window:
                                self.driver.switch_to.window(handle)
                                self.driver.close()
                        self.driver.switch_to.window(original_window)
                    # handles = self.driver.window_handles
                    # if len(handles) > 1:
                    #     cur = self.driver.current_window_handle
                    #     if cur != original_window and cur in handles:
                    #         self.driver.close()
                    #         time.sleep(0.5)
                    #     if original_window in self.driver.window_handles:
                    #         self.driver.switch_to.window(original_window)
                    #         time.sleep(0.5)
                except Exception as e:
                    logger.error(f"Error in finally block (details): {e}")
                    try:
                        handles = self.driver.window_handles
                        if handles:
                            self.driver.switch_to.window(handles[0])
                    except Exception:
                        pass

    # =========================================================================
    # PUBLICATION TYPE CLASSIFICATION
    # =========================================================================

    def classify_publication_type(self, journal, conference, publisher, title=""):
        if journal and journal.strip() and journal != 'N/A':
            return 'artikel'
        if conference and conference.strip() and conference != 'N/A':
            return 'prosiding'
        return self.classify_by_regex(publisher, title)

    def classify_by_regex(self, publisher, title=""):
        combined_text = f"{publisher} {title}".lower()
        if pd.isna(combined_text) or combined_text.strip() == "":
            return 'lainnya'
        book_publishers = ['nuansa aulia', 'citra aditya bakti', 'yrama widya', 'pustaka belajar', 'pustaka pelajar', 'erlangga', 'andpublisher', 'prenadamedia', 'gramedia', 'grasindo', 'media', 'prenhalindo', 'prenhallindo', 'wiley', 'springer']
        if any(p in combined_text for p in book_publishers) or 'edisi' in combined_text:
            return 'buku'
        if any(k in combined_text for k in ['jurnal', 'journal', 'jou.', 'acta', 'review', 'letters']):
            return 'artikel'
        if any(k in combined_text for k in ['prosiding', 'proceedings', 'proc.', 'konferensi', 'conference', 'conf.', 'simposium', 'symposium', 'workshop', 'pertemuan', 'meeting']):
            return 'prosiding'
        if any(k in combined_text for k in ['buku', 'book', 'bab buku', 'chapter', 'handbook', 'ensiklopedia', 'encyclopedia', 'buku teks', 'textbook', 'penerbit', 'publisher', 'press', 'books']):
            return 'buku'
        if any(k in combined_text for k in ['tesis', 'thesis', 'disertasi', 'dissertation', 'skripsi', 'program doktor', 'program pascasarjana', 'phd', 'master', 'doctoral', 'program studi', 'fakultas', 'analisis', 'analysis', 'penelitian', 'research', 'arxiv', 'preprint', 'laporan teknis', 'technical report', 'naskah awal', 'working paper', 'teknis']):
            return 'penelitian'
        if 'paten' in combined_text or 'patent' in combined_text:
            return 'penelitian'
        if re.search(r'\bUU\s*No\.\s*\d+|Undang-undang\s*Nomor\s*\d+|Peraturan\s*(Pemerintah|Presiden)\s*No\.\s*\d+', combined_text):
            return 'buku'
        if re.search(r'vol\.|\bvol\b|\bedisi\b|\bno\.|\bhal\.|\bhalaman\b', combined_text) or re.search(r'\bvol\.\s*\d+\s*(\(\s*\d+\s*\))?', combined_text) or re.search(r'\d+\s*\(\d+\)', combined_text):
            return 'artikel'
        return 'lainnya'

    # =========================================================================
    # SCRAPE PROFILE
    # =========================================================================

    def scrape_profile(self, profile_url, author_name):
        try:
            if self.is_cancelled():
                return None
            logger.info(f"Accessing profile: {author_name}")
            self.driver.get(profile_url)
            time.sleep(random.uniform(5, 8))
            self.raise_if_cancelled()
            scholar_id = profile_url.split("user=")[1].split("&")[0] if "user=" in profile_url else ""
            try:
                name = WebDriverWait(self.driver, 20).until(EC.presence_of_element_located((By.CSS_SELECTOR, '#gsc_prf_in'))).text
            except TimeoutException:
                return None
            try:
                affiliation = self.driver.find_element(By.CSS_SELECTOR, '.gsc_prf_il').text
            except Exception as e:
                logger.error(f"affiliation not found")
                affiliation = ""
            citation_data = {'Citations_all': '0', 'Citations_since2020': '0', 'h-index_all': '0', 'h-index_since2020': '0', 'i10-index_all': '0', 'i10-index_since2020': '0'}
            try:
                for stat in self.driver.find_elements(By.CSS_SELECTOR, '#gsc_rsb_st tbody tr'):
                    try:
                        m = stat.find_element(By.CSS_SELECTOR, 'td:nth-of-type(1)').text
                        citation_data[f"{m}_all"] = stat.find_element(By.CSS_SELECTOR, 'td:nth-of-type(2)').text or '0'
                        citation_data[f"{m}_since2020"] = stat.find_element(By.CSS_SELECTOR, 'td:nth-of-type(3)').text or '0'
                    except Exception:
                        continue
            except Exception as e:
                logger.warning(f"Cannot get citation stats for {author_name}: {e}")
            citations_per_year = {}
            try:
                chart = self.driver.find_element(By.CSS_SELECTOR, '#gsc_g')
                for ye, ve in zip(chart.find_elements(By.CSS_SELECTOR, '.gsc_g_t'), chart.find_elements(By.CSS_SELECTOR, '.gsc_g_al')):
                    y = ye.text.strip()
                    if y.isdigit() and 2015 <= int(y) <= 2024:
                        style = ve.get_attribute('style')
                        c = style.split(':')[-1].strip('%') if style else '0'
                        citations_per_year[y] = int(c) if c.isdigit() else 0
            except Exception as e:
                logger.error(f"citation per year error : {e}")
                pass
            self.raise_if_cancelled()
            while True:
                if self.is_cancelled():
                    break
                try:
                    btn = self.driver.find_element(By.ID, 'gsc_bpf_more')
                    if btn.get_attribute('disabled'):
                        break
                    btn.click()
                    time.sleep(random.uniform(2, 3))
                except Exception as e:
                    logger.error(f"click button failed : {e}")
                    break
            self.raise_if_cancelled()
            publications = []
            pub_items = self.driver.find_elements(By.CSS_SELECTOR, '#gsc_a_b .gsc_a_tr')
            logger.info(f"Found {len(pub_items)} publications for {author_name}")
            for i, item in enumerate(pub_items):
                if self.is_cancelled():
                    break
                try:
                    te = item.find_element(By.CSS_SELECTOR, '.gsc_a_t a')
                    title = te.text
                    pub_link = te.get_attribute('href')
                    pub_details = self.get_publication_details(pub_link)
                    if self.is_cancelled():
                        break
                    publications.append({
                        'title': title,
                        'authors': pub_details.get('authors') or item.find_element(By.CSS_SELECTOR, '.gs_gray:nth-of-type(1)').text,
                        'venue': item.find_element(By.CSS_SELECTOR, '.gs_gray:nth-of-type(2)').text,
                        'journal': pub_details.get('journal', 'N/A'),
                        'conference': pub_details.get('conference', 'N/A'),
                        'publisher': pub_details.get('publisher', ''),
                        'year': item.find_element(By.CSS_SELECTOR, '.gsc_a_y span').text or "N/A",
                        'citations': item.find_element(By.CSS_SELECTOR, '.gsc_a_c a').text or "0",
                        'link': pub_link,
                        'Author': author_name,
                        'publication_type': self.classify_publication_type(pub_details.get('journal', 'N/A'), pub_details.get('conference', 'N/A'), pub_details.get('publisher', ''), title),
                        'volume': pub_details.get('volume', ''),
                        'issue': pub_details.get('issue', ''),
                        'pages': pub_details.get('pages', ''),
                        'citations_per_year': self.get_publication_citations_per_year(pub_link)
                    })
                    time.sleep(random.uniform(1, 2))
                except Exception as e:
                    logger.error(f"Error extracting publication: {e}")
            return {'name': name, 'affiliation': affiliation, 'profile_url': profile_url,
                    'scholar_id': scholar_id, 'citation_stats': citation_data,
                    'citations_per_year': citations_per_year, 'publications': publications}
        except InterruptedError:
            raise
        except Exception as e:
            logger.error(f"Error scraping profile: {e}")
            return None

    # =========================================================================
    # CITATIONS PER YEAR
    # =========================================================================

    def get_publication_citations_per_year(self, pub_url):
        original_window = self.driver.current_window_handle
        new_tab_created = False
        try:
            if not self.driver or not self.driver.session_id:
                return {}
            if self.is_cancelled():
                return {}
            self.driver.execute_script("window.open('');")
            new_tab_created = True
            time.sleep(random.uniform(0.5, 1))
            if len(self.driver.window_handles) < 2:
                return {}
            self.driver.switch_to.window(self.driver.window_handles[1])
            self.driver.get(pub_url)
            time.sleep(random.uniform(4, 6))
            try:
                WebDriverWait(self.driver, 25).until(EC.presence_of_element_located((By.CSS_SELECTOR, '.gsc_oci_main, .gs_scl')))
            except TimeoutException:
                pass
            self.driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
            time.sleep(1.5)
            self.driver.execute_script("window.scrollTo(0, 0);")
            time.sleep(1.5)
            soup = BeautifulSoup(self.driver.page_source, 'html.parser')
            citations_per_year = {}
            year_elements = soup.select('.gsc_oci_g_t')
            citation_elements = soup.select('.gsc_oci_g_a')
            for ye in year_elements:
                y = ye.text.strip()
                if y.isdigit() and 2000 <= int(y) <= 2030:
                    citations_per_year[y] = 0
            for ce in citation_elements:
                style = ce.get('style', '')
                lm = re.search(r'left:([0-9]+)px', style)
                if not lm:
                    continue
                lp = int(lm.group(1))
                closest_year = None
                min_dist = float('inf')
                for ye in year_elements:
                    ym = re.search(r'left:([0-9]+)px', ye.get('style', ''))
                    if not ym:
                        continue
                    d = abs(int(ym.group(1)) - lp)
                    if d < min_dist:
                        min_dist = d
                        closest_year = ye.text.strip()
                if closest_year and closest_year.isdigit() and 2000 <= int(closest_year) <= 2030:
                    cve = ce.select_one('.gsc_oci_g_al')
                    if cve and cve.text.strip().isdigit():
                        citations_per_year[closest_year] = int(cve.text.strip())
            return citations_per_year
        except Exception as e:
            logger.error(f"Error retrieving citations per year: {e}")
            return {}
        finally:
            if new_tab_created:
                try:
                    if self.driver and hasattr(self.driver, 'session_id') and self.driver.session_id:
                        handles = self.driver.window_handles
                        if len(handles) > 1:
                            cur = self.driver.current_window_handle
                            if cur != original_window and cur in handles:
                                self.driver.close()
                                time.sleep(0.5)
                            if original_window in self.driver.window_handles:
                                self.driver.switch_to.window(original_window)
                                time.sleep(0.5)
                except Exception as e:
                    logger.error(f"Error in finally block (citations): {e}")
                    try:
                        handles = self.driver.window_handles
                        if handles:
                            self.driver.switch_to.window(handles[0])
                    except Exception:
                        pass

    # =========================================================================
    # CSV & DATABASE IMPORT
    # =========================================================================

    def save_to_csv(self, profile_data):
        try:
            pd.DataFrame([{
                'Name': profile_data['name'], 'Affiliation': profile_data['affiliation'],
                'Profile URL': profile_data['profile_url'], 'ID Google Scholar': profile_data['scholar_id'],
                **profile_data['citation_stats'], 'Total_Publikasi': len(profile_data['publications']),
                'Tanggal_Unduh': datetime.datetime.now().strftime('%Y-%m-%d')
            }]).to_csv('all_dosen_data_profiles.csv', mode='a',
                       header=not os.path.exists('all_dosen_data_profiles.csv') or os.path.getsize('all_dosen_data_profiles.csv') == 0,
                       index=False, encoding='utf-8')
            pubs_csv = 'all_dosen_data_publications.csv'
            pd.DataFrame([{
                'title': p.get('title', ''), 'authors': p.get('authors', ''), 'venue': p.get('venue', ''),
                'journal': p.get('journal', 'N/A'), 'conference': p.get('conference', 'N/A'),
                'publisher': p.get('publisher', ''), 'publication_type': p.get('publication_type', 'lainnya'),
                'volume': p.get('volume', ''), 'issue': p.get('issue', ''), 'pages': p.get('pages', ''),
                'year': p.get('year', 'N/A'), 'citations': p.get('citations', '0'),
                'link': p.get('link', ''), 'Author': p.get('Author', '')
            } for p in profile_data['publications']]).to_csv(
                pubs_csv, mode='a',
                header=not os.path.exists(pubs_csv) or os.path.getsize(pubs_csv) == 0,
                index=False, encoding='utf-8')
        except Exception as e:
            logger.error(f"Error saving to CSV: {e}")

    def import_to_database(self, profile_data):
        cursor = None
        try:
            cursor = self.conn.cursor()
            cs = profile_data['citation_stats']
            cursor.execute(sql.SQL("""
                INSERT INTO tmp_dosen_dt (v_nama_dosen, n_total_publikasi, n_total_sitasi_gs, n_total_sitasi_gs2020,
                    v_id_googlescholar, n_h_index_gs, n_h_index_gs2020, n_i10_index_gs, n_i10_index_gs2020,
                    v_sumber, t_tanggal_unduh, v_link_url)
                VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s) RETURNING v_id_dosen
            """), (
                profile_data.get('name', ''), len(profile_data.get('publications', [])),
                int(cs.get('Citations_all', 0) or 0), int(cs.get('Citations_since2020', 0) or 0),
                profile_data.get('scholar_id', ''),
                int(cs.get('h-index_all', 0) or 0), int(cs.get('h-index_since2020', 0) or 0),
                int(cs.get('i10-index_all', 0) or 0), int(cs.get('i10-index_since2020', 0) or 0),
                'Google Scholar', datetime.datetime.now(), profile_data.get('profile_url', '')
            ))
            dosen_id = cursor.fetchone()[0]
            imported_count = 0
            for pub in profile_data.get('publications', []):
                try:
                    pub_type = normalize_publication_type(pub.get('publication_type', 'lainnya'))
                    try:
                        year = int(pub.get('year')) if pub.get('year') not in (None, 'N/A', '') else None
                    except Exception:
                        year = None
                    cursor.execute(sql.SQL("""
                        INSERT INTO stg_publikasi_tr (v_judul, v_jenis, v_tahun_publikasi, n_total_sitasi,
                            v_sumber, v_link_url, t_tanggal_unduh, v_authors, v_publisher)
                        VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s) RETURNING v_id_publikasi
                    """), (pub.get('title', ''), pub_type, year, int(pub.get('citations', 0) or 0),
                           'Google Scholar', pub.get('link', ''), datetime.datetime.now(),
                           pub.get('authors', ''), pub.get('publisher', '')))
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
                    if pub.get('citations_per_year'):
                        self._insert_sitasi_tahunan_batch(cursor, pub_id, pub['citations_per_year'])
                    cursor.execute(sql.SQL("SELECT 1 FROM stg_publikasi_dosen_dt WHERE v_id_publikasi=%s AND v_id_dosen=%s"), (pub_id, dosen_id))
                    if not cursor.fetchone():
                        cursor.execute(sql.SQL("INSERT INTO stg_publikasi_dosen_dt (v_id_publikasi, v_id_dosen, v_author_order) VALUES (%s,%s,%s)"), (pub_id, dosen_id, "1"))
                    imported_count += 1
                except Exception as e:
                    logger.error(f"Error importing publication: {e}")
                    continue
            self.conn.commit()
            return imported_count
        except Exception as e:
            self.conn.rollback()
            logger.error(f"Error importing to database: {e}")
            raise
        finally:
            if cursor:
                cursor.close()

    def _insert_artikel_data(self, cursor, pub_id, pub):
        try:
            jn = pub.get('journal', '')
            if not jn or jn == 'N/A':
                return
            cursor.execute(sql.SQL("SELECT v_id_jurnal FROM stg_jurnal_mt WHERE v_nama_jurnal=%s"), (jn,))
            r = cursor.fetchone()
            jid = r[0] if r else cursor.execute(sql.SQL("INSERT INTO stg_jurnal_mt (v_nama_jurnal) VALUES (%s) RETURNING v_id_jurnal"), (jn,)) or cursor.fetchone()[0]
            cursor.execute(sql.SQL("INSERT INTO stg_artikel_dr (v_id_publikasi,v_id_jurnal,v_volume,v_issue,v_pages,t_updated_at) VALUES (%s,%s,%s,%s,%s,%s)"),
                           (pub_id, jid, pub.get('volume', ''), pub.get('issue', ''), pub.get('pages', ''), datetime.datetime.now()))
        except Exception as e:
            logger.error(f"Error insert artikel data: {e}")

    def _insert_prosiding_data(self, cursor, pub_id, pub):
        try:
            cursor.execute(sql.SQL("INSERT INTO stg_prosiding_dr (v_id_publikasi,v_nama_konferensi,f_terindeks_scopus,t_updated_at) VALUES (%s,%s,%s,%s)"),
                           (pub_id, pub.get('conference', ''), False, datetime.datetime.now()))
        except Exception as e:
            logger.error(f"Error insert prosiding data: {e}")

    def _insert_buku_data(self, cursor, pub_id, pub):
        try:
            cursor.execute(sql.SQL("INSERT INTO stg_buku_dr (v_id_publikasi,v_isbn,t_updated_at) VALUES (%s,%s,%s)"),
                           (pub_id, '', datetime.datetime.now()))
        except Exception as e:
            logger.error(f"Error insert buku data: {e}")

    def _insert_penelitian_data(self, cursor, pub_id, pub):
        try:
            pt = str(pub.get('publication_type', '')).lower()
            kategori = 'Tesis' if 'tesis' in pt else ('Disertasi' if 'disertasi' in pt else 'Penelitian')
            cursor.execute(sql.SQL("INSERT INTO stg_penelitian_dr (v_id_publikasi,v_kategori_penelitian,t_updated_at) VALUES (%s,%s,%s)"),
                           (pub_id, kategori, datetime.datetime.now()))
        except Exception as e:
            logger.error(f"Error insert penelitian data: {e}")

    def _insert_lainnya_data(self, cursor, pub_id, pub):
        try:
            cursor.execute(sql.SQL("INSERT INTO stg_lainnya_dr (v_id_publikasi,v_keterangan,t_updated_at) VALUES (%s,%s,%s)"),
                           (pub_id, None, datetime.datetime.now()))
        except Exception as e:
            logger.error(f"Error insert lainnya data: {e}")

    def _insert_sitasi_tahunan_batch(self, cursor, pub_id, citations_per_year):
        try:
            if not citations_per_year or not isinstance(citations_per_year, dict):
                return
            for year, citations in citations_per_year.items():
                try:
                    if not str(year).isdigit():
                        continue
                    yi = int(year)
                    if yi < 2000 or yi > 2030:
                        continue
                    cursor.execute(sql.SQL("INSERT INTO stg_publikasi_sitasi_tahunan_dr (v_id_publikasi,v_tahun,n_total_sitasi_tahun,v_sumber,t_tanggal_unduh) VALUES (%s,%s,%s,%s,%s)"),
                                   (pub_id, yi, int(citations) if citations else 0, 'Google Scholar', datetime.datetime.now().date()))
                except Exception as e:
                    logger.error(f"Error insert sitasi untuk tahun {year}: {e}")
        except Exception as e:
            logger.error(f"Error insert sitasi tahunan batch: {e}")

    # =========================================================================
    # MAIN RUN
    # =========================================================================

    def run(self, max_authors=10, scrape_from_beginning=False):
        def _timeout_handler(signum, frame):
            raise TimeoutError("Scraping author timeout! Melebihi 30 menit.")

        try:
            if not self.connect_to_db():
                raise Exception("Failed to connect to database")
            df = self.get_authors_from_db(scrape_from_beginning)
            if df.empty:
                raise Exception("No authors to scrape")
            max_authors = min(max_authors, len(df))
            self.emit_progress({'message': 'Setting up browser...', 'current': 0, 'total': max_authors})
            self.raise_if_cancelled()
            self.setup_driver_with_auto_login()
            if not self.driver:
                raise Exception("Failed to setup driver")
            successful = 0
            failed = 0
            try:
                for index, row in df.head(max_authors).iterrows():
                    author_name = row['Name']
                    profile_url = row['Profile URL']
                    if self.is_cancelled():
                        self.emit_progress({'message': 'Scraping dibatalkan oleh user.', 'status': 'cancelled'})
                        break
                    self.emit_progress({'message': f'Scraping {author_name} ({index + 1}/{max_authors})...', 'current': index + 1, 'total': max_authors, 'status': 'running'})
                    self.update_scraping_status(author_name, 'processing')
                    signal.signal(signal.SIGALRM, _timeout_handler)
                    signal.alarm(1800)
                    try:
                        profile_data = self.scrape_profile(profile_url, author_name)
                        if self.is_cancelled():
                            signal.alarm(0)
                            self.emit_progress({'message': 'Scraping dibatalkan oleh user.', 'status': 'cancelled'})
                            break
                        if profile_data and profile_data.get('publications'):
                            self.save_to_csv(profile_data)
                            self.import_to_database(profile_data)
                            self.update_scraping_status(author_name, 'completed')
                            successful += 1
                            logger.info(f"✅ Berhasil: {author_name} ({len(profile_data['publications'])} publikasi)")
                        else:
                            self.update_scraping_status(author_name, 'error', 'No publications found')
                            failed += 1
                    except InterruptedError:
                        signal.alarm(0)
                        self.emit_progress({'message': 'Scraping dibatalkan oleh user.', 'status': 'cancelled'})
                        self.update_scraping_status(author_name, 'pending', 'Dibatalkan oleh user')
                        break
                    except TimeoutError as te:
                        logger.error(f"⏰ TIMEOUT scraping {author_name}: {te}")
                        self.update_scraping_status(author_name, 'error', f'Timeout: {te}')
                        failed += 1
                        try:
                            if self.driver:
                                self.driver.quit()
                        except Exception:
                            pass
                        if hasattr(self, '_chrome_user_data_dir') and os.path.exists(self._chrome_user_data_dir):
                            import shutil
                            shutil.rmtree(self._chrome_user_data_dir, ignore_errors=True)
                        try:
                            self.raise_if_cancelled()
                            self.setup_driver_with_auto_login()
                        except InterruptedError:
                            break
                        except Exception as restart_err:
                            logger.error(f"Gagal restart driver: {restart_err}")
                            break
                    except Exception as e:
                        logger.error(f"❌ Error scraping {author_name}: {e}")
                        self.update_scraping_status(author_name, 'error', str(e))
                        failed += 1
                    finally:
                        signal.alarm(0)
                    if index < max_authors - 1 and not self.is_cancelled():
                        delay = random.uniform(5, 20)
                        self.emit_progress({'message': f'Waiting {delay:.1f}s before next scrape... ({successful} berhasil, {failed} gagal)', 'current': index + 1, 'total': max_authors})
                        elapsed = 0
                        while elapsed < delay:
                            if self.is_cancelled():
                                break
                            time.sleep(min(5, delay - elapsed))
                            elapsed += 5
            finally:
                signal.alarm(0)
                if self.driver:
                    try:
                        self.driver.quit()
                    except Exception:
                        pass
                if hasattr(self, '_chrome_user_data_dir') and os.path.exists(self._chrome_user_data_dir):
                    import shutil
                    shutil.rmtree(self._chrome_user_data_dir, ignore_errors=True)
            if self.is_cancelled():
                return {'success': True, 'message': f'Scraping dibatalkan. {successful} berhasil, {failed} gagal sebelum dibatalkan.', 'summary': {'total_attempted': successful + failed, 'successful': successful, 'failed': failed, 'cancelled': True}}
            return {'success': True, 'message': f'Selesai scraping {successful + failed} author: {successful} berhasil, {failed} gagal', 'summary': {'total_attempted': successful + failed, 'successful': successful, 'failed': failed, 'cancelled': False}}
        except InterruptedError:
            return {'success': True, 'message': 'Scraping dibatalkan oleh user.', 'summary': {'cancelled': True}}
        except Exception as e:
            logger.error(f"Error in main run: {e}")
            raise
        finally:
            if self.conn:
                self.conn.close()


# =============================================================================
# HELPERS
# =============================================================================

def normalize_publication_type(pub_type):
    pt = str(pub_type).lower().strip()
    if 'jurnal' in pt or 'artikel' in pt:
        return 'artikel'
    elif 'prosiding' in pt or 'conference' in pt:
        return 'prosiding'
    elif 'buku' in pt or 'book' in pt:
        return 'buku'
    elif 'penelitian' in pt or 'tesis' in pt or 'disertasi' in pt:
        return 'penelitian'
    else:
        return 'lainnya'


if __name__ == "__main__":
    DB_CONFIG = {
        'dbname': 'skm_scraper', 'user': 'skm_scraper',
        'password': 'unparScr4per', 'host': '10.211.1.188', 'port': '5432'
    }
    scraper = GoogleScholarScraper(db_config=DB_CONFIG, email="6182101045@student.unpar.ac.id", password="hariharto123")
    result = scraper.run(max_authors=5, scrape_from_beginning=False)
    print(result)