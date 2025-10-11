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

# Database connection parameters
DB_PARAMS = {
    'dbname': 'SKM_PUBLIKASI',
    'user': 'rayhanadjisantoso',
    'password': 'rayhan123',
    'host': 'localhost',
    'port': '5432'
}

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
        service = Service(ChromeDriverManager().install())
        driver = webdriver.Chrome(service=service, options=chrome_options)
    except Exception as e:
        print(f"Error saat membuat driver: {e}")
        try:
            driver = webdriver.Chrome(options=chrome_options)
        except Exception as e2:
            print(f"Error alternatif saat membuat driver: {e2}")
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

def setup_driver_with_check_login():
    """Setup driver dan check apakah sudah login (untuk web interface)"""
    driver = setup_driver()
    
    try:
        driver.get("https://scholar.google.com")
        time.sleep(5)
        
        # Check if already logged in
        try:
            # Cari elemen yang menandakan sudah login
            profile_element = driver.find_element(By.CSS_SELECTOR, '#gs_gb_rt a')
            print("✓ Appears to be logged in or no sign-in required")
            return driver
        except NoSuchElementException:
            print("✓ Appears to be logged in or no sign-in required")
            return driver
            
    except Exception as e:
        print(f"Error saat setup driver: {e}")
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
    return classify_by_regex(publisher, title)

def classify_by_regex(publisher, title=""):
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
    if any(keyword in combined_text for keyword in ['jurnal', 'journal', 'jou.', 'j.', 'acta']):
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
    """Transform publications data menggunakan klasifikasi yang benar"""
    transformed_data = []
    
    for pub in all_publications:
        # Data dasar publikasi
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
        
        # Ekstrak volume dan issue menggunakan regex jika tidak tersedia
        if not base_data['volume'] or not base_data['issue']:
            source_text = pub.get('journal', '') if pub.get('journal', 'N/A') != 'N/A' else pub.get('conference', '')
            vol, no = extract_vol_no(source_text, pub.get('title', ''))
            if not base_data['volume']:
                base_data['volume'] = vol
            if not base_data['issue']:
                base_data['issue'] = no
        
        # Ekstrak pages menggunakan regex jika tidak tersedia
        if not base_data['pages']:
            source_text = pub.get('journal', '') if pub.get('journal', 'N/A') != 'N/A' else pub.get('conference', '')
            base_data['pages'] = extract_pages(source_text, pub.get('title', ''))
        
        citations_per_year = pub.get('citations_per_year', {})
        
        # Jika tidak ada data sitasi per tahun, tambahkan satu baris dengan data dasar
        if not citations_per_year:
            transformed_data.append({
                **base_data,
                'tahun': pub.get('year', 'N/A'),
                'total_sitasi_tahun': '',
                'tanggal_unduh': datetime.datetime.now().strftime('%Y-%m-%d')
            })
        else:
            # Untuk setiap tahun dalam citations_per_year, buat baris terpisah
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

def get_authors_from_db(conn, scrape_from_beginning=False):
    """
    Mengambil daftar nama dosen dan URL profil Google Scholar dari database.
    
    Args:
        conn: Database connection
        scrape_from_beginning: Jika True, ambil semua dosen termasuk yang sudah 'completed'.
                              Jika False, hanya ambil dosen dengan status pending/error/processing.
    """
    cursor = None
    try:
        cursor = conn.cursor()
        
        if scrape_from_beginning:
            # Ambil SEMUA dosen, termasuk yang sudah completed
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
            print(f"  ⚠️  Mode: SCRAPING DARI AWAL - Semua dosen akan di-scrape ulang")
        else:
            # Hanya ambil dosen yang belum selesai
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
            print(f"Berhasil mengambil {len(df)} author yang belum selesai di-scrape dari database.")
            
            # Tampilkan info jika ada dosen dengan status 'processing'
            processing_count = len(df[df['Status'] == 'processing'])
            if processing_count > 0:
                print(f"  ⚠️  Ditemukan {processing_count} dosen dengan status 'processing' (kemungkinan scraping sebelumnya terhenti)")
                print(f"  → Dosen tersebut akan di-scrape ulang terlebih dahulu")
        
        return df
        
    except Exception as e:
        print(f"Error saat mengambil data author dari database: {e}")
        return pd.DataFrame()
    finally:
        if cursor:
            cursor.close()

def get_scraping_statistics(conn):
    """
    Mendapatkan statistik scraping dari database
    """
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
        
        stats = {
            'total': result[0] if result else 0,
            'completed': result[1] if result else 0,
            'error': result[2] if result else 0,
            'processing': result[3] if result else 0,
            'pending': result[4] if result else 0
        }
        
        return stats
        
    except Exception as e:
        print(f"Error saat mengambil statistik scraping: {e}")
        return {'total': 0, 'completed': 0, 'error': 0, 'processing': 0, 'pending': 0}
    finally:
        if cursor:
            cursor.close()

def reset_all_status_to_pending(conn):
    """
    Reset semua status menjadi 'pending' untuk scraping dari awal
    """
    cursor = None
    try:
        cursor = conn.cursor()
        query = """
            UPDATE temp_dosenGS_scraping
            SET v_status = 'pending',
                v_error_message = NULL,
                t_last_updated = NOW()
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
    """
    Update status scraping untuk seorang dosen
    Status: 'pending', 'processing', 'completed', 'error'
    """
    cursor = None
    try:
        cursor = conn.cursor()
        
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
        
        conn.commit()
        print(f"Status untuk {author_name} diupdate menjadi: {status}")
        
    except Exception as e:
        conn.rollback()
        print(f"Error saat update status untuk {author_name}: {e}")
    finally:
        if cursor:
            cursor.close()

def import_dosen_data(conn, profiles_df):
    """Import dosen data from profiles to database"""
    cursor = conn.cursor()
    dosen_ids = {}
    try:
        for _, row in profiles_df.iterrows():
            try:
                insert_query = sql.SQL("""
                    INSERT INTO tmp_dosen_dt 
                    (v_nama_dosen, v_id_googlescholar, n_total_publikasi, 
                     n_total_sitasi_gs, n_h_index_gs, n_h_index_gs2020,
                     n_i10_index_gs, n_i10_index_gs2020, v_sumber, v_link_url, t_tanggal_unduh)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                """)
                
                values = (
                    row['Name'],
                    row['ID Google Scholar'],
                    int(row['Total_Publikasi']) if pd.notna(row['Total_Publikasi']) else 0,
                    int(row['Citations_all']) if pd.notna(row['Citations_all']) else 0,
                    int(row['h-index_all']) if pd.notna(row['h-index_all']) else 0,
                    int(row['h-index_since2020']) if pd.notna(row['h-index_since2020']) else 0,
                    int(row['i10-index_all']) if pd.notna(row['i10-index_all']) else 0,
                    int(row['i10-index_since2020']) if pd.notna(row['i10-index_since2020']) else 0,
                    'Google Scholar',
                    row['Profile URL'],
                    datetime.datetime.now().date()
                )
                
                cursor.execute(insert_query, values)
                dosen_ids[row['Name']] = row['ID Google Scholar']
                
            except Exception as e:
                print(f"  Warning: Gagal insert profil {row.get('Name', 'Unknown')}: {e}")
                conn.rollback()
                continue
        
        conn.commit()
        print(f"✓ Berhasil memasukkan {len(dosen_ids)} data profil ke tmp_dosen_dt")
        return dosen_ids
        
    except Exception as e:
        print(f"✗ Error saat insert profile data: {e}")
        conn.rollback()
        return {}
    finally:
        cursor.close()

def normalize_publication_type(pub_type):
    """
    Normalisasi tipe publikasi ke format yang sesuai dengan constraint database
    Database menerima: 'artikel', 'buku', 'penelitian', 'prosiding', 'lainnya'
    """
    pub_type_lower = str(pub_type).lower().strip()
    
    # Mapping dari tipe publikasi hasil scraping ke tipe di database
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
                # Tentukan jenis publikasi dan normalisasi
                pub_type_raw = row.get('publication_type', 'lainnya')
                pub_type = normalize_publication_type(pub_type_raw)
                
                # Insert ke stg_publikasi_tr
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
                
                # Insert data spesifik berdasarkan jenis publikasi yang sudah dinormalisasi
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
                
                # Cek apakah ada data tahun dan total_sitasi_tahun yang valid
                if pd.notna(row.get('tahun')) and pd.notna(row.get('total_sitasi_tahun')):
                    tahun_str = str(row.get('tahun', '')).strip()
                    sitasi_str = str(row.get('total_sitasi_tahun', '')).strip()
                    
                    # Validasi apakah keduanya adalah angka
                    if tahun_str.isdigit() and sitasi_str.replace('-', '').isdigit():
                        _insert_sitasi_tahunan(cursor, pub_id, row)
                
                # Link ke dosen
                author_name = row.get('Author', '')
                if author_name and author_name in dosen_ids:
                    # Cek apakah sudah ada link
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
    """Insert data spesifik artikel/jurnal"""
    try:
        # Ambil nama jurnal dari row data
        journal_name = row.get('journal', '')
        
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
            row.get('volume', ''),
            row.get('issue', ''),
            row.get('pages', ''),
            datetime.datetime.now()
        )
        
        cursor.execute(insert_artikel_query, values)
        
    except Exception as e:
        print(f"    Error insert artikel data: {e}")

def _insert_prosiding_data(cursor, pub_id, row):
    """Insert data spesifik prosiding"""
    try:
        insert_query = sql.SQL("""
            INSERT INTO stg_prosiding_dr (v_id_publikasi, v_nama_konferensi, f_terindeks_scopus, t_updated_at)
            VALUES (%s, %s, %s, %s)
        """)
        
        values = (
            pub_id,
            row.get('conference', ''),
            False,
            datetime.datetime.now()
        )
        
        cursor.execute(insert_query, values)
    except Exception as e:
        print(f"    Error insert prosiding data: {e}")

def _insert_buku_data(cursor, pub_id, row):
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

def _insert_penelitian_data(cursor, pub_id, row):
    """Insert data publikasi penelitian (tesis/disertasi)"""
    try:
        insert_query = sql.SQL("""
            INSERT INTO stg_penelitian_dr (v_id_publikasi, v_kategori_penelitian, t_updated_at)
            VALUES (%s, %s, %s)
        """)
        
        pub_type_raw = str(row.get('publication_type', '')).lower()
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

def _insert_lainnya_data(cursor, pub_id, row):
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

def _insert_sitasi_tahunan(cursor, pub_id, row):
    """Insert data sitasi per tahun"""
    try:
        # Ambil dan validasi data
        tahun_raw = row.get('tahun', '')
        sitasi_raw = row.get('total_sitasi_tahun', '')
        
        # Konversi ke integer
        if pd.notna(tahun_raw) and pd.notna(sitasi_raw):
            tahun_str = str(tahun_raw).strip()
            sitasi_str = str(sitasi_raw).strip()
            
            if tahun_str.isdigit():
                tahun = int(tahun_str)
                
                # Konversi sitasi (bisa negatif jadi handle dengan replace)
                if sitasi_str.replace('-', '').isdigit():
                    sitasi = int(sitasi_str)
                else:
                    sitasi = 0
                
                # Validasi tahun
                if 2000 <= tahun <= 2030:
                    insert_query = sql.SQL("""
                        INSERT INTO stg_publikasi_sitasi_tahunan_dr 
                        (v_id_publikasi, v_tahun, n_total_sitasi_tahun, v_sumber, t_tanggal_unduh)
                        VALUES (%s, %s, %s, %s, %s)
                    """)
                    
                    values = (
                        pub_id,
                        tahun,
                        sitasi,
                        'Google Scholar',
                        datetime.datetime.now().date()
                    )
                    
                    cursor.execute(insert_query, values)
    except Exception as e:
        print(f"    Error insert sitasi tahunan: {e}")

def main():
    conn = None
    try:
        # 1. Hubungkan ke database
        conn = connect_to_db()
        if not conn:
            print("Gagal terhubung ke database. Program akan berhenti.")
            return

        # Tampilkan statistik scraping
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

        # Tanyakan apakah ingin scraping dari awal
        print("Pilihan Mode Scraping:")
        print("1. Lanjutkan scraping (hanya dosen yang belum selesai)")
        print("2. Scraping dari awal (reset semua status dan scrape ulang semua dosen)")
        
        while True:
            scrape_mode = input("\nPilih mode (1/2): ").strip()
            if scrape_mode in ['1', '2']:
                break
            else:
                print("Error: Pilih 1 atau 2")
        
        scrape_from_beginning = (scrape_mode == '2')
        
        if scrape_from_beginning:
            print("\n⚠️  Mode: SCRAPING DARI AWAL")
            confirm = input("Apakah Anda yakin ingin reset semua status dan scraping ulang? (yes/no): ").strip().lower()
            if confirm in ['yes', 'y']:
                if reset_all_status_to_pending(conn):
                    print("✓ Status berhasil di-reset. Memulai scraping dari awal...\n")
                else:
                    print("✗ Gagal reset status. Program berhenti.")
                    return
            else:
                print("Scraping dari awal dibatalkan. Menggunakan mode lanjutkan scraping.")
                scrape_from_beginning = False

        # Ambil daftar author
        df = get_authors_from_db(conn, scrape_from_beginning)
        if df.empty:
            print("Semua author telah selesai di-scrape atau tidak ada data. Program akan berhenti.")
            return

        # 2. Tanyakan jumlah maksimum author
        while True:
            try:
                max_authors_str = input(f"Masukkan jumlah maksimum author yang akan di-scrape (tersisa: {len(df)}): ")
                max_authors = int(max_authors_str)
                if max_authors > 0:
                    break
                else:
                    print("Error: Harap masukkan angka yang lebih besar dari 0.")
            except ValueError:
                print("Error: Input tidak valid. Harap masukkan angka.")
        
        max_authors = min(max_authors, len(df))

        print("\n--- Konfigurasi Dimuat ---")
        print(f"Sumber Data: Database PostgreSQL")
        print(f"Mode Scraping: {'DARI AWAL (semua dosen)' if scrape_from_beginning else 'LANJUTKAN (hanya yang belum selesai)'}")
        print(f"Authors to Scrape: {max_authors} dari {len(df)} yang tersedia")
        print(f"Import to Database: Ya (otomatis)")
        print("---------------------------\n")

        # Path file CSV
        profiles_csv_path = 'all_dosen_data_profiles.csv'
        publications_csv_path = 'all_dosen_data_publications.csv'

        # Buat file baru jika belum ada (dengan header)
        if not os.path.exists(profiles_csv_path):
            pd.DataFrame().to_csv(profiles_csv_path, index=False)
        if not os.path.exists(publications_csv_path):
            pd.DataFrame().to_csv(publications_csv_path, index=False)
            
        final_profiles_df = pd.DataFrame()
        final_publications_df = pd.DataFrame()

        # Setup driver
        driver = setup_driver_with_manual_login()
        
        if driver is None:
            print("Gagal membuat driver dengan login manual. Program berhenti.")
            return

        try:
            scraping_count = 0
            for index, row in df.head(max_authors).iterrows():
                author_name = row['Name']
                profile_url = row['Profile URL']
                
                print(f"\n{'='*60}")
                print(f"Scraping ({scraping_count + 1}/{max_authors}): {author_name}")
                print(f"{'='*60}")
                
                # Update status menjadi 'processing'
                update_scraping_status(conn, author_name, 'processing')
                
                try:
                    profile_data = scrape_google_scholar_profile_with_existing_driver(driver, profile_url, author_name)
                    
                    if profile_data and profile_data['publications']:
                        print(f"✓ Berhasil mengambil data untuk {profile_data['name']}")
                        
                        # Simpan data profil
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

                        header_needed = not os.path.getsize(profiles_csv_path) > 0
                        current_profile_df.to_csv(profiles_csv_path, mode='a', header=header_needed, index=False, encoding='utf-8')
                        print(f"✓ Data profil disimpan ke {profiles_csv_path}")
                        
                        # Simpan data publikasi
                        transformed_publications = transform_publications_data(profile_data['publications'])
                        current_publications_df = pd.DataFrame(transformed_publications)
                        
                        header_needed = not os.path.getsize(publications_csv_path) > 0
                        current_publications_df.to_csv(publications_csv_path, mode='a', header=header_needed, index=False, encoding='utf-8')
                        print(f"✓ {len(current_publications_df)} publikasi disimpan ke {publications_csv_path}")
                        
                        # Gabungkan untuk impor DB
                        final_profiles_df = pd.concat([final_profiles_df, current_profile_df], ignore_index=True)
                        final_publications_df = pd.concat([final_publications_df, current_publications_df], ignore_index=True)
                        
                        # Update status menjadi 'completed'
                        update_scraping_status(conn, author_name, 'completed')
                        scraping_count += 1
                        
                    else:
                        error_msg = f"Tidak ada publikasi ditemukan"
                        print(f"✗ {error_msg} untuk {author_name}")
                        update_scraping_status(conn, author_name, 'error', error_msg)
                
                except Exception as e:
                    error_msg = f"Error scraping: {str(e)}"
                    print(f"✗ {error_msg}")
                    update_scraping_status(conn, author_name, 'error', error_msg)
                
                # Delay antara scraping
                if scraping_count < max_authors:
                    delay_time = random.uniform(60, 120)
                    print(f"\n⏳ Menunggu {delay_time:.1f} detik sebelum lanjut...")
                    time.sleep(delay_time)
                    
        finally:
            if driver is not None:
                try:
                    driver.quit()
                    print("\n✓ Driver berhasil ditutup")
                except Exception as e:
                    print(f"✗ Error saat menutup driver: {e}")
        
        if final_profiles_df.empty:
            print("\n✗ Tidak ada data yang berhasil di-scrape.")
            return
            
        print(f"\n{'='*60}")
        print("PROSES SCRAPING SELESAI")
        print(f"{'='*60}")
        print(f"Total berhasil di-scrape: {len(final_profiles_df)} dosen")
        print(f"Total publikasi: {len(final_publications_df)}")
        print(f"{'='*60}\n")
        
        # Impor ke database
        if not conn:
            conn = connect_to_db()
        if not conn:
            print("✗ Gagal menyambung kembali ke database. Data hanya tersimpan di file CSV.")
            return
        try:
            print("\n" + "="*60)
            print("PROSES IMPOR DATA KE DATABASE")
            print("="*60)
            dosen_ids = import_dosen_data(conn, final_profiles_df)
            import_publications_data(conn, final_publications_df, dosen_ids)
            print("✓ Proses impor data ke database berhasil!")
            print("="*60 + "\n")
        except Exception as e:
            print(f"✗ Error saat proses impor ke database: {e}")
            import traceback
            traceback.print_exc()
            print("Data tetap tersedia di dalam file CSV.")
        
        # Tampilkan statistik akhir
        final_stats = get_scraping_statistics(conn)
        print(f"\n{'='*60}")
        print("STATISTIK SCRAPING TERBARU")
        print(f"{'='*60}")
        print(f"Total Dosen        : {final_stats['total']}")
        print(f"Sudah Selesai      : {final_stats['completed']}")
        print(f"Processing (stuck) : {final_stats['processing']}")
        print(f"Error              : {final_stats['error']}")
        print(f"Belum Di-scrape    : {final_stats['pending']}")
        print(f"{'='*60}\n")
    
    except Exception as e:
        print(f"✗ Terjadi error pada fungsi utama: {e}")
        import traceback
        traceback.print_exc()
    finally:
        if conn:
            conn.close()
            print("✓ Koneksi database telah ditutup.")

if __name__ == "__main__":
    main()