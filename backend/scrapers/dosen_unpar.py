#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Mon Sep 22 11:23:34 2025
Modified: Added Auto-Login with Account Rotation

@author: rayhanadjisantoso
"""

import pandas as pd
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, NoSuchElementException
from webdriver_manager.chrome import ChromeDriverManager
import time
import random
import urllib.parse
import os

# Multi-account pool for login rotation
ACCOUNT_POOL = [
    {"email": "6182101017@student.unpar.ac.id", "password": "618017SH"},
    {"email": "6182101045@student.unpar.ac.id", "password": "6180145CD"},
    {"email": "6182101059@student.unpar.ac.id", "password": "618059SJ"},
    {"email": "6182101063@student.unpar.ac.id", "password": "618063XJ"},
]

# Global variables for account management
current_account_index = 0
failed_accounts = set()
restart_count = 0
max_restarts = 3

def get_next_account():
    """Get next available account that hasn't failed (random selection)"""
    global current_account_index, failed_accounts
    
    # Get list of indices that haven't failed
    available_indices = [i for i in range(len(ACCOUNT_POOL)) if i not in failed_accounts]
    
    if not available_indices:
        # All accounts have failed
        return None, None
    
    # Random selection from available accounts
    selected_index = random.choice(available_indices)
    account = ACCOUNT_POOL[selected_index]
    
    return account, selected_index

def mark_account_failed(account_index):
    """Mark an account as failed (hit CAPTCHA)"""
    global failed_accounts
    failed_accounts.add(account_index)
    print(f"⚠️  Account {account_index + 1} ({ACCOUNT_POOL[account_index]['email']}) marked as failed (CAPTCHA detected)")
    print(f"   Failed accounts: {len(failed_accounts)}/{len(ACCOUNT_POOL)}")

def reset_failed_accounts():
    """Reset failed accounts (for retry after all failed)"""
    global failed_accounts, current_account_index
    failed_accounts.clear()
    print("♻️  All accounts reset for new attempt")

def setup_driver():
    """Setup dan mengembalikan WebDriver dengan konfigurasi yang sesuai"""
    chrome_options = Options()
    
    # Konfigurasi dasar
    chrome_options.add_argument("--no-sandbox")
    chrome_options.add_argument("--disable-dev-shm-usage")
    chrome_options.add_argument("--disable-gpu")
    chrome_options.add_argument("--window-size=1920,1080")
    
    # Opsi untuk mencegah crash
    chrome_options.add_argument("--disable-extensions")
    chrome_options.add_argument("--disable-infobars")
    chrome_options.add_argument("--disable-browser-side-navigation")
    chrome_options.add_argument("--disable-features=NetworkService")
    chrome_options.add_argument("--disable-web-security")
    chrome_options.add_argument("--disable-site-isolation-trials")
    
    # Tambahkan variasi user agent
    user_agents = [
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:109.0) Gecko/20100101 Firefox/115.0",
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/16.5 Safari/605.1.15"
    ]
    chrome_options.add_argument(f"--user-agent={random.choice(user_agents)}")
    
    # Opsi untuk menghindari deteksi bot
    chrome_options.add_argument("--disable-blink-features=AutomationControlled")
    chrome_options.add_experimental_option("excludeSwitches", ["enable-automation"])
    chrome_options.add_experimental_option('useAutomationExtension', False)
    
    # Menambahkan prefs
    prefs = {
        "profile.default_content_setting_values.notifications": 2,
        "profile.default_content_settings.popups": 0,
        "profile.managed_default_content_settings.images": 2,
        "profile.default_content_setting_values.cookies": 1,
        "profile.cookie_controls_mode": 0,
        "profile.block_third_party_cookies": False
    }
    chrome_options.add_experimental_option("prefs", prefs)
    
    # Gunakan ChromeDriverManager
    try:
        driver_path = ChromeDriverManager().install()

        if os.path.basename(driver_path) != 'chromedriver':
            driver_dir = os.path.dirname(driver_path)
            candidate_path = os.path.join(driver_dir, 'chromedriver')
            if os.path.exists(candidate_path):
                driver_path = candidate_path

        import platform
        import subprocess
        try:
            os.chmod(driver_path, 0o755)
        except Exception as chmod_error:
            print(f"Warning: Tidak dapat mengatur permission chromedriver: {chmod_error}")

        if platform.system() == 'Darwin':
            try:
                subprocess.run(['xattr', '-d', 'com.apple.quarantine', driver_path],
                               capture_output=True, check=False)
            except Exception as perm_error:
                print(f"Warning: Tidak dapat menghapus atribut quarantine: {perm_error}")

        service = Service(driver_path)
        driver = webdriver.Chrome(service=service, options=chrome_options)
        
    except Exception as e:
        print(f"Error saat membuat driver: {e}")
        print("Trying alternative method...")
        
        try:
            driver = webdriver.Chrome(options=chrome_options)
        except Exception as e2:
            print(f"Error alternatif saat membuat driver: {e2}")
            
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
                raise
    
    # Hapus properti webdriver
    try:
        driver.execute_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")
    except Exception as e:
        print(f"Warning: Tidak dapat menyembunyikan webdriver: {e}")
    
    # Set timeouts
    driver.set_page_load_timeout(120)
    driver.implicitly_wait(30)
    
    return driver

def check_if_logged_in(driver):
    """Check if successfully logged in to Google Scholar"""
    try:
        time.sleep(3)
        
        try:
            driver.find_element(By.ID, "gs_hdr_act_s")
            return False
        except NoSuchElementException:
            try:
                profile_element = driver.find_element(By.CSS_SELECTOR, '#gs_gb_rt a')
                return True
            except:
                pass
            
            current_url = driver.current_url
            if 'scholar.google.com' in current_url and 'accounts.google.com' not in current_url:
                return True
        
        return False
        
    except Exception as e:
        print(f"Error checking login status: {e}")
        return False

def perform_auto_login(driver):
    """Perform automatic login to Google Scholar through SSO with account rotation"""
    global restart_count, max_restarts
    
    # Start with first account
    account, idx = get_next_account()
    if account:
        email = account['email']
        password = account['password']
        current_account_index = idx
    else:
        raise Exception("No accounts available")
    
    while restart_count < max_restarts:
        # Try login with available accounts
        while True:
            # Check if all accounts failed
            if len(failed_accounts) >= len(ACCOUNT_POOL):
                print(f"\n⚠️  All {len(ACCOUNT_POOL)} accounts have failed!")
                restart_count += 1
                
                if restart_count >= max_restarts:
                    raise Exception(f"Login failed after {max_restarts} complete restarts. All accounts hit CAPTCHA.")
                
                # Delay 2-5 minutes before restart
                delay = random.uniform(120, 300)
                print(f"\n🔄 Restart attempt {restart_count}/{max_restarts}")
                print(f"⏳ Waiting {delay/60:.1f} minutes before restarting from Step 1...")
                time.sleep(delay)
                
                # Reset all accounts and close driver
                reset_failed_accounts()
                try:
                    driver.quit()
                except:
                    pass
                
                # Setup new driver
                driver = setup_driver()
                
                # Select random account for restart
                account, idx = get_next_account()
                if account:
                    email = account['email']
                    password = account['password']
                    current_account_index = idx
                    print(f"\n🔄 Restarting with random account: {email}")
                break
            
            # Get next available account
            account, idx = get_next_account()
            if not account:
                break
            
            email = account['email']
            password = account['password']
            current_account_index = idx
            
            print(f"\n🔐 Attempting login with account {idx + 1}: {email}")
            
            try:
                # Step 1: Open Google Scholar
                print("Step 1: Opening https://scholar.google.com/")
                driver.get("https://scholar.google.com/")
                time.sleep(random.uniform(11, 29))
                
                # Step 2: Click Login button
                print("Step 2: Clicking Login button")
                try:
                    login_button = WebDriverWait(driver, 10).until(
                        EC.element_to_be_clickable((By.ID, "gs_hdr_act_s"))
                    )
                    login_button.click()
                    time.sleep(random.uniform(21, 25))
                except Exception as e:
                    print(f"Could not find login button: {e}")
                    if check_if_logged_in(driver):
                        print("✓ Already logged in!")
                        return driver
                    raise
                
                # Step 3: Enter email on Google login page
                print("Step 3: Entering email on Google login page")
                
                email_input = WebDriverWait(driver, 15).until(
                    EC.presence_of_element_located((By.ID, "identifierId"))
                )
                
                time.sleep(random.uniform(10, 30))
                email_input.clear()
                time.sleep(random.uniform(9, 16))
                
                # Type email character by character with random delays
                for char in email:
                    email_input.send_keys(char)
                    time.sleep(random.uniform(5, 9))
                
                time.sleep(random.uniform(7, 15))
                
                # Step 4: Click Next button (Google)
                print("Step 4: Clicking Next button")
                
                next_button = WebDriverWait(driver, 10).until(
                    EC.element_to_be_clickable((By.XPATH, "//span[contains(text(), 'Selanjutnya')]"))
                )
                next_button.click()
                time.sleep(random.uniform(13, 28))
                
                # Step 5: Check for CAPTCHA
                print("Step 5: Checking for CAPTCHA")
                
                try:
                    captcha = driver.find_element(By.ID, "captchaimg")
                    if captcha.is_displayed():
                        print(f"⚠️  CAPTCHA detected for account {idx + 1}!")
                        mark_account_failed(idx)
                        continue
                except NoSuchElementException:
                    print("✓ No CAPTCHA detected, continuing...")
                
                # Step 6: Enter email on SSO page
                print("Step 6: Entering email on UNPAR SSO page")
                
                sso_email_input = WebDriverWait(driver, 15).until(
                    EC.presence_of_element_located((By.ID, "username"))
                )
                
                time.sleep(random.uniform(8, 19))
                sso_email_input.clear()
                time.sleep(random.uniform(9, 17))
                
                # Type email character by character
                for char in email:
                    sso_email_input.send_keys(char)
                    time.sleep(random.uniform(8, 14))
                
                time.sleep(random.uniform(13, 25))
                
                # Step 7: Click Next on SSO
                print("Step 7: Clicking Next button on SSO")
                
                sso_next_button = WebDriverWait(driver, 10).until(
                    EC.element_to_be_clickable((By.ID, "next_login"))
                )
                sso_next_button.click()
                time.sleep(random.uniform(14, 27))
                
                # Step 8: Enter password
                print("Step 8: Entering password")
                
                password_input = WebDriverWait(driver, 10).until(
                    EC.presence_of_element_located((By.ID, "password"))
                )
                
                time.sleep(random.uniform(9, 22))
                password_input.clear()
                time.sleep(random.uniform(13, 18))
                
                # Type password character by character
                for char in password:
                    password_input.send_keys(char)
                    time.sleep(random.uniform(8, 14))
                
                time.sleep(random.uniform(10, 23))
                
                # Step 9: Click Login button
                print("Step 9: Clicking Login button")
                
                login_submit = WebDriverWait(driver, 10).until(
                    EC.element_to_be_clickable((By.CSS_SELECTOR, "button.login__submit2"))
                )
                login_submit.click()
                time.sleep(random.uniform(13, 27))
                
                # Step 10: Click Continue on confirmation page
                print("Step 10: Clicking Continue button")
                
                try:
                    continue_button = WebDriverWait(driver, 10).until(
                        EC.element_to_be_clickable((By.XPATH, "//span[contains(text(), 'Lanjutkan')]"))
                    )
                    continue_button.click()
                    time.sleep(random.uniform(12, 18))
                except TimeoutException:
                    print("Continue button not found or already passed")
                
                # Verify login success
                print("Verifying login success...")
                
                if check_if_logged_in(driver):
                    print(f"✓ Login successful with {email}!")
                    return driver
                else:
                    raise Exception("Login verification failed")
                
            except Exception as e:
                print(f"Error during login with account {idx + 1}: {e}")
                mark_account_failed(idx)
                continue
    
    # If we've exhausted all restarts
    raise Exception(f"Login failed after {max_restarts} complete restarts. Unable to bypass CAPTCHA.")

def setup_driver_with_auto_login():
    """Setup driver dan lakukan login otomatis"""
    driver = setup_driver()
    
    try:
        driver = perform_auto_login(driver)
        if driver:
            print("✓ Driver ready with successful login")
            return driver
        else:
            raise Exception("Auto-login failed")
    except Exception as e:
        print(f"Error during setup with auto-login: {e}")
        try:
            driver.quit()
        except:
            pass
        return None

def get_all_unpar_scholars(max_pages=100, driver=None, search_query=None):
    """
    Scrape scholars menggunakan driver yang sudah login atau membuat driver baru
    
    Args:
        max_pages: Jumlah maksimal halaman yang akan di-scrape
        driver: WebDriver yang sudah login (optional, akan dibuat otomatis jika None)
        search_query: Query pencarian custom (optional)
    
    Returns:
        List of scholar dictionaries
    """
    scholars = []
    if search_query is None:
        search_query = '"Universitas Katolik Parahyangan" OR "Parahyangan Catholic University" OR "unpar"'
    
    # Flag untuk tracking apakah driver dibuat di sini
    driver_created_here = False
    
    try:
        # Jika driver tidak diberikan, buat driver baru dengan auto-login
        if driver is None:
            print("Driver tidak diberikan, membuat driver baru dengan auto-login...")
            driver = setup_driver_with_auto_login()
            if driver is None:
                raise Exception("Gagal membuat driver dengan auto-login")
            driver_created_here = True
        base_url = "https://scholar.google.com/citations?view_op=search_authors&mauthors={}&hl=en"
        
        page_count = 0
        encoded_query = urllib.parse.quote(search_query)
        url = base_url.format(encoded_query)
        driver.get(url)
        print(f"\nScraping dimulai untuk query: {search_query}")
        print(f"URL: {url}")
        
        while page_count < max_pages:
            print(f"Scraping halaman {page_count + 1}...")
            
            # Use WebDriverWait to ensure the profiles are loaded
            wait = WebDriverWait(driver, 10)
            profiles = wait.until(EC.presence_of_all_elements_located((By.CSS_SELECTOR, '.gs_ai_chpr')))
            
            for profile in profiles:
                try:
                    name_elem = profile.find_element(By.CSS_SELECTOR, '.gs_ai_name a')
                    affil_elem = profile.find_element(By.CSS_SELECTOR, '.gs_ai_aff')
                    citations_elem = profile.find_elements(By.CSS_SELECTOR, '.gs_ai_cby')
                    
                    name = name_elem.text.strip()
                    profile_url = name_elem.get_attribute('href')
                    affiliation = affil_elem.text.strip()
                    
                    if citations_elem:
                        citations_text = citations_elem[0].text.strip().replace("Cited by", "").strip()
                        citations = int(citations_text) if citations_text.isdigit() else 0
                    else:
                        citations = 0
                    
                    # Extract Google Scholar ID from profile URL
                    scholar_id = ""
                    if "user=" in profile_url:
                        scholar_id = profile_url.split("user=")[1]
                    
                    scholars.append({
                        'ID Google Scholar': scholar_id,
                        'Name': name,
                        'Affiliation': affiliation,
                        'Citations': citations,
                        'Profile URL': profile_url
                    })
                except Exception as e:
                    print(f"Gagal mengambil data untuk satu profil: {e}")
                    continue

            # Find the "Next" button
            try:
                next_button = driver.find_element(By.CSS_SELECTOR, '.gsc_pgn button[aria-label="Next"]')
                
                # Check if the button is disabled
                if 'gs_dis' in next_button.get_attribute('class'):
                    print("Tombol 'Next' dinonaktifkan, mengakhiri scraping.")
                    break
                    
                # Scroll to the button and click it to ensure it's in view
                driver.execute_script("arguments[0].scrollIntoView(true);", next_button)
                next_button.click()
                
            except Exception as e:
                print(f"Tidak ada tombol 'Next' ditemukan atau terjadi kesalahan: {e}")
                break
            
            page_count += 1
            time.sleep(3)  # Longer delay to mimic human behavior
            
    except Exception as e:
        print(f"Terjadi kesalahan saat scraping: {e}")
    
    return scholars

# Run the script
if __name__ == "__main__":
    print("="*60)
    print("GOOGLE SCHOLAR SCRAPER - AUTO LOGIN MODE")
    print("="*60)
    print(f"Account Pool: {len(ACCOUNT_POOL)} accounts available")
    print(f"Max Restarts: {max_restarts}")
    print("="*60 + "\n")
    
    # Reset global variables
    restart_count = 0
    failed_accounts = set()
    
    # Setup driver dengan auto-login
    print("Memulai setup driver dengan auto-login...")
    driver = setup_driver_with_auto_login()
    
    if driver is None:
        print("✗ Gagal membuat driver dengan auto-login. Program berhenti.")
        exit(1)
    
    print("\n" + "="*60)
    print("MEMULAI SCRAPING DOSEN UNPAR")
    print("="*60 + "\n")
    
    try:
        scholars_data = get_all_unpar_scholars(driver, max_pages=100)
        
        if scholars_data:
            df = pd.DataFrame(scholars_data)

            # Hapus duplikasi berdasarkan Profile URL
            df_clean = df.drop_duplicates(subset=["Profile URL"])
            df_clean.to_csv("dosen_unpar_gs.csv", index=False, encoding="utf-8")
            print(f"\n✓ Data bersih (tanpa duplikasi) telah disimpan dalam 'dosen_unpar_gs.csv'.")
            print(f"✓ Total: {len(df_clean)} dosen ditemukan.")
        else:
            print("\n✗ Tidak ada data ditemukan.")
    
    except Exception as e:
        print(f"\n✗ Error saat scraping: {e}")
        import traceback
        traceback.print_exc()
    
    finally:
        if driver is not None:
            try:
                driver.quit()
                print("\n✓ Driver berhasil ditutup")
            except Exception as e:
                print(f"✗ Error saat menutup driver: {e}")