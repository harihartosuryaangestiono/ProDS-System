#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Mon Sep 22 11:23:34 2025

@author: rayhanadjisantoso
"""

import pandas as pd
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
import time

def get_all_unpar_scholars(max_pages=100):
    # Set up Chrome options for a more "human-like" session
    chrome_options = Options()
    chrome_options.add_argument("--no-sandbox")
    chrome_options.add_argument("--disable-dev-shm-usage")
    chrome_options.add_argument("user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36")
    
    # Initialize the WebDriver
    service = Service()
    driver = webdriver.Chrome(service=service, options=chrome_options)
    
    scholars = []
    search_queries = [
        "Universitas Katolik Parahyangan",
        "Parahyangan Catholic University",
        "unpar"
    ]

    try:
        # Navigate to the Google Scholar login page
        print("Mengarahkan Anda ke halaman Google Scholar. Silakan login dan selesaikan CAPTCHA secara manual di jendela browser yang terbuka.")
        driver.get("https://scholar.google.com/")
        
        # Wait for user confirmation
        input("Setelah Anda berhasil login, tekan ENTER di terminal ini untuk melanjutkan...")

        base_url = "https://scholar.google.com/citations?view_op=search_authors&mauthors={}&hl=en"
        
        for query in search_queries:
            page_count = 0
            url = base_url.format(query.replace(" ", "+"))
            driver.get(url)
            print(f"\nScraping dimulai untuk query: {query}")
            print(f"URL: {url}")
            
            while page_count < max_pages:
                print(f"Scraping halaman {page_count + 1} untuk query '{query}'...")
                
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
                        
                        scholars.append({
                            'Query': query,
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
                        print("Tombol 'Next' dinonaktifkan, mengakhiri scraping untuk query ini.")
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
    finally:
        driver.quit() # Ensure the browser closes
    
    return scholars

# Run the script
if __name__ == "__main__":
    print("Memulai scraping dosen Unpar dari Google Scholar menggunakan Selenium...")
    scholars_data = get_all_unpar_scholars(max_pages=100)
    
    if scholars_data:
        df = pd.DataFrame(scholars_data)

        # Simpan data mentah dulu (semua hasil, termasuk duplikat)
        df.to_csv("dosen_unpar_selenium_login_manual_raw.csv", index=False, encoding="utf-8")
        print("Data mentah (termasuk duplikasi) telah disimpan dalam 'dosen_unpar_selenium_login_manual_raw.csv'.")

        # Hapus duplikasi berdasarkan Profile URL (lebih unik dibanding hanya nama)
        df_unique = df.drop_duplicates(subset=["Profile URL"])
        df_unique.to_csv("dosen_unpar_selenium_login_manual_unique.csv", index=False, encoding="utf-8")
        print("Data unik (tanpa duplikasi) telah disimpan dalam 'dosen_unpar_selenium_login_manual_unique.csv'.")
    else:
        print("Tidak ada data ditemukan.")