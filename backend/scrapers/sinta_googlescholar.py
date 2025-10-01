# -*- coding: utf-8 -*-
"""
SINTA Google Scholar Publications Scraper - Updated for Correct Database Schema
Created on Tue May 20 07:40:01 2025

@author: harih
"""

import requests
from bs4 import BeautifulSoup
import pandas as pd
import csv
from time import sleep
import random
import os
from urllib.parse import urljoin
from datetime import datetime
import logging
import re
import psycopg2
from psycopg2 import sql

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler("sinta_scraper.log"),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger("SintaScraper")

class DatabaseManager:
    def __init__(self, dbname="ProDSGabungan", user="postgres", password="hari123", host="localhost", port="5432"):
        self.conn_params = {
            'dbname': dbname,
            'user': user,
            'password': password,
            'host': host,
            'port': port
        }
        self.connection = None
    
    def connect(self):
        """Establish a connection to the database"""
        try:
            self.connection = psycopg2.connect(**self.conn_params)
            logger.info("Connected to PostgreSQL database")
            return True
        except Exception as e:
            logger.error(f"Error connecting to database: {e}")
            return False
    
    def disconnect(self):
        """Close the database connection"""
        if self.connection:
            self.connection.close()
            logger.info("Disconnected from database")
    
    def get_dosen_id_by_sinta_id(self, sinta_id):
        """Get dosen ID from database using SINTA ID"""
        try:
            with self.connection.cursor() as cursor:
                cursor.execute("SELECT v_id_dosen, v_nama_dosen FROM tmp_dosen_dt WHERE v_id_sinta = %s", (sinta_id,))
                result = cursor.fetchone()
                if result:
                    return result[0], result[1]  # Return dosen_id and nama_dosen
                else:
                    logger.warning(f"Dosen with SINTA ID {sinta_id} not found in database")
                    return None, None
        except Exception as e:
            logger.error(f"Error getting dosen by SINTA ID: {e}")
            return None, None
    
    def get_or_create_jurnal_id(self, nama_jurnal):
        """Get or create jurnal ID"""
        try:
            with self.connection.cursor() as cursor:
                # Check if jurnal exists
                cursor.execute("SELECT v_id_jurnal FROM stg_jurnal_mt WHERE v_nama_jurnal = %s", (nama_jurnal,))
                result = cursor.fetchone()
                if result:
                    return result[0]
                
                # Create new jurnal
                cursor.execute(
                    "INSERT INTO stg_jurnal_mt (v_nama_jurnal) VALUES (%s) RETURNING v_id_jurnal",
                    (nama_jurnal,)
                )
                jurnal_id = cursor.fetchone()[0]
                self.connection.commit()
                logger.debug(f"Created new jurnal: {nama_jurnal} with ID: {jurnal_id}")
                return jurnal_id
                
        except Exception as e:
            self.connection.rollback()
            logger.error(f"Error managing jurnal: {e}")
            return None
    
    def get_or_create_publikasi_id(self, judul, jenis, tahun_publikasi, total_sitasi=0, sumber="Sinta_GoogleScholar", link_url=None):
        """Get or create publikasi ID"""
        try:
            with self.connection.cursor() as cursor:
                # Check if publikasi exists by title and year
                cursor.execute("""
                    SELECT v_id_publikasi FROM stg_publikasi_tr 
                    WHERE v_judul = %s AND v_tahun_publikasi = %s AND v_jenis = %s
                """, (judul, tahun_publikasi, jenis))
                result = cursor.fetchone()
                if result:
                    return result[0]
                
                # Create new publikasi
                cursor.execute("""
                    INSERT INTO stg_publikasi_tr (v_judul, v_jenis, v_tahun_publikasi, n_total_sitasi, v_sumber, v_link_url) 
                    VALUES (%s, %s, %s, %s, %s, %s) RETURNING v_id_publikasi
                """, (judul, jenis, tahun_publikasi, total_sitasi, sumber, link_url))
                publikasi_id = cursor.fetchone()[0]
                self.connection.commit()
                logger.debug(f"Created new publikasi: {judul[:50]}... with ID: {publikasi_id}")
                return publikasi_id
                
        except Exception as e:
            self.connection.rollback()
            logger.error(f"Error managing publikasi: {e}")
            return None
    
    def insert_artikel_details(self, publikasi_id, jurnal_id, volume, issue, pages, terindeks, ranking):
        """Insert artikel-specific details"""
        try:
            with self.connection.cursor() as cursor:
                # Check if artikel details already exist
                cursor.execute("SELECT v_id_publikasi FROM stg_artikel_dr WHERE v_id_publikasi = %s", (publikasi_id,))
                if cursor.fetchone():
                    # Update existing artikel details
                    cursor.execute("""
                        UPDATE stg_artikel_dr SET 
                            v_id_jurnal = %s, v_volume = %s, v_issue = %s, v_pages = %s,
                            v_terindeks = %s, v_ranking = %s
                        WHERE v_id_publikasi = %s
                    """, (jurnal_id, volume, issue, pages, terindeks, ranking, publikasi_id))
                else:
                    # Insert new artikel details
                    cursor.execute("""
                        INSERT INTO stg_artikel_dr (v_id_publikasi, v_id_jurnal, v_volume, v_issue, v_pages, v_terindeks, v_ranking) 
                        VALUES (%s, %s, %s, %s, %s, %s, %s)
                    """, (publikasi_id, jurnal_id, volume, issue, pages, terindeks, ranking))
                
                self.connection.commit()
                return True
                
        except Exception as e:
            self.connection.rollback()
            logger.error(f"Error inserting artikel details: {e}")
            return False
    
    def link_publikasi_dosen(self, publikasi_id, dosen_id, author_order="1 out of 1"):
        """Link publikasi with dosen"""
        try:
            with self.connection.cursor() as cursor:
                # Check if link already exists
                cursor.execute("""
                    SELECT v_id_publikasi FROM stg_publikasi_dosen_dt 
                    WHERE v_id_publikasi = %s AND v_id_dosen = %s
                """, (publikasi_id, dosen_id))
                if cursor.fetchone():
                    # Update existing link
                    cursor.execute("""
                        UPDATE stg_publikasi_dosen_dt SET 
                            v_author_order = %s
                        WHERE v_id_publikasi = %s AND v_id_dosen = %s
                    """, (author_order, publikasi_id, dosen_id))
                else:
                    # Insert new link
                    cursor.execute("""
                        INSERT INTO stg_publikasi_dosen_dt (v_id_publikasi, v_id_dosen, v_author_order) 
                        VALUES (%s, %s, %s)
                    """, (publikasi_id, dosen_id, author_order))
                
                self.connection.commit()
                return True
                
        except Exception as e:
            self.connection.rollback()
            logger.error(f"Error linking publikasi with dosen: {e}")
            return False
    
    def insert_sitasi_tahunan(self, publikasi_id, tahun, total_sitasi, sumber="GoogleScholar", tanggal_unduh=None):
        """Insert annual citation data"""
        if tanggal_unduh is None:
            tanggal_unduh = datetime.now().date()
        
        try:
            with self.connection.cursor() as cursor:
                # Check if citation data already exists for this year
                cursor.execute("""
                    SELECT v_id_sitasi FROM stg_publikasi_sitasi_tahunan_dr 
                    WHERE v_id_publikasi = %s AND v_tahun = %s AND v_sumber = %s
                """, (publikasi_id, tahun, sumber))
                
                result = cursor.fetchone()
                if result:
                    # Update existing citation data
                    cursor.execute("""
                        UPDATE stg_publikasi_sitasi_tahunan_dr SET 
                            n_total_sitasi_tahun = %s, t_tanggal_unduh = %s
                        WHERE v_id_sitasi = %s
                    """, (total_sitasi, tanggal_unduh, result[0]))
                else:
                    # Insert new citation data
                    cursor.execute("""
                        INSERT INTO stg_publikasi_sitasi_tahunan_dr 
                        (v_id_publikasi, v_tahun, n_total_sitasi_tahun, v_sumber, t_tanggal_unduh) 
                        VALUES (%s, %s, %s, %s, %s)
                    """, (publikasi_id, tahun, total_sitasi, sumber, tanggal_unduh))
                
                self.connection.commit()
                return True
                
        except Exception as e:
            self.connection.rollback()
            logger.error(f"Error inserting citation data: {e}")
            return False
    
    def insert_publication_complete(self, pub_data):
        """Insert complete publication data with all related tables"""
        try:
            # Get dosen ID from database using SINTA ID
            dosen_id, author_name = self.get_dosen_id_by_sinta_id(pub_data['sinta_id'])
            if not dosen_id:
                logger.error(f"Dosen with SINTA ID {pub_data['sinta_id']} not found in database")
                return False
            
            # Get or create jurnal (extract journal name from venue)
            jurnal_name = self.extract_journal_name(pub_data['venue'])
            jurnal_id = self.get_or_create_jurnal_id(jurnal_name)
            if not jurnal_id:
                logger.error(f"Failed to create/get jurnal for {jurnal_name}")
                return False
            
            # Create publikasi dengan semua field yang diperlukan
            publikasi_id = self.get_or_create_publikasi_id(
                judul=pub_data['judul'],
                jenis=pub_data['publication_type'],
                tahun_publikasi=pub_data['tahun_publikasi'],
                total_sitasi=pub_data['total_sitasi_seluruhnya'],
                sumber='Sinta_GoogleScholar',
                link_url=pub_data.get('link_url')
            )
            if not publikasi_id:
                logger.error(f"Failed to create/get publikasi for {pub_data['judul']}")
                return False
            
            # Insert artikel-specific details
            if pub_data['publication_type'] == 'artikel':
                if not self.insert_artikel_details(
                    publikasi_id, jurnal_id, 
                    pub_data['volume'], pub_data['issue'], pub_data['pages'],
                    pub_data.get('terindeks', 'GoogleScholar'), 
                    pub_data.get('ranking', 'N/A')
                ):
                    logger.error(f"Failed to insert artikel details")
                    return False
            
            # Link publikasi with dosen
            author_order = self.extract_author_order(pub_data['all_authors'], author_name)
            if not self.link_publikasi_dosen(publikasi_id, dosen_id, author_order):
                logger.error(f"Failed to link publikasi with dosen")
                return False
            
            # Insert citation data for current year
            if pub_data['total_sitasi_seluruhnya'] > 0:
                current_year = datetime.now().year
                if not self.insert_sitasi_tahunan(
                    publikasi_id, 
                    pub_data['tahun_publikasi'],  # Use publication year instead of current year
                    pub_data['total_sitasi_seluruhnya'], 
                    'GoogleScholar', 
                    datetime.strptime(pub_data['tanggal_unduh'], '%Y-%m-%d').date() if isinstance(pub_data['tanggal_unduh'], str) else pub_data['tanggal_unduh']
                ):
                    logger.error(f"Failed to insert citation data")
                    return False
            
            logger.debug(f"Successfully inserted publication: {pub_data['judul'][:50]}...")
            return True
            
        except Exception as e:
            logger.error(f"Error inserting complete publication data: {e}")
            return False
    
    def extract_journal_name(self, venue_text):
        """Extract journal name from venue text"""
        if not venue_text or venue_text == "N/A":
            return "Unknown Journal"
        
        # Remove common patterns that are not part of journal name
        # Remove year at the end
        venue_clean = re.sub(r',?\s*\d{4}$', '', venue_text)
        
        # Remove volume/issue/page patterns
        venue_clean = re.sub(r'\s+\d+\s*\(\d+\).*$', '', venue_clean)
        venue_clean = re.sub(r',\s*\d+[-–]\d+.*$', '', venue_clean)
        venue_clean = re.sub(r',\s*pp?\.?\s*\d+[-–]\d+.*$', '', venue_clean, flags=re.IGNORECASE)
        
        # Remove trailing commas and whitespace
        venue_clean = venue_clean.strip().rstrip(',').strip()
        
        if not venue_clean:
            return "Unknown Journal"
        
        return venue_clean[:255]  # Limit to database field size
    
    def extract_author_order(self, all_authors_text, target_author):
        """Extract author order information"""
        # Simple implementation - just return position info
        authors = [a.strip() for a in all_authors_text.split(',')]
        total_authors = len(authors)
        
        # Try to find the target author position
        for i, author in enumerate(authors):
            if target_author.lower() in author.lower() or author.lower() in target_author.lower():
                return f"{i+1} out of {total_authors}"
        
        return f"1 out of {total_authors}"  # Default if not found
    
    def insert_publications_batch(self, publications):
        """Insert multiple publications efficiently"""
        inserted_count = 0
        
        for pub in publications:
            try:
                if self.insert_publication_complete(pub):
                    inserted_count += 1
            except Exception as e:
                logger.error(f"Error processing publication {pub.get('judul', 'Unknown')}: {e}")
                continue
        
        logger.info(f"Successfully processed {inserted_count} out of {len(publications)} publications")
        return inserted_count
    
    def get_all_authors(self):
        """Get all authors from tmp_dosen_dt table"""
        try:
            with self.connection.cursor() as cursor:
                cursor.execute("SELECT v_nama_dosen, v_id_sinta FROM tmp_dosen_dt WHERE v_id_sinta IS NOT NULL")
                authors = [{'name': row[0], 'id': row[1]} for row in cursor.fetchall()]
                return authors
        except Exception as e:
            logger.error(f"Error getting authors from database: {e}")
            return []
    
    def update_dosen_statistics(self, sinta_id):
        """Update dosen publication and citation statistics"""
        try:
            with self.connection.cursor() as cursor:
                # Get dosen ID
                cursor.execute("SELECT v_id_dosen FROM tmp_dosen_dt WHERE v_id_sinta = %s", (sinta_id,))
                result = cursor.fetchone()
                if not result:
                    return False
                
                dosen_id = result[0]
                
                # Count total publications
                cursor.execute("""
                    SELECT COUNT(*) FROM stg_publikasi_dosen_dt pd
                    JOIN stg_publikasi_tr p ON pd.v_id_publikasi = p.v_id_publikasi
                    WHERE pd.v_id_dosen = %s
                """, (dosen_id,))
                total_publikasi = cursor.fetchone()[0]
                
                # Sum total citations
                cursor.execute("""
                    SELECT COALESCE(SUM(p.n_total_sitasi), 0) FROM stg_publikasi_dosen_dt pd
                    JOIN stg_publikasi_tr p ON pd.v_id_publikasi = p.v_id_publikasi
                    WHERE pd.v_id_dosen = %s
                """, (dosen_id,))
                total_sitasi = cursor.fetchone()[0]
                
                # Update dosen statistics
                cursor.execute("""
                    UPDATE tmp_dosen_dt SET 
                        n_total_publikasi = %s,
                        n_total_sitasi_gs = %s
                    WHERE v_id_dosen = %s
                """, (total_publikasi, total_sitasi, dosen_id))
                
                self.connection.commit()
                logger.info(f"Updated statistics for dosen ID {dosen_id}: {total_publikasi} publications, {total_sitasi} citations")
                return True
                
        except Exception as e:
            self.connection.rollback()
            logger.error(f"Error updating dosen statistics: {e}")
            return False

class SintaScraper:
    def __init__(self, db_manager=None):
        self.session = requests.Session()
        self.headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
            'Accept-Language': 'en-US,en;q=0.5',
            'DNT': '1',
            'Connection': 'keep-alive',
            'Upgrade-Insecure-Requests': '1',
        }
        self.logged_in = False
        self.today = datetime.now().strftime("%Y-%m-%d")
        self.username = None
        self.password = None
        self.db = db_manager
    
    def login(self, username, password):
        """Login to SINTA before scraping - tries multiple login endpoints"""
        self.username = username
        self.password = password
            
        # Try the general login endpoint
        if self._try_login("https://sinta.kemdikbud.go.id/logins"):
            return True
            
        logger.error("All login attempts failed")
        return False
        
    def _try_login(self, login_url):
        """Try to log in using a specific endpoint"""
        logger.info(f"Attempting login at: {login_url}")
        
        try:
            # Get the login page to retrieve CSRF tokens and understand form structure
            response = self.session.get(login_url, headers=self.headers)
            response.raise_for_status()
            
            soup = BeautifulSoup(response.text, 'html.parser')
            
            # Find all input fields to understand the form structure
            form_inputs = soup.find_all('input')
            logger.info(f"Found {len(form_inputs)} input fields on login form")
            
            # Extract CSRF token if present
            csrf_token = soup.find('input', {'name': '_token'})
            
            # Find the actual form and its action URL
            form = soup.find('form', {'id': 'loginform'}) or soup.find('form', {'method': 'post'}) or soup.find('form', {'action': True})
            
            post_url = login_url
            if form and form.has_attr('action'):
                # Use the form's action URL if available
                post_url = urljoin(login_url, form['action'])
                logger.info(f"Found form action URL: {post_url}")
            
            # Prepare login data - try both email and username fields
            login_data = {}
            
            # Add all non-hidden inputs from the form
            if form:
                for input_tag in form.find_all('input'):
                    if input_tag.has_attr('name') and input_tag.has_attr('value') and input_tag.get('type') != 'submit':
                        if input_tag['type'] != 'hidden':
                            continue
                        login_data[input_tag['name']] = input_tag['value']
            
            # Add credentials - try both common field names
            email_field = soup.find('input', {'type': 'email'}) or soup.find('input', {'name': 'email'})
            username_field = soup.find('input', {'name': 'username'})
            
            if email_field and email_field.has_attr('name'):
                login_data[email_field['name']] = self.username
                logger.info(f"Using email field: {email_field['name']}")
            elif username_field and username_field.has_attr('name'):
                login_data[username_field['name']] = self.username
                logger.info(f"Using username field: {username_field['name']}")
            else:
                # Try both common field names if we couldn't detect
                login_data['email'] = self.username
                login_data['username'] = self.username
            
            # Add password
            password_field = soup.find('input', {'type': 'password'})
            if password_field and password_field.has_attr('name'):
                login_data[password_field['name']] = self.password
            else:
                login_data['password'] = self.password
            
            # Add CSRF token if found
            if csrf_token:
                login_data['_token'] = csrf_token['value']
                logger.info("CSRF token found and added to request")
            
            # Add submit button data if available
            submit_button = soup.find('button', {'type': 'submit'}) or soup.find('input', {'type': 'submit'})
            if submit_button:
                if submit_button.has_attr('name') and submit_button.has_attr('value'):
                    login_data[submit_button['name']] = submit_button['value']
                    logger.info(f"Added submit button data: {submit_button['name']}={submit_button['value']}")
                elif submit_button.has_attr('name'):
                    login_data[submit_button['name']] = "Login"
            
            # Add remember me option
            login_data['remember'] = 'on'
            
            # Additional fields sometimes needed
            login_data['login'] = 'Login'
            
            # Set additional headers that might be expected by the server
            login_headers = self.headers.copy()
            login_headers['Referer'] = login_url
            login_headers['Origin'] = 'https://sinta.kemdikbud.go.id'
            login_headers['Content-Type'] = 'application/x-www-form-urlencoded'
            
            logger.info(f"Login data prepared: {login_data}")
            logger.info(f"Posting to: {post_url}")
            
            # Perform login
            response = self.session.post(
                post_url, 
                data=login_data, 
                headers=login_headers, 
                allow_redirects=True
            )
            response.raise_for_status()
            
            # Check if login was successful
            success_indicators = ["dashboard", "authors/profile"]
            failure_indicators = ["logins", "login", "signin", "sign-in"]
            
            if any(indicator in response.url for indicator in success_indicators) or \
               not any(indicator in response.url for indicator in failure_indicators):
                self.logged_in = True
                logger.info(f"Login successful! Redirected to: {response.url}")
                return True
            else:
                logger.warning(f"Login attempt failed. Current URL: {response.url}")
                
                # Debug: Check for error messages
                error_soup = BeautifulSoup(response.text, 'html.parser')
                error_msg = error_soup.find('div', class_='alert-danger') or error_soup.find('div', class_='invalid-feedback')
                if error_msg:
                    logger.warning(f"Error message: {error_msg.text.strip()}")
                
                return False
                
        except Exception as e:
            logger.error(f"Login error at {login_url}: {e}")
            return False

    def check_login_status(self):
        """Check if still logged in by visiting dashboard page"""
        try:
            logger.info("Checking login status...")
            response = self.session.get("https://sinta.kemdikbud.go.id/dashboard", headers=self.headers)
            is_logged_in = "dashboard" in response.url or "authors/profile" in response.url
            logger.info(f"Login status check: {'Logged in' if is_logged_in else 'Not logged in'}")
            return is_logged_in
        except Exception as e:
            logger.error(f"Error checking login status: {e}")
            return False
    
    def relogin_if_needed(self):
        """Check login status and relogin if needed"""
        if not self.check_login_status() and self.username and self.password:
            logger.info("Session expired. Attempting to relogin...")
            return self.login(self.username, self.password)
        return self.logged_in

    def scrape_author_publications(self, author_id, author_name):
        """Scrape all Google Scholar publications for an author, handling pagination properly"""
        if not self.logged_in:
            logger.warning("Not logged in. Some pages may not be accessible.")
            # Try to check login status and relogin if needed
            self.relogin_if_needed()
        
        base_url = f"https://sinta.kemdikbud.go.id/authors/profile/{author_id}/"
        initial_url = base_url + "?view=googlescholar"
        all_publications = []
        
        # First, determine total number of pages
        try:
            logger.info(f"Checking pagination for {author_name} (ID: {author_id})")
            response = self.session.get(initial_url, headers=self.headers)
            response.raise_for_status()
            
            if "login" in response.url and self.logged_in:
                logger.warning("Session expired during initial page check.")
                if not self.relogin_if_needed():
                    logger.error("Relogin failed. Stopping scraping for this author.")
                    return all_publications
                
                # Retry after relogin
                response = self.session.get(initial_url, headers=self.headers)
                response.raise_for_status()
            
            soup = BeautifulSoup(response.text, 'html.parser')
            
            # Find pagination links to determine total pages
            pagination = soup.find('ul', class_='pagination')
            total_pages = 1  # Default to 1 if no pagination found
            
            if pagination:
                # Get all page number links
                page_links = pagination.find_all('a', class_='page-link')
                page_numbers = []
                
                for link in page_links:
                    # Extract page numbers, skipping "Previous" and "Next" links
                    link_text = link.get_text().strip()
                    if link_text.isdigit():
                        page_numbers.append(int(link_text))
                
                if page_numbers:
                    total_pages = max(page_numbers)
            
            logger.info(f"Found {total_pages} page(s) of publications for {author_name}")
            
            # Now, process each page sequentially
            for page_num in range(1, total_pages + 1):
                page_url = f"{base_url}?page={page_num}&view=googlescholar"
                logger.info(f"Scraping page {page_num}/{total_pages} for {author_name} (ID: {author_id})")
                
                try:
                    # If not the first page, make a new request
                    if page_num > 1:
                        response = self.session.get(page_url, headers=self.headers)
                        response.raise_for_status()
                        
                        if "login" in response.url and self.logged_in:
                            logger.warning(f"Session expired on page {page_num}.")
                            if not self.relogin_if_needed():
                                logger.error("Relogin failed. Stopping at current page.")
                                break
                            
                            # Retry after relogin
                            response = self.session.get(page_url, headers=self.headers)
                            response.raise_for_status()
                        
                        soup = BeautifulSoup(response.text, 'html.parser')
                    
                    # For first page, we already have the soup from pagination check
                    
                    # Check if we're actually viewing publications
                    main_content = soup.find('div', class_='main-content')
                    if not main_content:
                        logger.warning(f"Main content area not found on page {page_num} - possible site structure change")
                    
                    # Look for publication items
                    pub_items = soup.find_all('div', class_='ar-list-item')
                    if not pub_items:
                        logger.warning(f"No publication items found on page {page_num}. Possible structure change or no data available.")
                    
                    # Scrape publications from current page
                    publications = self.scrape_page(soup, author_id, author_name)
                    all_publications.extend(publications)
                    
                    logger.info(f"Found {len(publications)} publications on page {page_num}")
                    
                    # Add delay between page requests if not the last page
                    if page_num < total_pages:
                        delay = random.uniform(2, 4)
                        logger.info(f"Waiting {delay:.2f} seconds before next page...")
                        sleep(delay)
                        
                except Exception as e:
                    logger.error(f"Error scraping page {page_num} for author {author_id}: {e}")
                    break
            
        except Exception as e:
            logger.error(f"Error determining pagination for author {author_id}: {e}")
        
        logger.info(f"Finished scraping for {author_name}. Total publications: {len(all_publications)}")
        return all_publications

    def scrape_page(self, soup, author_id, author_name):
        """Scrape publications from a single page"""
        publications = []
        pub_items = soup.find_all('div', class_='ar-list-item')
        
        for item in pub_items:
            try:
                # Title and URL
                title_link = item.find('a', href=lambda x: x and 'scholar.google.com/scholar' in x)
                title = title_link.text.strip() if title_link else "N/A"
                link_url = title_link['href'] if title_link else None
                
                # Authors - get all authors text
                authors_elem = item.find('div', class_='ar-authors')
                all_authors_text = authors_elem.text.strip() if authors_elem else author_name
                
                # Year
                year_elem = item.find('a', class_='ar-year')
                year = year_elem.text.strip() if year_elem else "N/A"
                
                # Venue
                venue_elem = item.find('a', class_='ar-pub')
                venue = venue_elem.text.strip() if venue_elem else "N/A"
                
                # Citations
                citations_elem = item.find('a', class_='ar-cited')
                total_citations = citations_elem.text.strip().replace('cited', '').strip() if citations_elem else "0"
                
                # Extract volume, issue, pages from venue info
                venue_text = venue if venue != "N/A" else ""
                volume = "N/A"
                issue = "N/A"
                pages = "N/A"
                terindeks = "GoogleScholar"  # Default indexing source
                ranking = "N/A"  # Google Scholar doesn't provide quartile rankings
                
                # Improved regex patterns for parsing venue text
                if venue_text:
                    # Pattern 1: "Journal Name Volume (Issue), Pages, Year"
                    # Example: "Jurnal Ilmiah Manajemen, Ekonomi, & Akuntansi (MEA) 9 (1), 2939-2952, 2025"
                    pattern1 = re.search(r'(\d+)\s*\((\d+)\),\s*([\d-]+)', venue_text)
                    if pattern1:
                        volume = pattern1.group(1)
                        issue = pattern1.group(2)
                        pages = pattern1.group(3)
                    else:
                        # Pattern 2: "Vol. X, Issue Y, pp. Z-W" or "Vol. X, No. Y, pp. Z-W"
                        vol_match = re.search(r'Vol\.?\s*(\d+)', venue_text, re.IGNORECASE)
                        issue_match = re.search(r'(?:Issue|No\.?)\s*(\d+)', venue_text, re.IGNORECASE)
                        pages_match = re.search(r'pp\.?\s*([\d-]+)', venue_text, re.IGNORECASE)
                        
                        if vol_match:
                            volume = vol_match.group(1)
                        if issue_match:
                            issue = issue_match.group(1)
                        if pages_match:
                            pages = pages_match.group(1)
                        else:
                            # Pattern 3: Try to find pages without "pp." prefix
                            # Look for pattern like "123-456" or "123–456" (em dash)
                            pages_only = re.search(r'(\d+[-–]\d+)', venue_text)
                            if pages_only:
                                pages = pages_only.group(1)
                    
                    # Additional patterns for edge cases
                    if volume == "N/A" or issue == "N/A" or pages == "N/A":
                        # Pattern 4: "Volume(Issue)" without comma
                        # Example: "Journal Name 15(3) 234-245"
                        pattern4 = re.search(r'(\d+)\((\d+)\)', venue_text)
                        if pattern4:
                            if volume == "N/A":
                                volume = pattern4.group(1)
                            if issue == "N/A":
                                issue = pattern4.group(2)
                        
                        # Pattern 5: Just volume and pages
                        # Example: "Journal Name 15, 234-245"
                        if volume == "N/A":
                            vol_only = re.search(r'(?:^|[^\d])(\d+)(?:,|\s)', venue_text)
                            if vol_only:
                                volume = vol_only.group(1)
                        
                        # Pattern 6: Issue in parentheses without volume
                        # Example: "Journal Name (3), 234-245"
                        if issue == "N/A":
                            issue_only = re.search(r'\((\d+)\)', venue_text)
                            if issue_only:
                                issue = issue_only.group(1)
                        
                        # Pattern 7: Pages at the end of string
                        # Example: "Journal Name, 2023, 234-245"
                        if pages == "N/A":
                            pages_end = re.search(r'(\d+[-–]\d+)(?:,?\s*\d{4})?', venue_text)
                            if pages_end:
                                pages = pages_end.group(1)
                
                pub_data = {
                    'sinta_id': author_id,
                    'judul': title,
                    'author': author_name,  # Target author name
                    'all_authors': all_authors_text,  # All authors for order calculation
                    'tahun_publikasi': int(year) if year.isdigit() else datetime.now().year,
                    'venue': venue,
                    'publication_type': "artikel",  # Default for Google Scholar
                    'volume': volume,
                    'issue': issue,
                    'pages': pages,
                    'terindeks': terindeks,
                    'ranking': ranking,
                    'publisher': "N/A",  # Google Scholar doesn't provide this
                    'total_sitasi_seluruhnya': int(total_citations) if total_citations.isdigit() else 0,
                    'total_sitasi_tahun': 0,  # Default to 0 as we don't have this info
                    'sumber': 'Sinta_GoogleScholar',
                    'tanggal_unduh': self.today,
                    'link_url': link_url
                }
                
                publications.append(pub_data)
                
            except Exception as e:
                logger.error(f"Error processing publication: {e}")
                continue
                
        return publications

def process_single_author(scraper, author_id, author_name):
    """Process a single author and save to database"""
    logger.info(f"Processing author: {author_name} (ID: {author_id})")
    
    try:
        publications = scraper.scrape_author_publications(author_id, author_name)
        if publications:
            # Insert publications into database
            inserted_count = scraper.db.insert_publications_batch(publications)
            
            # Update dosen statistics after inserting publications
            scraper.db.update_dosen_statistics(author_id)
            
            logger.info(f"Saved {inserted_count} publications for {author_name}")
            return inserted_count
        else:
            logger.info(f"No publications found for {author_name}")
            return 0
            
    except Exception as e:
        logger.error(f"Error processing author {author_name}: {e}")
        return 0

def main():
    # Initialize database connection
    db_manager = DatabaseManager()
    if not db_manager.connect():
        logger.error("Failed to connect to database. Exiting.")
        return
    
    # Initialize scraper
    scraper = SintaScraper(db_manager)
    
    # Get login credentials from environment or user input
    username = os.getenv('6182101045@student.unpar.ac.id')
    password = os.getenv('PAPAganteng1_')
    
    if not username or not password:
        logger.info("Please enter your SINTA credentials:")
        username = input("Username/Email: ").strip()
        password = input("Password: ").strip()
    
    # Login to SINTA
    if not scraper.login(username, password):
        logger.error("Login failed. Exiting.")
        return
    
    # Get all authors from database
    authors = db_manager.get_all_authors()
    if not authors:
        logger.error("No authors found in database. Exiting.")
        return
    
    logger.info(f"Found {len(authors)} authors in database")
    
    total_processed = 0
    total_publications = 0
    
    for author in authors:
        author_id = author['id']
        author_name = author['name']
        
        # Process each author
        pub_count = process_single_author(scraper, author_id, author_name)
        total_publications += pub_count
        total_processed += 1
        
        # Add delay between authors
        if total_processed < len(authors):
            delay = random.uniform(5, 10)
            logger.info(f"Waiting {delay:.2f} seconds before next author...")
            sleep(delay)
    
    logger.info(f"Processing complete! Processed {total_processed} authors, found {total_publications} total publications")
    
    # Close database connection
    db_manager.disconnect()

if __name__ == "__main__":
    main()