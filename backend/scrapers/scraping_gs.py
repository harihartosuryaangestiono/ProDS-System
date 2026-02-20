#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Combined Google Scholar Scraper with PostgreSQL Database Import and Auto-Login
Created on Wed Sep 24 12:18:02 2025
@author: rayhanadjisantoso
"""

import selenium
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, NoSuchElementException, StaleElementReferenceException
import time
import random
from bs4 import BeautifulSoup
import pandas as pd
import re
import datetime
from roman import fromRoman
import json
import psycopg2
from psycopg2 import sql
import os
import uuid
import shutil

# Database connection parameters
DB_PARAMS = {
    'dbname': 'ProDSGabungan',
    'user': 'postgres',
    'password': 'password123',
    'host': 'localhost',
    'port': '5432'
}

# Multi-account pool for login rotation
ACCOUNT_POOL = [
    {"email": "6182101017@student.unpar.ac.id", "password": "618017SH"},
    {"email": "6182101045@student.unpar.ac.id", "password": "hariharto123"},
    {"email": "6182101059@student.unpar.ac.id", "password": "618059SJ"},
    {"email": "6182101063@student.unpar.ac.id", "password": "618063XJ"},
]

# Global variables for account management
current_account_index = 0
failed_accounts = set()
restart_count = 0
max_restarts = 3

# ======================================================
# Global untuk tracking user-data-dir yang aktif
# ======================================================
_current_user_data_dir = None

def get_next_account():
    """Get next available account that hasn't failed (random selection)"""
    global current_account_index, failed_accounts
    available_indices = [i for i in range(len(ACCOUNT_POOL)) if i not in failed_accounts]
    if not available_indices:
        return None, None
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

def cleanup_user_data_dir():
    """Bersihkan user-data-dir Chrome yang aktif"""
    global _current_user_data_dir
    if _current_user_data_dir and os.path.exists(_current_user_data_dir):
        shutil.rmtree(_current_user_data_dir, ignore_errors=True)
        print(f"✓ Cleaned up user-data-dir: {_current_user_data_dir}")
        _current_user_data_dir = None

def setup_driver():
    """
    Setup dan mengembalikan WebDriver.
    FIX: Headless mode + chromedriver sistem + unique user-data-dir
    """
    global _current_user_data_dir

    chrome_options = Options()

    # ======================================================
    # FIX 1: Headless mode - WAJIB di VPS (tidak ada display)
    # ======================================================
    chrome_options.add_argument("--headless=new")
    chrome_options.add_argument("--no-sandbox")
    chrome_options.add_argument("--disable-dev-shm-usage")
    chrome_options.add_argument("--disable-gpu")
    chrome_options.add_argument("--window-size=1920,1080")
    chrome_options.add_argument("--disable-extensions")
    chrome_options.add_argument("--disable-infobars")
    chrome_options.add_argument("--disable-browser-side-navigation")
    chrome_options.add_argument("--disable-features=NetworkService")
    chrome_options.add_argument("--disable-web-security")
    chrome_options.add_argument("--disable-site-isolation-trials")
    chrome_options.add_argument("--single-process")

    # User agent rotation
    user_agents = [
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:109.0) Gecko/20100101 Firefox/115.0",
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/16.5 Safari/605.1.15"
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
        "profile.default_content_setting_values.cookies": 1,
        "profile.cookie_controls_mode": 0,
        "profile.block_third_party_cookies": False
    }
    chrome_options.add_experimental_option("prefs", prefs)

    # ======================================================
    # FIX 2: Unique user-data-dir - mencegah conflict session
    # ======================================================
    cleanup_user_data_dir()  # Bersihkan yang lama dulu
    user_data_dir = f"/tmp/chrome_profile_{uuid.uuid4().hex}"
    os.makedirs(user_data_dir, exist_ok=True)
    _current_user_data_dir = user_data_dir
    chrome_options.add_argument(f"--user-data-dir={user_data_dir}")
    print(f"✓ Chrome user-data-dir: {user_data_dir}")

    # ======================================================
    # FIX 3: Langsung pakai chromedriver sistem, skip ChromeDriverManager
    # ======================================================
    chromedriver_path = shutil.which('chromedriver') or '/usr/local/bin/chromedriver'

    if not os.path.exists(chromedriver_path):
        raise Exception(
            f"ChromeDriver tidak ditemukan di: {chromedriver_path}\n"
            f"Install dulu:\n"
            f"  wget https://storage.googleapis.com/chrome-for-testing-public/141.0.7390.54/linux64/chromedriver-linux64.zip\n"
            f"  unzip chromedriver-linux64.zip\n"
            f"  sudo mv chromedriver-linux64/chromedriver /usr/local/bin/chromedriver\n"
            f"  sudo chmod +x /usr/local/bin/chromedriver"
        )

    print(f"✓ Menggunakan chromedriver: {chromedriver_path}")
    service = Service(chromedriver_path)
    driver = webdriver.Chrome(service=service, options=chrome_options)

    # Hapus properti webdriver
    try:
        driver.execute_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")
    except Exception as e:
        print(f"Warning: Tidak dapat menyembunyikan webdriver: {e}")

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
                driver.find_element(By.CSS_SELECTOR, '#gs_gb_rt a')
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

    account, idx = get_next_account()
    if account:
        email = account['email']
        password = account['password']
        current_account_index = idx
    else:
        raise Exception("No accounts available")

    while restart_count < max_restarts:
        while True:
            if len(failed_accounts) >= len(ACCOUNT_POOL):
                print(f"\n⚠️  All {len(ACCOUNT_POOL)} accounts have failed!")
                restart_count += 1

                if restart_count >= max_restarts:
                    raise Exception(f"Login failed after {max_restarts} complete restarts. All accounts hit CAPTCHA.")

                delay = random.uniform(120, 300)
                print(f"\n🔄 Restart attempt {restart_count}/{max_restarts}")
                print(f"⏳ Waiting {delay/60:.1f} minutes before restarting from Step 1...")
                time.sleep(delay)

                reset_failed_accounts()
                try:
                    driver.quit()
                except:
                    pass
                cleanup_user_data_dir()

                driver = setup_driver()

                account, idx = get_next_account()
                if account:
                    email = account['email']
                    password = account['password']
                    current_account_index = idx
                    print(f"\n🔄 Restarting with random account: {email}")
                break

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

                # Screenshot debug
                driver.save_screenshot('/tmp/debug_step1.png')
                print(f"  URL: {driver.current_url} | Title: {driver.title}")

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
                time.sleep(random.uniform(10, 20))
                email_input.clear()
                time.sleep(random.uniform(5, 10))
                for char in email:
                    email_input.send_keys(char)
                    time.sleep(random.uniform(0.1, 0.3))
                time.sleep(random.uniform(7, 15))

                # Step 4: Click Next button (Google) - coba berbagai selector
                print("Step 4: Clicking Next button")
                driver.save_screenshot('/tmp/debug_step4.png')
                print(f"  URL: {driver.current_url} | Title: {driver.title}")

                next_button = None
                next_selectors = [
                    (By.XPATH, "//span[contains(text(), 'Selanjutnya')]"),
                    (By.XPATH, "//span[contains(text(), 'Next')]"),
                    (By.XPATH, "//button[contains(@jsname, 'LgbsSe')]"),
                    (By.CSS_SELECTOR, "#identifierNext"),
                    (By.CSS_SELECTOR, "button[type='submit']"),
                ]
                for selector_type, selector in next_selectors:
                    try:
                        next_button = WebDriverWait(driver, 5).until(
                            EC.element_to_be_clickable((selector_type, selector))
                        )
                        print(f"  ✓ Found next button with selector: {selector}")
                        break
                    except:
                        continue

                if not next_button:
                    raise Exception("Next button tidak ditemukan dengan semua selector yang dicoba")

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
                driver.save_screenshot('/tmp/debug_step6.png')
                print(f"  URL: {driver.current_url} | Title: {driver.title}")

                sso_email_input = WebDriverWait(driver, 15).until(
                    EC.presence_of_element_located((By.ID, "username"))
                )
                time.sleep(random.uniform(8, 15))
                sso_email_input.clear()
                time.sleep(random.uniform(5, 10))
                for char in email:
                    sso_email_input.send_keys(char)
                    time.sleep(random.uniform(0.1, 0.3))
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
                time.sleep(random.uniform(9, 15))
                password_input.clear()
                time.sleep(random.uniform(5, 10))
                for char in password:
                    password_input.send_keys(char)
                    time.sleep(random.uniform(0.1, 0.3))
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
        cleanup_user_data_dir()
        return None

def scrape_google_scholar_profile_with_existing_driver(driver, profile_url, author_name):
    """Scrape Google Scholar profile using an existing driver (already logged in)"""
    try:
        print(f"Accessing profile for: {author_name}")
        print(f"Profile URL: {profile_url}")

        driver.get(profile_url)
        time.sleep(random.uniform(5, 8))

        scholar_id = ""
        if "user=" in profile_url:
            scholar_id = profile_url.split("user=")[1].split("&")[0]

        try:
            name = WebDriverWait(driver, 20).until(
                EC.presence_of_element_located((By.CSS_SELECTOR, '#gsc_prf_in'))
            ).text
        except TimeoutException:
            print(f"Timeout saat mengambil nama untuk {author_name}")
            return None

        try:
            affiliation = driver.find_element(By.CSS_SELECTOR, '.gsc_prf_il').text
        except NoSuchElementException:
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
            citation_stats = driver.find_elements(By.CSS_SELECTOR, '#gsc_rsb_st tbody tr')
            if citation_stats:
                for stat in citation_stats:
                    try:
                        metric_name = stat.find_element(By.CSS_SELECTOR, 'td:nth-of-type(1)').text
                        all_citations = stat.find_element(By.CSS_SELECTOR, 'td:nth-of-type(2)').text
                        recent_citations = stat.find_element(By.CSS_SELECTOR, 'td:nth-of-type(3)').text
                        citation_data[f"{metric_name}_all"] = all_citations if all_citations else '0'
                        citation_data[f"{metric_name}_since2020"] = recent_citations if recent_citations else '0'
                    except Exception as e:
                        print(f"Warning: Error saat extract metrik: {e}")
                        continue
        except Exception as e:
            print(f"Warning: Tidak dapat mengambil citation stats untuk {author_name}: {e}")

        citations_per_year = {}
        try:
            chart = driver.find_element(By.CSS_SELECTOR, '#gsc_g')
            years = chart.find_elements(By.CSS_SELECTOR, '.gsc_g_t')
            values = chart.find_elements(By.CSS_SELECTOR, '.gsc_g_al')

            if len(years) == len(values):
                for year_element, value_element in zip(years, values):
                    year = year_element.text.strip()
                    citations = value_element.get_attribute('style').split(':')[-1].strip('%')
                    if year.isdigit() and 2015 <= int(year) <= 2024:
                        citations_per_year[year] = int(citations) if citations.isdigit() else 0
        except NoSuchElementException:
            print(f"Warning: Tidak ada grafik sitasi untuk {author_name}")
        except Exception as e:
            print(f"Warning: Error saat extract citations per year: {e}")

        publications = []

        while True:
            try:
                show_more_button = driver.find_element(By.ID, 'gsc_bpf_more')
                if show_more_button.get_attribute('disabled'):
                    break
                show_more_button.click()
                time.sleep(random.uniform(2, 3))
            except NoSuchElementException:
                break

        try:
            WebDriverWait(driver, 10).until(
                EC.presence_of_all_elements_located((By.CSS_SELECTOR, '#gsc_a_b .gsc_a_tr'))
            )
        except TimeoutException:
            print("Tidak ada publikasi ditemukan.")
        else:
            pub_items = driver.find_elements(By.CSS_SELECTOR, '#gsc_a_b .gsc_a_tr')

            for item in pub_items:
                try:
                    title_element = item.find_element(By.CSS_SELECTOR, '.gsc_a_t a')
                    title = title_element.text
                    pub_link = title_element.get_attribute('href')
                    pub_details = get_publication_details_selenium(driver, pub_link)

                    authors = item.find_element(By.CSS_SELECTOR, '.gs_gray:nth-of-type(1)').text
                    venue_fallback = item.find_element(By.CSS_SELECTOR, '.gs_gray:nth-of-type(2)').text
                    citations = item.find_element(By.CSS_SELECTOR, '.gsc_a_c a').text or "0"
                    year = item.find_element(By.CSS_SELECTOR, '.gsc_a_y span').text or "N/A"

                    pub_citations_per_year = get_publication_citations_per_year_selenium(driver, pub_link)

                    pub_data = {
                        'title': title,
                        'authors': pub_details['authors'] or authors,
                        'journal': pub_details['journal'],
                        'conference': pub_details['conference'],
                        'publisher': pub_details['publisher'],
                        'year': year,
                        'citations': citations,
                        'link': pub_link,
                        'citations_per_year': pub_citations_per_year,
                        'Author': author_name,
                        'volume': pub_details['volume'],
                        'issue': pub_details['issue'],
                        'pages': pub_details['pages']
                    }

                    publications.append(pub_data)
                    time.sleep(random.uniform(1, 2))
                except Exception as e:
                    print(f"Error saat ekstrak publikasi: {str(e)}")

        return {
            'name': name,
            'affiliation': affiliation,
            'profile_url': profile_url,
            'scholar_id': scholar_id,
            'citation_stats': citation_data,
            'citations_per_year': citations_per_year,
            'publications': publications
        }

    except Exception as e:
        print(f"Error saat scraping profil {author_name}: {str(e)}")
        return None

def get_publication_citations_per_year_selenium(driver, pub_url):
    """Extract citations per year for a specific publication using Selenium + BeautifulSoup"""
    original_window = driver.current_window_handle
    new_tab_created = False

    try:
        if not driver or not driver.session_id:
            return {}

        try:
            driver.execute_script("window.open('');")
            new_tab_created = True
            time.sleep(random.uniform(0.5, 1))
            if len(driver.window_handles) < 2:
                return {}
            driver.switch_to.window(driver.window_handles[1])
        except Exception as e:
            print(f"Error saat membuka tab baru: {e}")
            return {}

        try:
            driver.get(pub_url)
            time.sleep(random.uniform(4, 6))
        except Exception as e:
            print(f"Error saat memuat halaman publikasi: {e}")
            return {}

        try:
            WebDriverWait(driver, 25).until(
                EC.presence_of_element_located((By.CSS_SELECTOR, '.gsc_oci_main, .gs_scl'))
            )
        except TimeoutException:
            print(f"Timeout waiting for main content at {pub_url}")

        driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
        time.sleep(1.5)
        driver.execute_script("window.scrollTo(0, 0);")
        time.sleep(1.5)

        page_source = driver.page_source
        soup = BeautifulSoup(page_source, 'html.parser')

        citations_per_year = {}
        year_elements = soup.select('.gsc_oci_g_t')
        citation_elements = soup.select('.gsc_oci_g_a')

        for year_element in year_elements:
            year = year_element.text.strip()
            if year.isdigit() and 2010 <= int(year) <= 2024:
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

            if closest_year and closest_year.isdigit() and 2010 <= int(closest_year) <= 2024:
                citation_value_element = citation_element.select_one('.gsc_oci_g_al')
                if citation_value_element:
                    citation_value = citation_value_element.text.strip()
                    if citation_value.isdigit():
                        citations_per_year[closest_year] = int(citation_value)

        if not citations_per_year:
            citation_spans = soup.select('.gsc_oci_g_al')
            for span in citation_spans:
                parent = span.parent
                if parent and parent.name == 'a':
                    style = parent.get('style', '')
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
                    if closest_year and closest_year.isdigit() and 2010 <= int(closest_year) <= 2024:
                        citation_value = span.text.strip()
                        if citation_value.isdigit():
                            citations_per_year[closest_year] = int(citation_value)

        return citations_per_year

    except Exception as e:
        print(f"Error retrieving citations per year for publication {pub_url}: {str(e)}")
        return {}

    finally:
        if new_tab_created:
            try:
                if driver and hasattr(driver, 'session_id') and driver.session_id:
                    current_handles = driver.window_handles
                    if len(current_handles) > 1:
                        current_window = driver.current_window_handle
                        if current_window != original_window and current_window in current_handles:
                            driver.close()
                            time.sleep(0.5)
                        if original_window in driver.window_handles:
                            driver.switch_to.window(original_window)
                            time.sleep(0.5)
            except Exception as e:
                print(f"Error in finally block (citations): {e}")
                try:
                    if driver and hasattr(driver, 'window_handles'):
                        handles = driver.window_handles
                        if handles:
                            driver.switch_to.window(handles[0])
                except:
                    pass

def get_publication_details_selenium(driver, pub_url):
    """Extract detailed publication information from publication page using Selenium + BeautifulSoup"""
    original_window = driver.current_window_handle
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
        if not driver or not driver.session_id:
            return details

        try:
            driver.execute_script("window.open('');")
            new_tab_created = True
            time.sleep(random.uniform(0.5, 1))
            if len(driver.window_handles) < 2:
                return details
            driver.switch_to.window(driver.window_handles[1])
        except Exception as e:
            print(f"Error saat membuka tab baru: {e}")
            return details

        try:
            driver.get(pub_url)
            time.sleep(random.uniform(4, 6))
        except Exception as e:
            print(f"Error saat memuat halaman publikasi: {e}")
            return details

        try:
            WebDriverWait(driver, 25).until(
                EC.presence_of_element_located((By.CSS_SELECTOR, '.gsc_oci_main, .gs_scl'))
            )
        except TimeoutException:
            print(f"Timeout waiting for main content at {pub_url}")

        driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
        time.sleep(1.5)
        driver.execute_script("window.scrollTo(0, 0);")
        time.sleep(1.5)

        page_source = driver.page_source
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
                if driver and hasattr(driver, 'session_id') and driver.session_id:
                    current_handles = driver.window_handles
                    if len(current_handles) > 1:
                        current_window = driver.current_window_handle
                        if current_window != original_window and current_window in current_handles:
                            driver.close()
                            time.sleep(0.5)
                        if original_window in driver.window_handles:
                            driver.switch_to.window(original_window)
                            time.sleep(0.5)
            except Exception as e:
                print(f"Error in finally block (details): {e}")
                try:
                    if driver and hasattr(driver, 'window_handles'):
                        handles = driver.window_handles
                        if handles:
                            driver.switch_to.window(handles[0])
                except:
                    pass

def classify_publication_type(journal, conference, publisher, title=""):
    if journal and journal.strip() and journal != 'N/A':
        return 'artikel'
    if conference and conference.strip() and conference != 'N/A':
        return 'prosiding'
    return classify_by_regex(publisher, title)

def classify_by_regex(publisher, title=""):
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
    if any(keyword in combined_text for keyword in ['jurnal', 'journal', 'jou.', 'j.', 'acta']):
        return 'artikel'
    if any(keyword in combined_text for keyword in ['prosiding', 'proceedings', 'proc.', 'konferensi', 'conference',
                                                    'conf.', 'simposium', 'symposium', 'workshop', 'pertemuan', 'meeting']):
        return 'prosiding'
    if any(keyword in combined_text for keyword in ['buku', 'book', 'bab buku', 'chapter', 'handbook', 'ensiklopedia',
                                                    'encyclopedia', 'buku teks', 'textbook', 'penerbit', 'publisher', 'press', 'books']):
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
    if re.search(r'\bUU\s*No\.\s*\d+|Undang-undang\s*Nomor\s*\d+|Peraturan\s*(Pemerintah|Presiden)\s*No\.\s*\d+', combined_text):
        return 'buku'
    if re.search(r'vol\.|\bvol\b|\bedisi\b|\bno\.|\bhal\.|\bhalaman\b', combined_text) or \
       re.search(r'\bvol\.\s*\d+\s*(\(\s*\d+\s*\))?', combined_text) or \
       re.search(r'\d+\s*\(\d+\)', combined_text):
        return 'artikel'
    return 'lainnya'

def extract_vol_no(venue_text, title=""):
    """Extract volume and issue information"""
    def clean_text(text):
        if not isinstance(text, str):
            return ""
        return re.sub(r'\s+', ' ', text.strip())

    def convert_roman(roman_str):
        roman_str = roman_str.upper()
        valid_chars = {'I', 'V', 'X', 'L', 'C', 'D', 'M'}
        if not all(c in valid_chars for c in roman_str):
            return None
        try:
            return str(fromRoman(roman_str))
        except:
            return None

    search_text = clean_text(venue_text)
    title_text = clean_text(title)
    combined_text = f"{search_text} {title_text}".lower()

    legal_patterns = [
        r'\bUU\s*No\.?\s*\d+',
        r'\bUndang-undang\s*Nomor\s*\d+',
        r'\bPeraturan\s*(Pemerintah|Presiden|Menteri|Daerah)\s*No\.?\s*\d+',
        r'\bLaw\s*No\.?\s*\d+',
        r'\bAct\s*No\.?\s*\d+',
        r'\bPerda\s*No\.?\s*\d+'
    ]

    if any(re.search(pattern, combined_text, re.IGNORECASE) for pattern in legal_patterns):
        return "", ""

    journal_format = re.search(r'(\d+)\s*\(\s*(\d+)\s*\)', search_text)
    if journal_format:
        return journal_format.group(1), journal_format.group(2)

    if re.search(r'\b\d+\s*-\s*\d+\b', search_text):
        return "", ""

    year_pattern = r'(?:19|20)\d{2}'

    def extract_standard_format(text):
        vol_no = re.search(
            r'(?<!\S)[Vv]ol(?:ume)?\.?\s*(\d+|[IVXLCDMivxlcdm]+).*?[Nn]o(?:mber)?\.?\s*(\d+)',
            text
        )
        if vol_no:
            vol = vol_no.group(1)
            no = vol_no.group(2)
            if vol.isalpha():
                vol = convert_roman(vol) or ""
            return vol, no
        vol_num = re.search(r'(?<!\S)volume\s*(\d+).*?number\s*(\d+)', text, re.IGNORECASE)
        if vol_num:
            return vol_num.group(1), vol_num.group(2)
        return None, None

    vol, no = extract_standard_format(search_text)
    if vol or no:
        return vol, no
    if title_text:
        vol, no = extract_standard_format(title_text)
        if vol or no:
            return vol, no

    def find_isolated_numbers(text):
        numbers = [n for n in re.findall(r'\b\d+\b', text)
                   if not re.match(year_pattern, n) and int(n) < 1000]
        if len(numbers) >= 2:
            return numbers[0], numbers[1]
        elif numbers:
            return "", numbers[0]
        return "", ""

    vol, no = find_isolated_numbers(search_text)
    if no:
        return vol, no
    if title_text:
        vol, no = find_isolated_numbers(title_text)
        if no:
            return vol, no

    return "", ""

def extract_pages(venue_text, title=""):
    """Ekstrak informasi halaman (pages) dari venue atau title"""
    if not isinstance(venue_text, str) and not isinstance(title, str):
        return ""

    venue_text = re.sub(r'\s+', ' ', str(venue_text).strip().lower())
    title_text = re.sub(r'\s+', ' ', str(title).strip().lower())
    combined_text = f"{venue_text} {title_text}"

    pages_pattern1 = re.search(r'(?:pp\.?|pages?|halaman)\s*(\d+)\s*[-–—]\s*(\d+)', combined_text, re.IGNORECASE)
    if pages_pattern1:
        return f"{pages_pattern1.group(1)}-{pages_pattern1.group(2)}"

    pages_pattern2 = re.search(r'(?:p\.?|page|halaman)\s*(\d+)(?:\s|$|,|\.)', combined_text, re.IGNORECASE)
    if pages_pattern2:
        return pages_pattern2.group(1)

    pages_pattern3 = re.search(r'[^\d]+(\d+)\s*[-–—]\s*(\d+)\s*$', venue_text)
    if pages_pattern3:
        start_page = int(pages_pattern3.group(1))
        end_page = int(pages_pattern3.group(2))
        if end_page > start_page and start_page > 0 and end_page < 2000:
            return f"{start_page}-{end_page}"

    pages_pattern4 = re.search(r'\((\d+)\s*[-–—]\s*(\d+)\)', combined_text)
    if pages_pattern4:
        start_page = int(pages_pattern4.group(1))
        end_page = int(pages_pattern4.group(2))
        if end_page > start_page and start_page > 0 and end_page < 2000:
            return f"{start_page}-{end_page}"

    return ""

def transform_publications_data(all_publications):
    """Transform publications data menggunakan klasifikasi yang benar"""
    transformed_data = []

    for pub in all_publications:
        base_data = {
            'judul': pub.get('title', ''),
            'author': pub.get('authors', ''),
            'tahun_publikasi': pub.get('year', 'N/A'),
            'journal': pub.get('journal', 'N/A'),
            'conference': pub.get('conference', 'N/A'),
            'publisher': pub.get('publisher', ''),
            'publication_type': classify_publication_type(
                pub.get('journal', 'N/A'),
                pub.get('conference', 'N/A'),
                pub.get('publisher', ''),
                pub.get('title', '')
            ),
            'volume': pub.get('volume', ''),
            'issue': pub.get('issue', ''),
            'pages': pub.get('pages', ''),
            'total_sitasi_seluruhnya': pub.get('citations', 0),
            'Publication URL': pub.get('link', ''),
            'sumber': 'Google Scholar'
        }

        if not base_data['volume'] or not base_data['issue']:
            source_text = pub.get('journal', '') if pub.get('journal', 'N/A') != 'N/A' else pub.get('conference', '')
            vol, no = extract_vol_no(source_text, pub.get('title', ''))
            if not base_data['volume']:
                base_data['volume'] = vol
            if not base_data['issue']:
                base_data['issue'] = no

        if not base_data['pages']:
            source_text = pub.get('journal', '') if pub.get('journal', 'N/A') != 'N/A' else pub.get('conference', '')
            base_data['pages'] = extract_pages(source_text, pub.get('title', ''))

        citations_per_year = pub.get('citations_per_year', {})

        if not citations_per_year:
            transformed_data.append({
                **base_data,
                'tahun': pub.get('year', 'N/A'),
                'total_sitasi_tahun': '',
                'tanggal_unduh': datetime.datetime.now().strftime('%Y-%m-%d')
            })
        else:
            for year, citations in citations_per_year.items():
                transformed_data.append({
                    **base_data,
                    'tahun': year,
                    'total_sitasi_tahun': citations,
                    'tanggal_unduh': datetime.datetime.now().strftime('%Y-%m-%d')
                })

    return transformed_data

def save_to_csv(all_profiles, all_publications, filename):
    current_date = datetime.datetime.now().strftime('%Y-%m-%d')

    author_pub_counts = {}
    for pub in all_publications:
        author = pub['Author']
        author_pub_counts[author] = author_pub_counts.get(author, 0) + 1

    for profile in all_profiles:
        profile['Total_Publikasi'] = author_pub_counts.get(profile['Name'], 0)
        profile['Tanggal_Unduh'] = current_date

    profiles_df = pd.DataFrame(all_profiles)

    if 'citations_per_year' in profiles_df.columns:
        citations_per_year_df = pd.json_normalize(profiles_df['citations_per_year'])
        citations_per_year_df.columns = [f"Citations_{year}" for year in citations_per_year_df.columns]
        profiles_df = pd.concat([profiles_df.drop(columns=['citations_per_year']), citations_per_year_df], axis=1)

    profiles_df.to_csv(f"{filename}_profiles.csv", index=False, encoding='utf-8')

    transformed_publications = transform_publications_data(all_publications)
    publications_df = pd.DataFrame(transformed_publications)
    publications_df.to_csv(f"{filename}_publications.csv", index=False, encoding='utf-8')

    return current_date, profiles_df, publications_df

def connect_to_db():
    """Establish connection to PostgreSQL database"""
    try:
        conn = psycopg2.connect(**DB_PARAMS)
        print("Connected to database successfully!")
        return conn
    except Exception as e:
        print(f"Error connecting to database: {e}")
        return None

def get_authors_from_db(conn, scrape_from_beginning=False):
    cursor = None
    try:
        cursor = conn.cursor()

        if scrape_from_beginning:
            query = """
                SELECT v_nama, v_link, COALESCE(v_status, 'pending') as status
                FROM temp_dosenGS_scraping
                WHERE v_link IS NOT NULL
                ORDER BY v_nama
            """
            cursor.execute(query)
            results = cursor.fetchall()
            df = pd.DataFrame(results, columns=['Name', 'Profile URL', 'Status'])
            print(f"Berhasil mengambil {len(df)} author (SEMUA STATUS) dari database.")
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
            print(f"Berhasil mengambil {len(df)} author yang belum selesai dari database.")

        return df

    except Exception as e:
        print(f"Error saat mengambil data author dari database: {e}")
        return pd.DataFrame()
    finally:
        if cursor:
            cursor.close()

def get_scraping_statistics(conn):
    cursor = None
    try:
        cursor = conn.cursor()
        query = """
            SELECT
                COUNT(*) as total,
                SUM(CASE WHEN v_status = 'completed' THEN 1 ELSE 0 END) as completed,
                SUM(CASE WHEN v_status = 'error' THEN 1 ELSE 0 END) as error,
                SUM(CASE WHEN v_status = 'processing' THEN 1 ELSE 0 END) as processing,
                SUM(CASE WHEN v_status IS NULL OR v_status = 'pending' THEN 1 ELSE 0 END) as pending
            FROM temp_dosenGS_scraping
            WHERE v_link IS NOT NULL
        """
        cursor.execute(query)
        result = cursor.fetchone()
        return {
            'total': result[0] if result else 0,
            'completed': result[1] if result else 0,
            'error': result[2] if result else 0,
            'processing': result[3] if result else 0,
            'pending': result[4] if result else 0
        }
    except Exception as e:
        print(f"Error saat mengambil statistik scraping: {e}")
        return {'total': 0, 'completed': 0, 'error': 0, 'processing': 0, 'pending': 0}
    finally:
        if cursor:
            cursor.close()

def reset_all_status_to_pending(conn):
    cursor = None
    try:
        cursor = conn.cursor()
        query = """
            UPDATE temp_dosenGS_scraping
            SET v_status = 'pending', v_error_message = NULL, t_last_updated = NOW()
            WHERE v_link IS NOT NULL
        """
        cursor.execute(query)
        affected_rows = cursor.rowcount
        conn.commit()
        print(f"✓ Berhasil reset {affected_rows} dosen ke status 'pending'")
        return True
    except Exception as e:
        conn.rollback()
        print(f"✗ Error saat reset status: {e}")
        return False
    finally:
        if cursor:
            cursor.close()

def update_scraping_status(conn, author_name, status, error_message=None):
    cursor = None
    try:
        cursor = conn.cursor()
        if status == 'error' and error_message:
            query = """
                UPDATE temp_dosenGS_scraping
                SET v_status = %s, v_error_message = %s, t_last_updated = NOW()
                WHERE v_nama = %s
            """
            cursor.execute(query, (status, error_message, author_name))
        else:
            query = """
                UPDATE temp_dosenGS_scraping
                SET v_status = %s, t_last_updated = NOW()
                WHERE v_nama = %s
            """
            cursor.execute(query, (status, author_name))
        conn.commit()
        print(f"Status untuk {author_name} diupdate menjadi: {status}")
    except Exception as e:
        conn.rollback()
        print(f"Error saat update status untuk {author_name}: {e}")
    finally:
        if cursor:
            cursor.close()

def import_dosen_data(conn, profiles_df):
    """Import dosen data from profiles to database - SELALU INSERT BARU"""
    cursor = conn.cursor()
    dosen_ids = {}
    try:
        for _, row in profiles_df.iterrows():
            try:
                insert_query = sql.SQL("""
                    INSERT INTO tmp_dosen_dt
                    (v_nama_dosen, v_id_googlescholar, n_total_publikasi,
                     n_total_sitasi_gs, n_total_sitasi_gs2020, n_h_index_gs, n_h_index_gs2020,
                     n_i10_index_gs, n_i10_index_gs2020, v_sumber, v_link_url, t_tanggal_unduh)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                    RETURNING v_id_dosen
                """)
                values = (
                    row['Name'],
                    row['ID Google Scholar'],
                    int(row['Total_Publikasi']) if pd.notna(row['Total_Publikasi']) else 0,
                    int(row['Citations_all']) if pd.notna(row['Citations_all']) else 0,
                    int(row['Citations_since2020']) if pd.notna(row['Citations_since2020']) else 0,
                    int(row['h-index_all']) if pd.notna(row['h-index_all']) else 0,
                    int(row['h-index_since2020']) if pd.notna(row['h-index_since2020']) else 0,
                    int(row['i10-index_all']) if pd.notna(row['i10-index_all']) else 0,
                    int(row['i10-index_since2020']) if pd.notna(row['i10-index_since2020']) else 0,
                    'Google Scholar',
                    row['Profile URL'],
                    datetime.datetime.now().date()
                )
                cursor.execute(insert_query, values)
                new_dosen_id = cursor.fetchone()[0]
                dosen_ids[row['Name']] = row['ID Google Scholar']
                print(f"  ✓ Inserted new record for {row['Name']} with ID: {new_dosen_id}")
            except Exception as e:
                print(f"  Warning: Gagal insert profil {row.get('Name', 'Unknown')}: {e}")
                conn.rollback()
                continue
        conn.commit()
        print(f"✓ Berhasil memasukkan {len(dosen_ids)} data profil BARU ke tmp_dosen_dt")
        return dosen_ids
    except Exception as e:
        print(f"✗ Error saat insert profile data: {e}")
        conn.rollback()
        return {}
    finally:
        cursor.close()

def normalize_publication_type(pub_type):
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

def import_publications_data(conn, publications_df, dosen_ids):
    """Import publications data to database"""
    cursor = conn.cursor()
    try:
        inserted_count = 0

        for index, row in publications_df.iterrows():
            try:
                pub_type_raw = row.get('publication_type', 'lainnya')
                pub_type = normalize_publication_type(pub_type_raw)

                insert_pub_query = sql.SQL("""
                    INSERT INTO stg_publikasi_tr
                    (v_judul, v_jenis, v_tahun_publikasi, n_total_sitasi, v_sumber,
                     v_link_url, v_authors, v_publisher, t_tanggal_unduh)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                    RETURNING v_id_publikasi
                """)

                tahun = int(row['tahun_publikasi']) if pd.notna(row['tahun_publikasi']) and str(row['tahun_publikasi']).isdigit() else None
                total_sitasi = int(row['total_sitasi_seluruhnya']) if pd.notna(row['total_sitasi_seluruhnya']) and str(row['total_sitasi_seluruhnya']).isdigit() else 0

                pub_values = (
                    row.get('judul', ''),
                    pub_type,
                    tahun,
                    total_sitasi,
                    row.get('sumber', 'Google Scholar'),
                    row.get('Publication URL', ''),
                    row.get('author', ''),
                    row.get('publisher', ''),
                    datetime.datetime.now()
                )

                cursor.execute(insert_pub_query, pub_values)
                pub_id = cursor.fetchone()[0]

                if pub_type == "artikel":
                    _insert_artikel_data(cursor, pub_id, row)
                elif pub_type == "prosiding":
                    _insert_prosiding_data(cursor, pub_id, row)
                elif pub_type == "buku":
                    _insert_buku_data(cursor, pub_id, row)
                elif pub_type == "penelitian":
                    _insert_penelitian_data(cursor, pub_id, row)
                else:
                    _insert_lainnya_data(cursor, pub_id, row)

                if pd.notna(row.get('tahun')) and pd.notna(row.get('total_sitasi_tahun')):
                    tahun_str = str(row.get('tahun', '')).strip()
                    sitasi_str = str(row.get('total_sitasi_tahun', '')).strip()
                    if tahun_str.isdigit() and sitasi_str.replace('-', '').isdigit():
                        _insert_sitasi_tahunan(cursor, pub_id, row)

                author_name = row.get('Author', '')
                if author_name and author_name in dosen_ids:
                    check_link = sql.SQL("""
                        SELECT 1 FROM stg_publikasi_dosen_dt
                        WHERE v_id_publikasi = %s AND v_id_dosen =
                        (SELECT v_id_dosen FROM tmp_dosen_dt WHERE v_id_googlescholar = %s)
                    """)
                    cursor.execute(check_link, (pub_id, dosen_ids[author_name]))

                    if not cursor.fetchone():
                        link_query = sql.SQL("""
                            INSERT INTO stg_publikasi_dosen_dt (v_id_publikasi, v_id_dosen, v_author_order)
                            SELECT %s, v_id_dosen, %s FROM tmp_dosen_dt
                            WHERE v_id_googlescholar = %s
                        """)
                        cursor.execute(link_query, (pub_id, "1", dosen_ids[author_name]))

                inserted_count += 1

            except Exception as e:
                print(f"  Warning: Gagal insert publikasi '{row.get('judul', 'Unknown')[:50]}...': {e}")
                conn.rollback()
                continue

        conn.commit()
        print(f"✓ Berhasil memasukkan {inserted_count} data publikasi ke database")
        return inserted_count

    except Exception as e:
        print(f"✗ Error saat insert publication data: {e}")
        conn.rollback()
        return 0
    finally:
        cursor.close()

def _insert_artikel_data(cursor, pub_id, row):
    try:
        journal_name = row.get('journal', '')
        if not journal_name or journal_name == 'N/A':
            return
        check_journal_query = sql.SQL("SELECT v_id_jurnal FROM stg_jurnal_mt WHERE v_nama_jurnal = %s")
        cursor.execute(check_journal_query, (journal_name,))
        result = cursor.fetchone()
        if result:
            journal_id = result[0]
        else:
            insert_journal_query = sql.SQL("INSERT INTO stg_jurnal_mt (v_nama_jurnal) VALUES (%s) RETURNING v_id_jurnal")
            cursor.execute(insert_journal_query, (journal_name,))
            journal_id = cursor.fetchone()[0]
        insert_artikel_query = sql.SQL("""
            INSERT INTO stg_artikel_dr (v_id_publikasi, v_id_jurnal, v_volume, v_issue, v_pages, t_updated_at)
            VALUES (%s, %s, %s, %s, %s, %s)
        """)
        cursor.execute(insert_artikel_query, (pub_id, journal_id, row.get('volume', ''), row.get('issue', ''), row.get('pages', ''), datetime.datetime.now()))
    except Exception as e:
        print(f"    Error insert artikel data: {e}")

def _insert_prosiding_data(cursor, pub_id, row):
    try:
        insert_query = sql.SQL("""
            INSERT INTO stg_prosiding_dr (v_id_publikasi, v_nama_konferensi, f_terindeks_scopus, t_updated_at)
            VALUES (%s, %s, %s, %s)
        """)
        cursor.execute(insert_query, (pub_id, row.get('conference', ''), False, datetime.datetime.now()))
    except Exception as e:
        print(f"    Error insert prosiding data: {e}")

def _insert_buku_data(cursor, pub_id, row):
    try:
        insert_query = sql.SQL("INSERT INTO stg_buku_dr (v_id_publikasi, v_isbn, t_updated_at) VALUES (%s, %s, %s)")
        cursor.execute(insert_query, (pub_id, '', datetime.datetime.now()))
    except Exception as e:
        print(f"    Error insert buku data: {e}")

def _insert_penelitian_data(cursor, pub_id, row):
    try:
        pub_type_raw = str(row.get('publication_type', '')).lower()
        if 'tesis' in pub_type_raw:
            kategori = 'Tesis'
        elif 'disertasi' in pub_type_raw:
            kategori = 'Disertasi'
        else:
            kategori = 'Penelitian'
        insert_query = sql.SQL("""
            INSERT INTO stg_penelitian_dr (v_id_publikasi, v_kategori_penelitian, t_updated_at)
            VALUES (%s, %s, %s)
        """)
        cursor.execute(insert_query, (pub_id, kategori, datetime.datetime.now()))
    except Exception as e:
        print(f"    Error insert penelitian data: {e}")

def _insert_lainnya_data(cursor, pub_id, row):
    try:
        insert_query = sql.SQL("INSERT INTO stg_lainnya_dr (v_id_publikasi, v_keterangan, t_updated_at) VALUES (%s, %s, %s)")
        cursor.execute(insert_query, (pub_id, None, datetime.datetime.now()))
    except Exception as e:
        print(f"    Error insert lainnya data: {e}")

def _insert_sitasi_tahunan(cursor, pub_id, row):
    try:
        tahun_raw = row.get('tahun', '')
        sitasi_raw = row.get('total_sitasi_tahun', '')
        if pd.notna(tahun_raw) and pd.notna(sitasi_raw):
            tahun_str = str(tahun_raw).strip()
            sitasi_str = str(sitasi_raw).strip()
            if tahun_str.isdigit():
                tahun = int(tahun_str)
                sitasi = int(sitasi_str) if sitasi_str.replace('-', '').isdigit() else 0
                if 2000 <= tahun <= 2030:
                    insert_query = sql.SQL("""
                        INSERT INTO stg_publikasi_sitasi_tahunan_dr
                        (v_id_publikasi, v_tahun, n_total_sitasi_tahun, v_sumber, t_tanggal_unduh)
                        VALUES (%s, %s, %s, %s, %s)
                    """)
                    cursor.execute(insert_query, (pub_id, tahun, sitasi, 'Google Scholar', datetime.datetime.now().date()))
    except Exception as e:
        print(f"    Error insert sitasi tahunan: {e}")

def main():
    global restart_count, failed_accounts
    conn = None
    driver = None
    try:
        conn = connect_to_db()
        if not conn:
            print("Gagal terhubung ke database. Program akan berhenti.")
            return

        stats = get_scraping_statistics(conn)
        print("\n" + "="*60)
        print("STATISTIK SCRAPING")
        print("="*60)
        print(f"Total Dosen        : {stats['total']}")
        print(f"Sudah Selesai      : {stats['completed']}")
        print(f"Processing (stuck) : {stats['processing']}")
        print(f"Error              : {stats['error']}")
        print(f"Belum Di-scrape    : {stats['pending']}")
        print("="*60 + "\n")

        print("Pilihan Mode Scraping:")
        print("1. Lanjutkan scraping (hanya dosen yang belum selesai)")
        print("2. Scraping dari awal (reset semua status)")

        while True:
            scrape_mode = input("\nPilih mode (1/2): ").strip()
            if scrape_mode in ['1', '2']:
                break
            else:
                print("Error: Pilih 1 atau 2")

        scrape_from_beginning = (scrape_mode == '2')

        if scrape_from_beginning:
            confirm = input("Apakah Anda yakin ingin scraping dari awal? (yes/no): ").strip().lower()
            if confirm not in ['yes', 'y']:
                scrape_from_beginning = False

        df = get_authors_from_db(conn, scrape_from_beginning)
        if df.empty:
            print("Tidak ada data. Program akan berhenti.")
            return

        while True:
            try:
                max_authors_str = input(f"Masukkan jumlah maksimum author (tersisa: {len(df)}): ")
                max_authors = int(max_authors_str)
                if max_authors > 0:
                    break
            except ValueError:
                print("Error: Input tidak valid.")

        max_authors = min(max_authors, len(df))

        profiles_csv_path = 'all_dosen_data_profiles.csv'
        publications_csv_path = 'all_dosen_data_publications.csv'

        if not os.path.exists(profiles_csv_path):
            pd.DataFrame().to_csv(profiles_csv_path, index=False)
        if not os.path.exists(publications_csv_path):
            pd.DataFrame().to_csv(publications_csv_path, index=False)

        final_profiles_df = pd.DataFrame()
        final_publications_df = pd.DataFrame()

        print("\n" + "="*60)
        print("PROSES AUTO-LOGIN DENGAN ACCOUNT ROTATION")
        print("="*60)

        restart_count = 0
        failed_accounts = set()

        driver = setup_driver_with_auto_login()

        if driver is None:
            print("✗ Gagal membuat driver dengan auto-login. Program berhenti.")
            return

        print("="*60 + "\n")

        try:
            scraping_count = 0
            for index, row in df.head(max_authors).iterrows():
                author_name = row['Name']
                profile_url = row['Profile URL']

                print(f"\n{'='*60}")
                print(f"Scraping ({scraping_count + 1}/{max_authors}): {author_name}")
                print(f"{'='*60}")

                update_scraping_status(conn, author_name, 'processing')

                try:
                    profile_data = scrape_google_scholar_profile_with_existing_driver(driver, profile_url, author_name)

                    if profile_data and profile_data['publications']:
                        print(f"✓ Berhasil mengambil data untuk {profile_data['name']}")

                        profile_entry = {
                            'Name': profile_data['name'],
                            'Affiliation': profile_data['affiliation'],
                            'Profile URL': profile_data['profile_url'],
                            'ID Google Scholar': profile_data['scholar_id'],
                            'Citations_all': profile_data['citation_stats'].get('Citations_all', '0'),
                            'Citations_since2020': profile_data['citation_stats'].get('Citations_since2020', '0'),
                            'h-index_all': profile_data['citation_stats'].get('h-index_all', '0'),
                            'h-index_since2020': profile_data['citation_stats'].get('h-index_since2020', '0'),
                            'i10-index_all': profile_data['citation_stats'].get('i10-index_all', '0'),
                            'i10-index_since2020': profile_data['citation_stats'].get('i10-index_since2020', '0'),
                            'Total_Publikasi': len(profile_data['publications']),
                            'Tanggal_Unduh': datetime.datetime.now().strftime('%Y-%m-%d')
                        }

                        current_profile_df = pd.DataFrame([profile_entry])

                        if 'citations_per_year' in profile_data and profile_data['citations_per_year']:
                            citations_per_year_df = pd.json_normalize(profile_data['citations_per_year'])
                            citations_per_year_df.columns = [f"Citations_{year}" for year in citations_per_year_df.columns]
                            current_profile_df = pd.concat([current_profile_df.reset_index(drop=True), citations_per_year_df], axis=1)

                        header_needed = not os.path.getsize(profiles_csv_path) > 0
                        current_profile_df.to_csv(profiles_csv_path, mode='a', header=header_needed, index=False, encoding='utf-8')

                        transformed_publications = transform_publications_data(profile_data['publications'])
                        current_publications_df = pd.DataFrame(transformed_publications)

                        header_needed = not os.path.getsize(publications_csv_path) > 0
                        current_publications_df.to_csv(publications_csv_path, mode='a', header=header_needed, index=False, encoding='utf-8')

                        final_profiles_df = pd.concat([final_profiles_df, current_profile_df], ignore_index=True)
                        final_publications_df = pd.concat([final_publications_df, current_publications_df], ignore_index=True)

                        update_scraping_status(conn, author_name, 'completed')
                        scraping_count += 1

                    else:
                        error_msg = "Tidak ada publikasi ditemukan"
                        print(f"✗ {error_msg} untuk {author_name}")
                        update_scraping_status(conn, author_name, 'error', error_msg)

                except Exception as e:
                    error_msg = f"Error scraping: {str(e)}"
                    print(f"✗ {error_msg}")
                    update_scraping_status(conn, author_name, 'error', error_msg)

                if scraping_count < max_authors:
                    delay_time = random.uniform(60, 120)
                    print(f"\n⏳ Menunggu {delay_time:.1f} detik sebelum lanjut...")
                    time.sleep(delay_time)

        finally:
            # ======================================================
            # FIX 4: Cleanup driver dan user-data-dir
            # ======================================================
            if driver is not None:
                try:
                    driver.quit()
                    print("\n✓ Driver berhasil ditutup")
                except Exception as e:
                    print(f"✗ Error saat menutup driver: {e}")
            cleanup_user_data_dir()

        if final_profiles_df.empty:
            print("\n✗ Tidak ada data yang berhasil di-scrape.")
            return

        print(f"\n{'='*60}")
        print("PROSES SCRAPING SELESAI")
        print(f"{'='*60}")
        print(f"Total berhasil di-scrape: {len(final_profiles_df)} dosen")
        print(f"Total publikasi: {len(final_publications_df)}")

        if not conn:
            conn = connect_to_db()
        if conn:
            try:
                print("\n" + "="*60)
                print("PROSES IMPOR DATA KE DATABASE")
                print("="*60)
                dosen_ids = import_dosen_data(conn, final_profiles_df)
                import_publications_data(conn, final_publications_df, dosen_ids)
                print("✓ Proses impor data ke database berhasil!")
            except Exception as e:
                print(f"✗ Error saat proses impor ke database: {e}")
                import traceback
                traceback.print_exc()

        final_stats = get_scraping_statistics(conn)
        print(f"\n{'='*60}")
        print("STATISTIK SCRAPING TERBARU")
        print(f"{'='*60}")
        print(f"Total Dosen    : {final_stats['total']}")
        print(f"Sudah Selesai  : {final_stats['completed']}")
        print(f"Error          : {final_stats['error']}")
        print(f"Pending        : {final_stats['pending']}")

    except Exception as e:
        print(f"✗ Terjadi error pada fungsi utama: {e}")
        import traceback
        traceback.print_exc()
    finally:
        if driver is not None:
            try:
                driver.quit()
            except:
                pass
        cleanup_user_data_dir()
        if conn:
            conn.close()
            print("✓ Koneksi database telah ditutup.")

if __name__ == "__main__":
    main()