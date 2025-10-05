#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Combined Google Scholar Scraper with PostgreSQL Database Import
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
from webdriver_manager.chrome import ChromeDriverManager
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

# Database connection parameters - update these with your PostgreSQL credentials
DB_PARAMS = {
    'dbname': 'SKM_PUBLIKASI',  # Adjust this to your actual database name
    'user': 'rayhanadjisantoso',         # Update with your username
    'password': 'rayhan123',             # Update with your password
    'host': 'localhost',
    'port': '5432'
}

# ... (Semua fungsi dari setup_driver() hingga import_publications_data() tetap sama) ...
# ... (Untuk keringkasan, fungsi-fungsi ini tidak ditampilkan, tetapi tetap ada di file Anda)
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
    
    # Menambahkan prefs untuk menghindari notifikasi dan menghemat resource
    prefs = {
        "profile.default_content_setting_values.notifications": 2,
        "profile.default_content_settings.popups": 0,
        "profile.managed_default_content_settings.images": 2,
        "profile.default_content_setting_values.cookies": 1,
        "profile.cookie_controls_mode": 0,
        "profile.block_third_party_cookies": False
    }
    chrome_options.add_experimental_option("prefs", prefs)
    
    # Gunakan ChromeDriverManager untuk mendapatkan driver yang sesuai
    try:
        service = Service(ChromeDriverManager().install())
        driver = webdriver.Chrome(service=service, options=chrome_options)
    except Exception as e:
        print(f"Error saat membuat driver: {e}")
        try:
            driver = webdriver.Chrome(options=chrome_options)
        except Exception as e2:
            print(f"Error alternatif saat membuat driver: {e2}")
            raise
    
    # Hapus properti webdriver untuk menghindari deteksi
    try:
        driver.execute_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")
    except Exception as e:
        print(f"Warning: Tidak dapat menyembunyikan webdriver: {e}")
    
    # Set timeouts yang lebih panjang
    driver.set_page_load_timeout(120)
    driver.implicitly_wait(30)
    
    # Tambahkan cookies untuk Google Scholar
    try:
        driver.get("https://scholar.google.com")
        time.sleep(5)
        
        cookies = [
            {'name': 'GSP', 'value': 'ID=1234567890abcdef:CF=4', 'domain': '.google.com'},
            {'name': 'NID', 'value': '511=abcdefghijklmnopqrstuvwxyz1234567890', 'domain': '.google.com'},
            {'name': 'CONSENT', 'value': 'PENDING+999', 'domain': '.google.com'},
            {'name': '1P_JAR', 'value': '2024-01-01-00', 'domain': '.google.com'}
        ]
        
        for cookie in cookies:
            try:
                driver.add_cookie(cookie)
            except Exception as e:
                print(f"Warning: Could not add cookie {cookie['name']}: {e}")
    except Exception as e:
        print(f"Warning: Tidak dapat menambahkan cookies: {e}")
    
    return driver

def setup_driver_with_manual_login():
    """Setup driver dengan login manual untuk menghindari CAPTCHA"""
    driver = setup_driver()
    
    try:
        driver.get("https://scholar.google.com")
        
        print("\n" + "="*50)
        print("SILAKAN LOGIN KE GOOGLE SCHOLAR SECARA MANUAL")
        print("Setelah login berhasil, tekan Enter untuk melanjutkan")
        print("="*50 + "\n")
        
        input("Tekan Enter setelah login selesai...")
        
        print("Memverifikasi login...")
        time.sleep(3)
        
        cookies = driver.get_cookies()
        print(f"Berhasil mendapatkan {len(cookies)} cookies")
        
        return driver
    except Exception as e:
        print(f"Error saat setup driver dengan login manual: {e}")
        try:
            driver.quit()
        except:
            pass
        return None

def scrape_google_scholar_profile_with_existing_driver(driver, profile_url, author_name):
    """Scrape Google Scholar profile using an existing driver (already logged in)"""
    try:
        print(f"Accessing profile for: {author_name}")
        print(f"Profile URL: {profile_url}")
        
        driver.get(profile_url)
        time.sleep(random.uniform(5, 8))
        
        # Ekstrak Google Scholar ID dari profile URL
        scholar_id = ""
        if "user=" in profile_url:
            scholar_id = profile_url.split("user=")[1].split("&")[0]
        
        # Ekstrak informasi profil dengan error handling
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
        
        # Ekstrak statistik sitasi
        citation_stats = driver.find_elements(By.CSS_SELECTOR, '#gsc_rsb_st tbody tr')
        citation_data = {}
        
        for stat in citation_stats:
            metric_name = stat.find_element(By.CSS_SELECTOR, 'td:nth-of-type(1)').text
            all_citations = stat.find_element(By.CSS_SELECTOR, 'td:nth-of-type(2)').text
            recent_citations = stat.find_element(By.CSS_SELECTOR, 'td:nth-of-type(3)').text
            citation_data[f"{metric_name}_all"] = all_citations
            citation_data[f"{metric_name}_since2020"] = recent_citations
        
        # Ekstrak sitasi per tahun untuk profil
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
                        citations_per_year[year] = int(citations)
        except NoSuchElementException:
            pass
        
        # Ekstrak publikasi
        publications = []

        # Klik tombol 'Show more' hingga semua publikasi dimuat
        while True:
            try:
                show_more_button = driver.find_element(By.ID, 'gsc_bpf_more')
                if show_more_button.get_attribute('disabled'):
                    break
                show_more_button.click()
                time.sleep(random.uniform(2, 3))
            except NoSuchElementException:
                break
        
        # Setelah semua publikasi termuat, mulai scraping
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
        
        # Return data profil dengan Profile URL dan Scholar ID
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
        print(f"Error saat scraping profil {author_name}: {str(e)}")
        return None

def get_publication_citations_per_year_selenium(driver, pub_url):
    """Extract citations per year for a specific publication using Selenium + BeautifulSoup"""
    original_window = driver.current_window_handle
    new_tab_created = False
    
    try:
        try:
            driver.execute_script("window.open('');")        
            new_tab_created = True
            
            if len(driver.window_handles) < 2:
                print(f"Tidak dapat membuka tab baru untuk {pub_url}")
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
        
        print(f"Using graph extraction method for {pub_url}")
        
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
        
        driver.close()
        driver.switch_to.window(original_window)
        
        return citations_per_year
        
    except Exception as e:
        print(f"Error retrieving citations per year for publication {pub_url}: {str(e)}")
        return {}
        
    finally:
        if new_tab_created:
            try:
                if driver.session_id:
                    if len(driver.window_handles) > 1:
                        if driver.current_window_handle != original_window:
                            driver.close()
                        if original_window in driver.window_handles:
                            driver.switch_to.window(original_window)
            except Exception as e:
                print(f"Error saat menangani tab browser: {e}")

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
        try:
            driver.execute_script("window.open('');")        
            new_tab_created = True
            
            if len(driver.window_handles) < 2:
                print(f"Tidak dapat membuka tab baru untuk {pub_url}")
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
                if driver.session_id:
                    if len(driver.window_handles) > 1:
                        if driver.current_window_handle != original_window:
                            driver.close()
                        if original_window in driver.window_handles:
                            driver.switch_to.window(original_window)
            except Exception as e:
                print(f"Error saat menangani tab browser: {e}")

def classify_publication_type(journal, conference, publisher, title=""):
    """Klasifikasi jenis publikasi berdasarkan aturan baru"""
    if journal and journal.strip() and journal != 'N/A':
        return "Jurnal"
    
    if conference and conference.strip() and conference != 'N/A':
        return "Prosiding Konferensi"
    
    return classify_by_regex(publisher, title)

def classify_by_regex(publisher, title=""):
    """Klasifikasi menggunakan regex jika journal dan conference tidak tersedia"""
    combined_text = f"{publisher} {title}".lower()
    
    if pd.isna(combined_text) or combined_text.strip() == "":
        return "Lainnya"
    
    book_publishers = ['nuansa aulia', 'citra aditya bakti', 'yrama widya', 
                      'pustaka belajar', 'pustaka pelajar', 'erlangga', 
                      'andpublisher', 'prenadamedia', 'gramedia', 'grasindo',
                      'media', 'prenhalindo', 'prenhallindo', 'wiley', 'springer']
    
    if any(pub in combined_text for pub in book_publishers):
        return "Buku/Bab Buku"
    
    if 'edisi' in combined_text:
        return "Buku/Bab Buku"
    
    if any(keyword in combined_text for keyword in ['jurnal', 'journal', 'jou.', 'j.', 'acta']):
        return "Jurnal"
    
    if any(keyword in combined_text for keyword in ['prosiding', 'proceedings', 'proc.', 'konferensi', 'conference', 
                                                   'conf.', 'simposium', 'symposium', 'workshop', 'pertemuan', 'meeting']):
        return "Prosiding Konferensi"
    
    if any(keyword in combined_text for keyword in ['buku', 'book', 'bab buku', 'chapter', 'handbook', 'ensiklopedia', 
                                                   'encyclopedia', 'buku teks', 'textbook', 'penerbit', 'publisher', 'press', 
                                                   'books']):
        return "Buku/Bab Buku"
    
    if any(keyword in combined_text for keyword in ['tesis', 'thesis', 'disertasi', 'dissertation', 'skripsi', 'program doktor',
                                                   'program pascasarjana', 'phd', 'master', 'doctoral', 'program studi', 'fakultas']):
        return "Tesis/Disertasi"
    
    if any(keyword in combined_text for keyword in ['analisis', 'analysis', 'penelitian', 'research']):
        return "Laporan Penelitian"
    
    if any(keyword in combined_text for keyword in ['arxiv', 'preprint', 'laporan teknis', 'technical report', 
                                                   'naskah awal', 'working paper', 'teknis']):
        return "Preprint/Laporan Teknis"
    
    if 'paten' in combined_text or 'patent' in combined_text:
        return "Paten"
    
    if re.search(r'\bUU\s*No\.\s*\d+|Undang-undang\s*Nomor\s*\d+|Peraturan\s*(Pemerintah|Presiden)\s*No\.\s*\d+', 
                combined_text):
        return "Buku/Bab Buku"
    
    if re.search(r'vol\.|\bvol\b|\bedisi\b|\bno\.|\bhal\.|\bhalaman\b', combined_text) or \
       re.search(r'\bvol\.\s*\d+\s*(\(\s*\d+\s*\))?', combined_text) or \
       re.search(r'\d+\s*\(\d+\)', combined_text):
        return "Jurnal"
    
    return "Lainnya"

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
        
        vol_num = re.search(
            r'(?<!\S)volume\s*(\d+).*?number\s*(\d+)', 
            text, re.IGNORECASE
        )
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

# Database functions
def connect_to_db():
    """Establish connection to PostgreSQL database"""
    try:
        conn = psycopg2.connect(**DB_PARAMS)
        print("Connected to database successfully!")
        return conn
    except Exception as e:
        print(f"Error connecting to database: {e}")
        return None

def get_authors_from_db(conn):
    """
    Mengambil daftar nama dosen dan URL profil Google Scholar dari database.
    Asumsi:
    - Nama tabel: temp_dosengs_scraping
    - Kolom nama: v_nama_dosen
    - Kolom URL profil
    """
    cursor = None
    try:
        cursor = conn.cursor()
        query = """
            SELECT v_nama, v_link
            FROM temp_dosenGS_scraping
            WHERE v_link IS NOT NULL
        """
        cursor.execute(query)
        results = cursor.fetchall()
        
        df = pd.DataFrame(results, columns=['Name', 'Profile URL'])
        print(f"Berhasil mengambil {len(df)} author dari database.")
        return df
        
    except Exception as e:
        print(f"Error saat mengambil data author dari database: {e}")
        return pd.DataFrame()
    finally:
        if cursor:
            cursor.close()

def determine_publication_type(row):
    """Determine publication type based on available fields for database - matches CSV classification"""
    # Gunakan fungsi classify_publication_type yang sudah ada
    pub_type_csv = classify_publication_type(
        row.get('journal', 'N/A'),
        row.get('conference', 'N/A'),
        row.get('publisher', ''),
        row.get('judul', '')
    )
    
    # Map dari nama CSV ke nama database
    type_mapping = {
        'Jurnal': 'artikel',
        'Prosiding Konferensi': 'prosiding',
        'Buku/Bab Buku': 'buku',
        'Tesis/Disertasi': 'penelitian',
        'Laporan Penelitian': 'penelitian',
        'Preprint/Laporan Teknis': 'penelitian',
        'Paten': 'penelitian',
        'Lainnya': 'penelitian'
    }
    
    return type_mapping.get(pub_type_csv, 'penelitian')

def import_dosen_data(conn, profiles_df):
    """Import dosen data from profiles to database"""
    cursor = conn.cursor()
    dosen_ids = {}
    
    try:
        for _, row in profiles_df.iterrows():
            cursor.execute(
                "SELECT v_id_dosen FROM tmp_dosen_dt WHERE v_id_googleScholar = %s",
                (row.get('ID Google Scholar', ''),)
            )
            result = cursor.fetchone()
            
            if result:
                dosen_id = result[0]
                cursor.execute("""
                    UPDATE tmp_dosen_dt SET 
                    v_nama_dosen = %s,
                    n_total_publikasi = %s,
                    n_total_sitasi_gs = %s,
                    n_i10_index_gs = %s,
                    n_i10_index_gs2020 = %s,
                    n_h_index_gs = %s,
                    n_h_index_gs2020 = %s,
                    v_sumber = 'Google Scholar',
                    t_tanggal_unduh = %s,
                    v_link_url = %s
                    WHERE v_id_dosen = %s
                """, (
                    row.get('Name', ''),
                    row.get('Total_Publikasi', 0),
                    row.get('Citations_all', 0),
                    row.get('i10-index_all', 0),
                    row.get('i10-index_since2020', 0),
                    row.get('h-index_all', 0),
                    row.get('h-index_since2020', 0),
                    datetime.datetime.now(),
                    row.get('Profile URL', ''),
                    dosen_id
                ))
            else:
                cursor.execute("""
                    INSERT INTO tmp_dosen_dt (
                        v_nama_dosen, n_total_publikasi, n_total_sitasi_gs,
                        v_id_googleScholar, n_i10_index_gs, n_i10_index_gs2020,
                        n_h_index_gs, n_h_index_gs2020, v_sumber, t_tanggal_unduh,
                        v_link_url
                    ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                    RETURNING v_id_dosen
                """, (
                    row.get('Name', ''),
                    row.get('Total_Publikasi', 0),
                    row.get('Citations_all', 0),
                    row.get('ID Google Scholar', ''),
                    row.get('i10-index_all', 0),
                    row.get('i10-index_since2020', 0),
                    row.get('h-index_all', 0),
                    row.get('h-index_since2020', 0),
                    'Google Scholar',
                    datetime.datetime.now(),
                    row.get('Profile URL', '')
                ))
                dosen_id = cursor.fetchone()[0]
            
            dosen_ids[row.get('Name', '')] = dosen_id
            
        conn.commit()
        print(f"Successfully imported {len(profiles_df)} dosen profiles to database")
        return dosen_ids
    
    except Exception as e:
        conn.rollback()
        print(f"Error importing dosen data: {e}")
        return {}

def import_jurnal_data(conn, publications_df):
    """Import and get jurnal IDs"""
    cursor = conn.cursor()
    jurnal_ids = {}
    
    try:
        journals = publications_df[publications_df['journal'] != 'N/A']['journal'].unique()
        
        for journal in journals:
            if pd.isna(journal) or journal == 'N/A':
                continue
                
            cursor.execute(
                "SELECT v_id_jurnal FROM stg_jurnal_mt WHERE v_nama_jurnal = %s",
                (journal,)
            )
            result = cursor.fetchone()
            
            if result:
                jurnal_ids[journal] = result[0]
            else:
                cursor.execute("""
                    INSERT INTO stg_jurnal_mt (v_nama_jurnal)
                    VALUES (%s)
                    RETURNING v_id_jurnal
                """, (journal,))
                jurnal_ids[journal] = cursor.fetchone()[0]
        
        conn.commit()
        print(f"Successfully imported {len(jurnal_ids)} journals to database")
        return jurnal_ids
    
    except Exception as e:
        conn.rollback()
        print(f"Error importing journal data: {e}")
        return {}

def import_publications_data(conn, publications_df, dosen_ids, jurnal_ids):
    """Import publications data to database"""
    cursor = conn.cursor()
    
    try:
        imported_count = 0
        
        for _, row in publications_df.iterrows():
            pub_type = determine_publication_type(row)
            
            try:
                year = int(row['tahun_publikasi']) if pd.notna(row['tahun_publikasi']) and row['tahun_publikasi'] != 'N/A' else None
            except:
                year = None
            
            cursor.execute(
                "SELECT v_id_publikasi FROM stg_publikasi_tr WHERE v_judul = %s",
                (row['judul'],)
            )
            result = cursor.fetchone()
            
            if result:
                pub_id = result[0]
            else:
                cursor.execute("""
                    INSERT INTO stg_publikasi_tr (
                        v_judul, v_jenis, v_tahun_publikasi, 
                        n_total_sitasi, v_sumber, v_link_url, t_tanggal_unduh
                    ) VALUES (%s, %s, %s, %s, %s, %s, %s)
                    RETURNING v_id_publikasi
                """, (
                    row['judul'],
                    pub_type,
                    year,
                    row.get('total_sitasi_seluruhnya', 0),
                    'Google Scholar',
                    row.get('Publication URL', ''),
                    datetime.datetime.now()
                ))
                pub_id = cursor.fetchone()[0]
                
                if pub_type == 'artikel':
                    journal_id = jurnal_ids.get(row['journal']) if row['journal'] != 'N/A' else None
                    cursor.execute("""
                        INSERT INTO stg_artikel_dr (
                            v_id_publikasi, v_id_jurnal, v_volume, v_issue, v_pages
                        ) VALUES (%s, %s, %s, %s, %s)
                    """, (
                        pub_id,
                        journal_id,
                        row.get('volume', ''),
                        row.get('issue', ''),
                        row.get('pages', '')
                    ))
                elif pub_type == 'prosiding':
                    cursor.execute("""
                        INSERT INTO stg_prosiding_dr (
                            v_id_publikasi, v_nama_konferensi
                        ) VALUES (%s, %s)
                    """, (
                        pub_id,
                        row.get('conference', '')
                    ))
                elif pub_type == 'buku':
                    cursor.execute("""
                        INSERT INTO stg_buku_dr (
                            v_id_publikasi, v_penerbit
                        ) VALUES (%s, %s)
                    """, (
                        pub_id,
                        row.get('publisher', '')  # ✅ Harus mengambil dari kolom 'publisher'
                    ))
                else:
                    cursor.execute("""
                        INSERT INTO stg_penelitian_dr (
                            v_id_publikasi
                        ) VALUES (%s)
                    """, (pub_id,))
                
                authors = row['author'].split(',')
                for i, author in enumerate(authors):
                    author = author.strip()
                    dosen_id = None
                    for name, id in dosen_ids.items():
                        if author.lower() in name.lower() or name.lower() in author.lower():
                            dosen_id = id
                            break
                    
                    if dosen_id:
                        cursor.execute(
                            "SELECT 1 FROM stg_publikasi_dosen_dt WHERE v_id_publikasi = %s AND v_id_dosen = %s",
                            (pub_id, dosen_id)
                        )
                        if not cursor.fetchone():
                            cursor.execute("""
                                INSERT INTO stg_publikasi_dosen_dt (
                                    v_id_publikasi, v_id_dosen, v_author_order
                                ) VALUES (%s, %s, %s)
                            """, (
                                pub_id,
                                dosen_id,
                                f"{i+1} out of {len(authors)}"
                            ))
                
                if pd.notna(row.get('tahun')) and pd.notna(row.get('total_sitasi_tahun')):
                    try:
                        year_val = int(row['tahun'])
                        citations_val = int(row['total_sitasi_tahun'])
                        
                        cursor.execute("""
                            INSERT INTO stg_publikasi_sitasi_tahunan_dr (
                                v_id_publikasi, v_tahun, n_total_sitasi_tahun, 
                                v_sumber, t_tanggal_unduh
                            ) VALUES (%s, %s, %s, %s, %s)
                        """, (
                            pub_id,
                            year_val,
                            citations_val,
                            'Google Scholar',
                            datetime.datetime.now().date()
                        ))
                    except (ValueError, TypeError):
                        pass
                
                imported_count += 1
        
        conn.commit()
        print(f"Successfully imported {imported_count} publications to database")
    
    except Exception as e:
        conn.rollback()
        print(f"Error importing publications data: {e}")
        raise


def main():
    conn = None  # Inisialisasi koneksi di luar try-finally
    try:
        # 1. Hubungkan ke database untuk mendapatkan daftar author
        conn = connect_to_db()
        if not conn:
            print("Gagal terhubung ke database. Program akan berhenti.")
            return

        df = get_authors_from_db(conn)
        if df.empty:
            print("Tidak ada data author yang dapat di-scrape dari database. Program akan berhenti.")
            return

        # 2. Tanyakan jumlah maksimum author di terminal
        while True:
            try:
                max_authors_str = input(f"Masukkan jumlah maksimum author yang akan di-scrape (total tersedia: {len(df)}): ")
                max_authors = int(max_authors_str)
                if max_authors > 0:
                    break
                else:
                    print("Error: Harap masukkan angka yang lebih besar dari 0.")
            except ValueError:
                print("Error: Input tidak valid. Harap masukkan angka.")
        
        # Pastikan tidak scrape lebih dari yang tersedia
        max_authors = min(max_authors, len(df))

        # === PERUBAHAN: Pertanyaan untuk impor ke DB dihapus ===
        print("\n--- Konfigurasi Dimuat ---")
        print(f"Sumber Data: Database PostgreSQL")
        print(f"Authors to Scrape: {max_authors} dari {len(df)} yang tersedia")
        print(f"Import to Database: Ya (otomatis)") # Diubah menjadi otomatis
        print("---------------------------\n")

        # Tentukan path file output CSV
        profiles_csv_path = 'all_dosen_data_profiles.csv'
        publications_csv_path = 'all_dosen_data_publications.csv'

        # Hapus file CSV lama jika ada untuk memulai dari awal
        if os.path.exists(profiles_csv_path):
            os.remove(profiles_csv_path)
            print(f"Menghapus file lama: {profiles_csv_path}")
        if os.path.exists(publications_csv_path):
            os.remove(publications_csv_path)
            print(f"Menghapus file lama: {publications_csv_path}")
            
        # Kumpulan data untuk diimpor ke DB
        final_profiles_df = pd.DataFrame()
        final_publications_df = pd.DataFrame()

        # Setup driver
        driver = setup_driver_with_manual_login()
        
        if driver is None:
            print("Gagal membuat driver dengan login manual. Program berhenti.")
            return

        try:
            for index, row in df.head(max_authors).iterrows():
                author_name = row['Name']
                profile_url = row['Profile URL']
                print(f"\nScraping data untuk ({index + 1}/{max_authors}): {author_name}...")
                
                profile_data = scrape_google_scholar_profile_with_existing_driver(driver, profile_url, author_name)
                
                if profile_data and profile_data['publications']:
                    print(f"Berhasil mengambil data untuk {profile_data['name']}")
                    
                    # --- Proses dan Simpan Data Profil ---
                    profile_entry = {
                        'Name': profile_data['name'],
                        'Affiliation': profile_data['affiliation'],
                        'Profile URL': profile_data['profile_url'],
                        'ID Google Scholar': profile_data['scholar_id'],
                        **profile_data['citation_stats'],
                        'Total_Publikasi': len(profile_data['publications']),
                        'Tanggal_Unduh': datetime.datetime.now().strftime('%Y-%m-%d')
                    }
                    
                    current_profile_df = pd.DataFrame([profile_entry])
                    
                    if 'citations_per_year' in profile_data and profile_data['citations_per_year']:
                         citations_per_year_df = pd.json_normalize(profile_data['citations_per_year'])
                         citations_per_year_df.columns = [f"Citations_{year}" for year in citations_per_year_df.columns]
                         current_profile_df = pd.concat([current_profile_df.reset_index(drop=True), citations_per_year_df], axis=1)

                    header_needed = not os.path.exists(profiles_csv_path)
                    current_profile_df.to_csv(profiles_csv_path, mode='a', header=header_needed, index=False, encoding='utf-8')
                    print(f"Menambahkan data profil untuk {author_name} ke {profiles_csv_path}")
                    
                    # --- Proses dan Simpan Data Publikasi ---
                    transformed_publications = transform_publications_data(profile_data['publications'])
                    current_publications_df = pd.DataFrame(transformed_publications)
                    
                    header_needed = not os.path.exists(publications_csv_path)
                    current_publications_df.to_csv(publications_csv_path, mode='a', header=header_needed, index=False, encoding='utf-8')
                    print(f"Menambahkan {len(current_publications_df)} data publikasi ke {publications_csv_path}")
                    
                    # Gabungkan data untuk proses impor DB
                    final_profiles_df = pd.concat([final_profiles_df, current_profile_df], ignore_index=True)
                    final_publications_df = pd.concat([final_publications_df, current_publications_df], ignore_index=True)

                else:
                    print(f"Gagal mengambil data atau tidak ada publikasi untuk {author_name}")
                
                if index < max_authors - 1:
                    delay_time = random.uniform(60, 120)
                    print(f"Menunggu selama {delay_time:.1f} detik sebelum lanjut...")
                    time.sleep(delay_time)
        finally:
            if driver is not None:
                try:
                    driver.quit()
                    print("\nDriver berhasil ditutup")
                except Exception as e:
                    print(f"Error saat menutup driver: {e}")
        
        if final_profiles_df.empty:
            print("Tidak ada data yang berhasil di-scrape. Program berhenti.")
            return
            
        print("\nProses scraping selesai. Semua data telah disimpan ke file CSV.")
        
        # === PERUBAHAN: Blok impor DB dijalankan secara otomatis ===
        # Tidak ada lagi 'if/else', langsung impor.
        if not conn:
            conn = connect_to_db()
            if not conn:
                print("Gagal menyambung kembali ke database. Data hanya tersimpan di file CSV.")
                return
        
        try:
            print("Memulai proses impor semua data yang terkumpul ke database...")
            dosen_ids = import_dosen_data(conn, final_profiles_df)
            jurnal_ids = import_jurnal_data(conn, final_publications_df)
            import_publications_data(conn, final_publications_df, dosen_ids, jurnal_ids)
            print("Proses impor data ke database berhasil!")
        except Exception as e:
            print(f"Error saat proses impor ke database: {e}")
            print("Data tetap tersedia di dalam file CSV.")
        
        print(f"\nKolom pada CSV Publikasi: {final_publications_df.columns.tolist()}")
    
    except Exception as e:
        print(f"Terjadi error pada fungsi utama: {e}")
        import traceback
        traceback.print_exc()
    finally:
        # Selalu pastikan koneksi database ditutup
        if conn:
            conn.close()
            print("Koneksi database telah ditutup.")

if __name__ == "__main__":
    main()