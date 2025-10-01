#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
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
    chrome_options.add_argument("--disable-browser-side-navigation")  # Mencegah crash saat navigasi
    chrome_options.add_argument("--disable-features=NetworkService")  # Meningkatkan stabilitas
    chrome_options.add_argument("--disable-web-security")  # Mengurangi masalah keamanan yang dapat menyebabkan crash
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
        # Coba cara alternatif jika cara utama gagal
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
    driver.set_page_load_timeout(120)  # Tambah timeout untuk halaman yang lambat
    driver.implicitly_wait(30)  # Tambah waktu tunggu implisit
    
    # Tambahkan cookies untuk Google Scholar
    try:
        driver.get("https://scholar.google.com")
        time.sleep(5)  # Tunggu lebih lama untuk memastikan halaman dimuat
        
        # Cookies yang umum digunakan untuk Google Scholar
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
        # Buka Google Scholar
        driver.get("https://scholar.google.com")
        
        # Tunggu user login secara manual
        print("\n" + "="*50)
        print("SILAKAN LOGIN KE GOOGLE SCHOLAR SECARA MANUAL")
        print("Setelah login berhasil, tekan Enter untuk melanjutkan")
        print("="*50 + "\n")
        
        input("Tekan Enter setelah login selesai...")
        
        # Verifikasi login berhasil
        print("Memverifikasi login...")
        time.sleep(3)
        
        # Simpan cookies setelah login
        cookies = driver.get_cookies()
        print(f"Berhasil mendapatkan {len(cookies)} cookies")
        
        return driver
    except Exception as e:
        print(f"Error saat setup driver dengan login manual: {e}")
        try:
            driver.quit()
        except:
            pass
        return None  # Explicitly return None to indicate failure

def scrape_google_scholar_profile_with_existing_driver(driver, profile_url, author_name):
    """Scrape Google Scholar profile using an existing driver (already logged in)"""
    try:
        print(f"Accessing profile for: {author_name}")
        print(f"Profile URL: {profile_url}")
        
        # Langsung akses profile URL
        driver.get(profile_url)
        time.sleep(random.uniform(5, 8))  # Jeda lebih lama untuk loading
        
        # Ekstrak Google Scholar ID dari profile URL
        scholar_id = ""
        if "user=" in profile_url:
            scholar_id = profile_url.split("user=")[1].split("&")[0]  # Ambil hanya ID, abaikan parameter lain
        
        # Ekstrak informasi profil dengan error handling yang lebih baik
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
                    break  # Tombol tidak aktif (semua publikasi sudah dimuat)
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
                        'authors': pub_details['authors'] or authors,  # Gunakan authors dari detail jika ada, fallback ke yang lama
                        'journal': pub_details['journal'],  # Gunakan journal dari detail
                        'conference': pub_details['conference'],  # Gunakan conference dari detail
                        'publisher': pub_details['publisher'],  # Publisher selalu ada
                        'year': year,
                        'citations': citations,
                        'link': pub_link,  # URL publikasi yang akan digunakan
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
            'profile_url': profile_url,  # Tambahkan Profile URL
            'scholar_id': scholar_id,    # Tambahkan Scholar ID
            'citation_stats': citation_data,
            'citations_per_year': citations_per_year,
            'publications': publications
        }
        return profile_data
            
    except Exception as e:
        print(f"Error saat scraping profil {author_name}: {str(e)}")
        return None

def get_publication_citations_per_year_selenium(driver, pub_url):
    """Extract citations per year for a specific publication using Selenium + BeautifulSoup with Method 1 only"""
    original_window = driver.current_window_handle
    new_tab_created = False
    
    try:
        # Open new tab dengan penanganan error yang lebih baik
        try:
            driver.execute_script("window.open('');")        
            new_tab_created = True
            
            # Pastikan window handles masih tersedia
            if len(driver.window_handles) < 2:
                print(f"Tidak dapat membuka tab baru untuk {pub_url}")
                return {}
                
            driver.switch_to.window(driver.window_handles[1])
        except Exception as e:
            print(f"Error saat membuka tab baru: {e}")
            return {}
        
        # Load publication page dengan penanganan error
        try:
            driver.get(pub_url)
            time.sleep(random.uniform(4, 6))
        except Exception as e:
            print(f"Error saat memuat halaman publikasi: {e}")
            return {}
        
        # Wait for main content to load
        try:
            WebDriverWait(driver, 25).until(
                EC.presence_of_element_located((By.CSS_SELECTOR, '.gsc_oci_main, .gs_scl'))
            )
        except TimeoutException:
            print(f"Timeout waiting for main content at {pub_url}")
            
        # Improve page loading with scroll interactions
        driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
        time.sleep(1.5)
        driver.execute_script("window.scrollTo(0, 0);")
        time.sleep(1.5)
        
        # Get page source after JavaScript rendering
        page_source = driver.page_source
        
        # Parse HTML
        soup = BeautifulSoup(page_source, 'html.parser')
        
        # Initialize citations dictionary
        citations_per_year = {}
        
        # Method 1: Direct extraction from citation graph
        print(f"Using graph extraction method for {pub_url}")
        
        # PERBAIKAN: Ambil elemen tahun dan nilai sitasi dengan cara yang benar
        year_elements = soup.select('.gsc_oci_g_t')
        citation_elements = soup.select('.gsc_oci_g_a')
        
        # Proses elemen tahun
        for year_element in year_elements:
            year = year_element.text.strip()
            if year.isdigit() and 2010 <= int(year) <= 2024:
                # Default nilai sitasi adalah 0
                citations_per_year[year] = 0
        
        # Proses elemen sitasi
        for citation_element in citation_elements:
            # Ambil tahun dari posisi elemen (style="left:XXpx")
            style = citation_element.get('style', '')
            left_match = re.search(r'left:([0-9]+)px', style)
            if not left_match:
                continue
                
            # Cari elemen tahun yang posisinya paling dekat dengan elemen sitasi
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
            
            # Jika menemukan tahun yang cocok dan valid
            if closest_year and closest_year.isdigit() and 2010 <= int(closest_year) <= 2024:
                # Ambil nilai sitasi dari span dengan class gsc_oci_g_al
                citation_value_element = citation_element.select_one('.gsc_oci_g_al')
                if citation_value_element:
                    citation_value = citation_value_element.text.strip()
                    if citation_value.isdigit():
                        citations_per_year[closest_year] = int(citation_value)
        
        # Alternatif: Jika metode di atas tidak berhasil, coba cara langsung
        if not citations_per_year:
            # Cari semua elemen span dengan class gsc_oci_g_al
            citation_spans = soup.select('.gsc_oci_g_al')
            for span in citation_spans:
                # Cari parent element (a tag) untuk mendapatkan posisi
                parent = span.parent
                if parent and parent.name == 'a':
                    style = parent.get('style', '')
                    left_match = re.search(r'left:([0-9]+)px', style)
                    if not left_match:
                        continue
                        
                    left_pos = int(left_match.group(1))
                    
                    # Cari tahun terdekat
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
                    
                    # Jika menemukan tahun yang cocok dan valid
                    if closest_year and closest_year.isdigit() and 2010 <= int(closest_year) <= 2024:
                        citation_value = span.text.strip()
                        if citation_value.isdigit():
                            citations_per_year[closest_year] = int(citation_value)
        
        # Close tab and return to original tab
        driver.close()
        driver.switch_to.window(original_window)
        
        return citations_per_year
        
    except Exception as e:
        print(f"Error retrieving citations per year for publication {pub_url}: {str(e)}")
        return {}
        
    finally:
        # Pastikan selalu kembali ke tab original dan menutup tab tambahan
        if new_tab_created:
            try:
                # Periksa apakah driver masih aktif
                if driver.session_id:
                    # Periksa apakah tab masih ada
                    if len(driver.window_handles) > 1:
                        # Tutup tab saat ini jika bukan tab original
                        if driver.current_window_handle != original_window:
                            driver.close()
                        # Kembali ke tab original jika masih ada
                        if original_window in driver.window_handles:
                            driver.switch_to.window(original_window)
            except Exception as e:
                print(f"Error saat menangani tab browser: {e}")

def get_publication_details_selenium(driver, pub_url):
    """Extract detailed publication information from publication page using Selenium + BeautifulSoup"""
    original_window = driver.current_window_handle
    new_tab_created = False
    
    # Inisialisasi data default
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
        # Open new tab dengan penanganan error yang lebih baik
        try:
            driver.execute_script("window.open('');")        
            new_tab_created = True
            
            # Pastikan window handles masih tersedia
            if len(driver.window_handles) < 2:
                print(f"Tidak dapat membuka tab baru untuk {pub_url}")
                return details
                
            driver.switch_to.window(driver.window_handles[1])
        except Exception as e:
            print(f"Error saat membuka tab baru: {e}")
            return details
        
        # Load publication page dengan penanganan error
        try:
            driver.get(pub_url)
            time.sleep(random.uniform(4, 6))
        except Exception as e:
            print(f"Error saat memuat halaman publikasi: {e}")
            return details
        
        # Wait for main content to load
        try:
            WebDriverWait(driver, 25).until(
                EC.presence_of_element_located((By.CSS_SELECTOR, '.gsc_oci_main, .gs_scl'))
            )
        except TimeoutException:
            print(f"Timeout waiting for main content at {pub_url}")
            
        # Improve page loading with scroll interactions
        driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
        time.sleep(1.5)
        driver.execute_script("window.scrollTo(0, 0);")
        time.sleep(1.5)
        
        # Get page source after JavaScript rendering
        page_source = driver.page_source
        
        # Parse HTML
        soup = BeautifulSoup(page_source, 'html.parser')
        
        # Ekstrak informasi dari halaman detail
        author_fields = soup.find_all('div', class_='gsc_oci_field')
        author_values = soup.find_all('div', class_='gsc_oci_value')
        
        # Proses setiap pasangan field dan value
        for field, value in zip(author_fields, author_values):
            field_text = field.get_text().strip().lower()
            value_text = value.get_text().strip()
            
            # Ekstrak author
            if field_text == 'authors' or field_text == 'author':
                details['authors'] = value_text
            
            # Ekstrak journal
            elif field_text == 'journal':
                details['journal'] = value_text
                details['conference'] = 'N/A'  # Jika journal ada, conference jadi N/A
            
            # Ekstrak conference
            elif field_text == 'conference':
                details['conference'] = value_text
                details['journal'] = 'N/A'  # Jika conference ada, journal jadi N/A
            
            # Ekstrak publisher (selalu ada)
            elif field_text == 'publisher':
                details['publisher'] = value_text
            
            # Jika field adalah 'source', tentukan apakah itu journal atau conference
            elif field_text == 'source':
                # Cek kata kunci untuk menentukan journal vs conference
                value_lower = value_text.lower()
                if any(keyword in value_lower for keyword in ['journal', 'jurnal', 'acta', 'review', 'letters']):
                    details['journal'] = value_text
                    details['conference'] = 'N/A'
                elif any(keyword in value_lower for keyword in ['conference', 'proceedings', 'symposium', 'workshop', 'konferensi', 'prosiding']):
                    details['conference'] = value_text
                    details['journal'] = 'N/A'
                else:
                    # Jika tidak bisa ditentukan, masukkan sebagai publisher
                    if not details['publisher']:
                        details['publisher'] = value_text
            
            # Ekstrak volume
            elif field_text == 'volume':
                details['volume'] = value_text
            
            # Ekstrak issue
            elif field_text == 'issue':
                details['issue'] = value_text
            
            # Ekstrak pages
            elif field_text == 'pages':
                details['pages'] = value_text
        
        return details
        
    except Exception as e:
        print(f"Error retrieving details for publication {pub_url}: {str(e)}")
        return details
        
    finally:
        # Pastikan selalu kembali ke tab original dan menutup tab tambahan
        if new_tab_created:
            try:
                # Periksa apakah driver masih aktif
                if driver.session_id:
                    # Periksa apakah tab masih ada
                    if len(driver.window_handles) > 1:
                        # Tutup tab saat ini jika bukan tab original
                        if driver.current_window_handle != original_window:
                            driver.close()
                        # Kembali ke tab original jika masih ada
                        if original_window in driver.window_handles:
                            driver.switch_to.window(original_window)
            except Exception as e:
                print(f"Error saat menangani tab browser: {e}")

def classify_publication_type(journal, conference, publisher, title=""):
    """
    Klasifikasi jenis publikasi berdasarkan aturan baru:
    1. Jika kolom journal memiliki nilai, maka jenis publikasinya adalah jurnal
    2. Jika kolom conference memiliki nilai, maka jenis publikasinya adalah prosiding
    3. Jika kedua kolom tidak memiliki nilai, gunakan regex untuk mengidentifikasi
    """
    
    # Prioritas 1: Jika journal memiliki nilai (bukan N/A atau kosong)
    if journal and journal.strip() and journal != 'N/A':
        return "Jurnal"
    
    # Prioritas 2: Jika conference memiliki nilai (bukan N/A atau kosong)
    if conference and conference.strip() and conference != 'N/A':
        return "Prosiding Konferensi"
    
    # Prioritas 3: Jika kedua kolom tidak memiliki nilai, gunakan regex
    return classify_by_regex(publisher, title)

def classify_by_regex(publisher, title=""):
    """Klasifikasi menggunakan regex jika journal dan conference tidak tersedia"""
    
    # Gabungkan publisher dan title untuk analisis
    combined_text = f"{publisher} {title}".lower()
    
    if pd.isna(combined_text) or combined_text.strip() == "":
        return "Lainnya"
    
    # Daftar penerbit buku terkenal
    book_publishers = ['nuansa aulia', 'citra aditya bakti', 'yrama widya', 
                      'pustaka belajar', 'pustaka pelajar', 'erlangga', 
                      'andpublisher', 'prenadamedia', 'gramedia', 'grasindo',
                      'media', 'prenhalindo', 'prenhallindo', 'wiley', 'springer']
    
    # Deteksi penerbit buku
    if any(pub in combined_text for pub in book_publishers):
        return "Buku/Bab Buku"
    
    # Prioritas untuk buku jika ada kata "edisi"
    if 'edisi' in combined_text:
        return "Buku/Bab Buku"
    
    # Deteksi jurnal
    if any(keyword in combined_text for keyword in ['jurnal', 'journal', 'jou.', 'j.', 'acta']):
        return "Jurnal"
    
    # Deteksi prosiding konferensi
    if any(keyword in combined_text for keyword in ['prosiding', 'proceedings', 'proc.', 'konferensi', 'conference', 
                                                   'conf.', 'simposium', 'symposium', 'workshop', 'pertemuan', 'meeting']):
        return "Prosiding Konferensi"
    
    # Deteksi buku
    if any(keyword in combined_text for keyword in ['buku', 'book', 'bab buku', 'chapter', 'handbook', 'ensiklopedia', 
                                                   'encyclopedia', 'buku teks', 'textbook', 'penerbit', 'publisher', 'press', 
                                                   'books']):
        return "Buku/Bab Buku"
    
    # Deteksi tesis/disertasi
    if any(keyword in combined_text for keyword in ['tesis', 'thesis', 'disertasi', 'dissertation', 'skripsi', 'program doktor',
                                                   'program pascasarjana', 'phd', 'master', 'doctoral', 'program studi', 'fakultas']):
        return "Tesis/Disertasi"
    
    # Deteksi laporan penelitian
    if any(keyword in combined_text for keyword in ['analisis', 'analysis', 'penelitian', 'research']):
        return "Laporan Penelitian"
    
    # Deteksi preprint/laporan teknis
    if any(keyword in combined_text for keyword in ['arxiv', 'preprint', 'laporan teknis', 'technical report', 
                                                   'naskah awal', 'working paper', 'teknis']):
        return "Preprint/Laporan Teknis"
    
    # Deteksi paten
    if 'paten' in combined_text or 'patent' in combined_text:
        return "Paten"
    
    # Deteksi referensi hukum/undang-undang
    if re.search(r'\bUU\s*No\.\s*\d+|Undang-undang\s*Nomor\s*\d+|Peraturan\s*(Pemerintah|Presiden)\s*No\.\s*\d+', 
                combined_text):
        return "Buku/Bab Buku"
    
    # Deteksi berdasarkan format volume/issue
    if re.search(r'vol\.|\bvol\b|\bedisi\b|\bno\.|\bhal\.|\bhalaman\b', combined_text) or \
       re.search(r'\bvol\.\s*\d+\s*(\(\s*\d+\s*\))?', combined_text) or \
       re.search(r'\d+\s*\(\d+\)', combined_text):
        return "Jurnal"
    
    return "Lainnya"

def extract_vol_no(venue_text, title=""):
    """Extract volume and issue information - kept for backward compatibility"""
    def clean_text(text):
        """Clean and normalize text for processing"""
        if not isinstance(text, str):
            return ""
        return re.sub(r'\s+', ' ', text.strip())
    
    def convert_roman(roman_str):
        """Convert Roman numerals to integers with validation"""
        roman_str = roman_str.upper()
        valid_chars = {'I', 'V', 'X', 'L', 'C', 'D', 'M'}
        
        if not all(c in valid_chars for c in roman_str):
            return None
        
        try:
            return str(fromRoman(roman_str))
        except:
            return None

    # Clean input texts
    search_text = clean_text(venue_text)
    title_text = clean_text(title)
    combined_text = f"{search_text} {title_text}".lower()

    # Skip Legal Documents and Special Cases
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

    # Handle Standard Journal Format
    journal_format = re.search(r'(\d+)\s*\(\s*(\d+)\s*\)', search_text)
    if journal_format:
        return journal_format.group(1), journal_format.group(2)

    # Skip Page Numbers and Publication Years
    if re.search(r'\b\d+\s*-\s*\d+\b', search_text):  # Format halaman
        return "", ""
    
    year_pattern = r'(?:19|20)\d{2}'  # Skip tahun

    # Primary Patterns - Standard Volume/Number
    def extract_standard_format(text):
        """Extract standard vol/no formats"""
        # Pattern 1: Vol. X No. Y
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
        
        # Pattern 2: Volume X, Number Y
        vol_num = re.search(
            r'(?<!\S)volume\s*(\d+).*?number\s*(\d+)', 
            text, re.IGNORECASE
        )
        if vol_num:
            return vol_num.group(1), vol_num.group(2)
        
        return None, None

    # Try from venue first
    vol, no = extract_standard_format(search_text)
    if vol or no:
        return vol, no

    # Try from title if not found in venue
    if title_text:
        vol, no = extract_standard_format(title_text)
        if vol or no:
            return vol, no

    # Fallback - Isolated Numbers
    def find_isolated_numbers(text):
        """Find potential volume/number pairs"""
        numbers = [n for n in re.findall(r'\b\d+\b', text) 
                 if not re.match(year_pattern, n) and int(n) < 1000]
        
        if len(numbers) >= 2:
            return numbers[0], numbers[1]
        elif numbers:
            return "", numbers[0]  # Single number as No
        return "", ""

    # Check venue
    vol, no = find_isolated_numbers(search_text)
    if no:
        return vol, no

    # Check title
    if title_text:
        vol, no = find_isolated_numbers(title_text)
        if no:
            return vol, no

    return "", ""  # Default return

def extract_pages(venue_text, title=""):
    """Ekstrak informasi halaman (pages) dari venue atau title"""
    if not isinstance(venue_text, str) and not isinstance(title, str):
        return ""
    
    # Bersihkan teks input
    venue_text = re.sub(r'\s+', ' ', str(venue_text).strip().lower())
    title_text = re.sub(r'\s+', ' ', str(title).strip().lower())
    combined_text = f"{venue_text} {title_text}"
    
    # Pattern 1: pp. X-Y atau pages X-Y
    pages_pattern1 = re.search(r'(?:pp\.?|pages?|halaman)\s*(\d+)\s*[-–—]\s*(\d+)', combined_text, re.IGNORECASE)
    if pages_pattern1:
        return f"{pages_pattern1.group(1)}-{pages_pattern1.group(2)}"
    
    # Pattern 2: p. X atau page X (single page)
    pages_pattern2 = re.search(r'(?:p\.?|page|halaman)\s*(\d+)(?:\s|$|,|\.)', combined_text, re.IGNORECASE)
    if pages_pattern2:
        return pages_pattern2.group(1)
    
    # Pattern 3: Isolated page range (X-Y) at the end of venue
    pages_pattern3 = re.search(r'[^\d]+(\d+)\s*[-–—]\s*(\d+)\s*$', venue_text)
    if pages_pattern3:
        # Pastikan bukan tahun atau volume-issue
        start_page = int(pages_pattern3.group(1))
        end_page = int(pages_pattern3.group(2))
        if end_page > start_page and start_page > 0 and end_page < 2000:
            return f"{start_page}-{end_page}"
    
    # Pattern 4: Isolated page range in parentheses
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
        # Data dasar publikasi dengan nama kolom yang diubah
        base_data = {
            'judul': pub.get('title', ''),
            'author': pub.get('authors', ''),
            'tahun_publikasi': pub.get('year', 'N/A'),
            'journal': pub.get('journal', 'N/A'),      # Ganti venue dengan journal
            'conference': pub.get('conference', 'N/A'), # Tambah conference
            'publisher': pub.get('publisher', ''),      # Publisher selalu ada
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
        
        # Ekstrak volume dan issue menggunakan regex hanya jika tidak tersedia dari halaman detail
        if not base_data['volume'] or not base_data['issue']:
            # Gunakan journal atau conference sebagai sumber untuk ekstraksi volume/issue
            source_text = pub.get('journal', '') if pub.get('journal', 'N/A') != 'N/A' else pub.get('conference', '')
            vol, no = extract_vol_no(source_text, pub.get('title', ''))
            if not base_data['volume']:
                base_data['volume'] = vol
            if not base_data['issue']:
                base_data['issue'] = no
        
        # Ekstrak pages menggunakan regex hanya jika tidak tersedia dari halaman detail
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
    
    # Simpan data profil dengan citations_per_year
    profiles_df = pd.DataFrame(all_profiles)
    
    if 'citations_per_year' in profiles_df.columns:
        citations_per_year_df = pd.json_normalize(profiles_df['citations_per_year'])
        citations_per_year_df.columns = [f"Citations_{year}" for year in citations_per_year_df.columns]
        profiles_df = pd.concat([profiles_df.drop(columns=['citations_per_year']), citations_per_year_df], axis=1)
    
    profiles_df.to_csv(f"{filename}_profiles.csv", index=False, encoding='utf-8')
    
    # Transformasi data publikasi
    transformed_publications = transform_publications_data(all_publications)
    publications_df = pd.DataFrame(transformed_publications)
    
    # Simpan data publikasi yang sudah ditransformasi
    publications_df.to_csv(f"{filename}_publications.csv", index=False, encoding='utf-8')
    
    return current_date, profiles_df, publications_df

def main():
    try:
        # Gunakan login manual
        driver = setup_driver_with_manual_login()
        
        # Check if driver was successfully created
        if driver is None:
            print("Failed to create driver with manual login. Exiting.")
            return
        
        df = pd.read_csv('D:/Project/FinalWebProDS/frontend/dosen_unpar_gs.csv')
        all_profiles = []
        all_publications = []
        
        max_authors = 1  # Batasi jumlah profil yang di-scrape dalam satu sesi
        
        try:
            for index, row in df.head(max_authors).iterrows():
                author_name = row['Name']
                profile_url = row['Profile URL']  # Ambil Profile URL dari CSV
                print(f"Scraping data for {author_name}...")
                
                # Gunakan driver yang sudah login dengan profile URL langsung
                profile_data = scrape_google_scholar_profile_with_existing_driver(driver, profile_url, author_name)
                
                if profile_data:
                    print(f"Successfully retrieved data for {profile_data['name']}")
                    
                    profile_entry = {
                        'Name': profile_data['name'],  # Use 'Name' consistently
                        'Affiliation': profile_data['affiliation'],
                        'Profile URL': profile_data['profile_url'],      # Tambahkan Profile URL
                        'ID Google Scholar': profile_data['scholar_id'], # Tambahkan Scholar ID
                        **profile_data['citation_stats'],
                        'citations_per_year': profile_data['citations_per_year']
                    }
                    
                    all_profiles.append(profile_entry)
                    all_publications.extend(profile_data['publications'])
                else:
                    print(f"Failed to retrieve data for {author_name}")
                
                # Add a longer and more random delay between authors to avoid detection
                delay_time = random.uniform(60, 120)  # Random delay between 1-2 minutes
                print(f"Waiting for {delay_time:.1f} seconds before next author...")
                time.sleep(delay_time)
        finally:
            # Close the driver after all scraping is done
            if driver is not None:
                try:
                    driver.quit()
                    print("Driver closed successfully")
                except Exception as e:
                    print(f"Error closing driver: {e}")
        
        current_date, profiles_df, publications_df = save_to_csv(all_profiles, all_publications, 'all_dosen_data')
        
        print("Scraping selesai.")
        print(f"Kolom pada hasil CSV publikasi:")
        print(publications_df.columns.tolist())
    
    except Exception as e:
        print(f"Error in main function: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    main()