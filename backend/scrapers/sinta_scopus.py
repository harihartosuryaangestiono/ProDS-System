import requests
from bs4 import BeautifulSoup
import pandas as pd
import psycopg2
from psycopg2 import sql
from time import sleep
import random
import logging
import re
from datetime import datetime
from urllib.parse import urljoin
import csv
import os

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
    def __init__(self, dbname, user, password, host, port):
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
            logger.info("Connected to PostgreSQL Database")
            return True
        except Exception as e:
            logger.error(f"Error connecting to database: {e}")
            return False
    
    def disconnect(self):
        """Close the database connection"""
        if self.connection:
            self.connection.close()
            logger.info("Disconnected from database")
    
    def get_dosen_id_by_sinta(self, sinta_id):
        """Get dosen ID from database using Sinta ID"""
        try:
            with self.connection.cursor() as cursor:
                query = "SELECT v_id_dosen FROM tmp_dosen_dt WHERE v_id_sinta = %s"
                cursor.execute(query, (str(sinta_id),))
                result = cursor.fetchone()
                
                if result:
                    return result[0]
                else:
                    logger.warning(f"No dosen found with Sinta ID: {sinta_id}")
                    return None
                    
        except Exception as e:
            logger.error(f"Error getting dosen ID by Sinta ID {sinta_id}: {e}")
            return None
    
    def get_or_create_jurusan(self, nama_jurusan):
        """Get or create jurusan record"""
        try:
            with self.connection.cursor() as cursor:
                # Check if exists
                query = "SELECT v_id_jurusan FROM stg_jurusan_mt WHERE v_nama_jurusan = %s"
                cursor.execute(query, (nama_jurusan,))
                result = cursor.fetchone()
                
                if result:
                    return result[0]
                
                # Create new record
                insert_query = """
                    INSERT INTO stg_jurusan_mt (v_nama_jurusan) 
                    VALUES (%s) RETURNING v_id_jurusan
                """
                cursor.execute(insert_query, (nama_jurusan,))
                jurusan_id = cursor.fetchone()[0]
                self.connection.commit()
                logger.info(f"Created new jurusan: {nama_jurusan} with ID: {jurusan_id}")
                return jurusan_id
                
        except Exception as e:
            logger.error(f"Error getting/creating jurusan: {e}")
            self.connection.rollback()
            return None
    
    def get_or_create_jurnal(self, nama_jurnal):
        """Get or create jurnal record"""
        try:
            with self.connection.cursor() as cursor:
                # Check if exists
                query = "SELECT v_id_jurnal FROM stg_jurnal_mt WHERE v_nama_jurnal = %s"
                cursor.execute(query, (nama_jurnal,))
                result = cursor.fetchone()
                
                if result:
                    return result[0]
                
                # Create new record
                insert_query = """
                    INSERT INTO stg_jurnal_mt (v_nama_jurnal) 
                    VALUES (%s) RETURNING v_id_jurnal
                """
                cursor.execute(insert_query, (nama_jurnal,))
                jurnal_id = cursor.fetchone()[0]
                self.connection.commit()
                logger.info(f"Created new jurnal: {nama_jurnal} with ID: {jurnal_id}")
                return jurnal_id
                
        except Exception as e:
            logger.error(f"Error getting/creating jurnal: {e}")
            self.connection.rollback()
            return None
    
    def get_or_create_publikasi(self, judul, jenis, tahun_publikasi, total_sitasi=0, sumber="Sinta_Scopus", link_url=None):
        """Get or create publikasi record"""
        try:
            with self.connection.cursor() as cursor:
                # Check if exists
                query = """
                    SELECT v_id_publikasi FROM stg_publikasi_tr 
                    WHERE v_judul = %s AND v_jenis = %s AND v_tahun_publikasi = %s
                """
                cursor.execute(query, (judul, jenis, tahun_publikasi))
                result = cursor.fetchone()
                
                if result:
                    # Update citation count if higher
                    update_query = """
                        UPDATE stg_publikasi_tr SET n_total_sitasi = %s, v_link_url = %s
                        WHERE v_id_publikasi = %s AND n_total_sitasi < %s
                    """
                    cursor.execute(update_query, (total_sitasi, link_url, result[0], total_sitasi))
                    self.connection.commit()
                    return result[0]
                
                # Create new record
                insert_query = """
                    INSERT INTO stg_publikasi_tr (v_judul, v_jenis, v_tahun_publikasi, n_total_sitasi, v_sumber, v_link_url) 
                    VALUES (%s, %s, %s, %s, %s, %s) RETURNING v_id_publikasi
                """
                cursor.execute(insert_query, (judul, jenis, tahun_publikasi, total_sitasi, sumber, link_url))
                publikasi_id = cursor.fetchone()[0]
                self.connection.commit()
                logger.info(f"Created new publikasi: {judul[:50]}... with ID: {publikasi_id}")
                return publikasi_id
                
        except Exception as e:
            logger.error(f"Error getting/creating publikasi: {e}")
            self.connection.rollback()
            return None
    
    def create_artikel_details(self, publikasi_id, jurnal_id, volume=None, issue=None, pages=None, terindeks="Scopus", ranking=None):
        """Create artikel details record"""
        try:
            with self.connection.cursor() as cursor:
                # Check if already exists
                query = "SELECT v_id_publikasi FROM stg_artikel_dr WHERE v_id_publikasi = %s"
                cursor.execute(query, (publikasi_id,))
                if cursor.fetchone():
                    logger.debug(f"Artikel details already exist for publikasi ID: {publikasi_id}")
                    return True
                
                # Insert artikel details
                insert_query = """
                    INSERT INTO stg_artikel_dr (v_id_publikasi, v_id_jurnal, v_volume, v_issue, v_pages, v_terindeks, v_ranking) 
                    VALUES (%s, %s, %s, %s, %s, %s, %s)
                """
                cursor.execute(insert_query, (publikasi_id, jurnal_id, volume, issue, pages, terindeks, ranking))
                self.connection.commit()
                logger.debug(f"Created artikel details for publikasi ID: {publikasi_id}")
                return True
                
        except Exception as e:
            logger.error(f"Error creating artikel details: {e}")
            self.connection.rollback()
            return False
    
    def link_publikasi_dosen(self, publikasi_id, dosen_id, author_order=None):
        """Link publikasi to dosen"""
        try:
            with self.connection.cursor() as cursor:
                # Check if link already exists
                query = """
                    SELECT 1 FROM stg_publikasi_dosen_dt 
                    WHERE v_id_publikasi = %s AND v_id_dosen = %s
                """
                cursor.execute(query, (publikasi_id, dosen_id))
                if cursor.fetchone():
                    logger.debug(f"Link already exists between publikasi {publikasi_id} and dosen {dosen_id}")
                    return True
                
                # Create link
                insert_query = """
                    INSERT INTO stg_publikasi_dosen_dt (v_id_publikasi, v_id_dosen, v_author_order) 
                    VALUES (%s, %s, %s)
                """
                cursor.execute(insert_query, (publikasi_id, dosen_id, author_order))
                self.connection.commit()
                logger.debug(f"Linked publikasi {publikasi_id} to dosen {dosen_id}")
                return True
                
        except Exception as e:
            logger.error(f"Error linking publikasi to dosen: {e}")
            self.connection.rollback()
            return False
    
    def create_sitasi_tahunan(self, publikasi_id, tahun, total_sitasi, sumber="Sinta_Scopus"):
        """Create or update yearly citation record"""
        try:
            with self.connection.cursor() as cursor:
                # Check if record exists
                query = """
                    SELECT v_id_sitasi FROM stg_publikasi_sitasi_tahunan_dr 
                    WHERE v_id_publikasi = %s AND v_tahun = %s AND v_sumber = %s
                """
                cursor.execute(query, (publikasi_id, tahun, sumber))
                result = cursor.fetchone()
                
                if result:
                    # Update existing record
                    update_query = """
                        UPDATE stg_publikasi_sitasi_tahunan_dr 
                        SET n_total_sitasi_tahun = %s, t_tanggal_unduh = CURRENT_DATE
                        WHERE v_id_sitasi = %s
                    """
                    cursor.execute(update_query, (total_sitasi, result[0]))
                else:
                    # Create new record
                    insert_query = """
                        INSERT INTO stg_publikasi_sitasi_tahunan_dr 
                        (v_id_publikasi, v_tahun, n_total_sitasi_tahun, v_sumber) 
                        VALUES (%s, %s, %s, %s)
                    """
                    cursor.execute(insert_query, (publikasi_id, tahun, total_sitasi, sumber))
                
                self.connection.commit()
                return True
                
        except Exception as e:
            logger.error(f"Error creating/updating sitasi tahunan: {e}")
            self.connection.rollback()
            return False
    
    def process_publications_to_db(self, publications, sinta_id):
        """Process publications and insert into database"""
        if not publications:
            return 0
        
        inserted_count = 0
        
        # Get dosen ID from database using Sinta ID
        dosen_id = self.get_dosen_id_by_sinta(sinta_id)
        if not dosen_id:
            logger.error(f"No dosen found with Sinta ID: {sinta_id}. Cannot proceed.")
            return 0
        
        for pub in publications:
            try:
                # Get or create jurnal if venue is provided
                jurnal_id = None
                if pub.get('venue') and pub['venue'] != "N/A":
                    jurnal_id = self.get_or_create_jurnal(pub['venue'])
                
                # Get or create publikasi with link URL
                publikasi_id = self.get_or_create_publikasi(
                    pub['judul'],
                    'artikel',  # We're dealing with Scopus articles
                    pub.get('tahun_publikasi', datetime.now().year),
                    pub.get('total_sitasi_seluruhnya', 0),
                    'Sinta_Scopus',
                    pub.get('link_url')  # Add the publication URL
                )
                if not publikasi_id:
                    logger.error(f"Failed to create/get publikasi for {pub['judul'][:50]}...")
                    continue
                
                # Create artikel details if we have a jurnal
                if jurnal_id:
                    self.create_artikel_details(
                        publikasi_id, 
                        jurnal_id,
                        pub.get('volume'),
                        pub.get('issue'),
                        pub.get('pages'),
                        'Scopus',  # All publications from SINTA Scopus are indexed by Scopus
                        pub.get('ranking')
                    )
                
                # Link publikasi to dosen with author order
                author_order = pub.get('author_order', '1 out of 1')  # Default if not specified
                self.link_publikasi_dosen(publikasi_id, dosen_id, author_order)
                
                # Create yearly citation record for current year
                current_year = datetime.now().year
                self.create_sitasi_tahunan(
                    publikasi_id, 
                    current_year, 
                    pub.get('total_sitasi_seluruhnya', 0),
                    'Sinta_Scopus'
                )
                
                # Also create citation records for the publication year if different
                pub_year = pub.get('tahun_publikasi')
                if pub_year and pub_year != current_year and pub.get('total_sitasi_seluruhnya', 0) > 0:
                    self.create_sitasi_tahunan(
                        publikasi_id, 
                        pub_year, 
                        pub.get('total_sitasi_seluruhnya', 0),
                        'Sinta_Scopus'
                    )
                
                inserted_count += 1
                
            except Exception as e:
                logger.error(f"Error processing publication '{pub.get('judul', 'Unknown')}': {e}")
                continue
        
        logger.info(f"Successfully processed {inserted_count} publications to database")
        return inserted_count
    
    def get_all_authors_from_db(self):
        """Get all authors from the database"""
        try:
            with self.connection.cursor() as cursor:
                query = """
                    SELECT v_nama_dosen, v_id_sinta, v_id_dosen
                    FROM tmp_dosen_dt 
                    WHERE v_id_sinta IS NOT NULL AND v_id_sinta != ''
                """
                cursor.execute(query)
                authors = []
                for row in cursor.fetchall():
                    authors.append({
                        'name': row[0],
                        'id': row[1],  # SINTA ID
                        'db_id': row[2]  # Database internal ID
                    })
                return authors
        except Exception as e:
            logger.error(f"Error getting authors from database: {e}")
            return []

    def update_dosen_stats(self, sinta_id):
        """Update dosen publication and citation statistics using Sinta ID"""
        try:
            # Get dosen ID first
            dosen_id = self.get_dosen_id_by_sinta(sinta_id)
            if not dosen_id:
                logger.error(f"Cannot update stats - no dosen found with Sinta ID: {sinta_id}")
                return False
                
            with self.connection.cursor() as cursor:
                # Count publications
                pub_count_query = """
                    SELECT COUNT(*) FROM stg_publikasi_dosen_dt WHERE v_id_dosen = %s
                """
                cursor.execute(pub_count_query, (dosen_id,))
                pub_count = cursor.fetchone()[0]
                
                # Sum total citations
                citation_query = """
                    SELECT COALESCE(SUM(p.n_total_sitasi), 0)
                    FROM stg_publikasi_tr p
                    JOIN stg_publikasi_dosen_dt pd ON p.v_id_publikasi = pd.v_id_publikasi
                    WHERE pd.v_id_dosen = %s
                """
                cursor.execute(citation_query, (dosen_id,))
                total_citations = cursor.fetchone()[0]
                
                # Update dosen record
                update_query = """
                    UPDATE tmp_dosen_dt 
                    SET n_total_publikasi = %s, n_total_sitasi_gs = %s
                    WHERE v_id_dosen = %s
                """
                cursor.execute(update_query, (pub_count, total_citations, dosen_id))
                self.connection.commit()
                
                logger.info(f"Updated dosen {dosen_id} (Sinta ID: {sinta_id}): {pub_count} publications, {total_citations} citations")
                return True
                
        except Exception as e:
            logger.error(f"Error updating dosen stats for Sinta ID {sinta_id}: {e}")
            self.connection.rollback()
            return False


class SintaScraper:
    def __init__(self, db_manager):
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
            
        # If that fails, try the general login endpoint
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

    def extract_clean_author_name(self, author_html):
        """Extract only the author name from HTML formatted author string"""
        if not author_html:
            return "N/A"
            
        try:
            # Method 1: Use BeautifulSoup to parse HTML
            soup = BeautifulSoup(author_html, 'html.parser')
            text = soup.get_text().strip()
            
            # Remove "Creator : " prefix if present
            if "Creator : " in text:
                return text.replace("Creator : ", "").strip()
            
            # Method 2: Use regex as a fallback
            match = re.search(r'Creator\s*:\s*([^<]+)', author_html)
            if match:
                return match.group(1).strip()
                
            # If both methods fail, just return the stripped text
            return text
        except Exception as e:
            logger.error(f"Error extracting author name from {author_html}: {e}")
            return "N/A"
    
    def extract_clean_venue_name(self, venue_html):
        """Extract only the venue name from HTML formatted venue string"""
        if not venue_html or venue_html == "N/A":
            return "N/A"
            
        try:
            # Method 1: Use BeautifulSoup to parse HTML
            soup = BeautifulSoup(venue_html, 'html.parser')
            
            # Remove any icon elements (<i> tags)
            for icon in soup.find_all('i'):
                icon.decompose()
                
            # Get text content
            text = soup.get_text().strip()
            
            # Method 2: Use regex as a fallback
            if not text:
                match = re.search(r'</i>([^<]+)</a>', venue_html)
                if match:
                    return match.group(1).strip()
                
            return text
        except Exception as e:
            logger.error(f"Error extracting venue name from {venue_html}: {e}")
            return "N/A"

    def extract_publication_link(self, item):
        """Extract the publication URL from the item"""
        try:
            # Look for Scopus record link
            scopus_link = item.find('a', href=lambda x: x and 'scopus.com/record' in x)
            if scopus_link and scopus_link.has_attr('href'):
                return scopus_link['href']
            
            # Look for any other publication link
            pub_links = item.find_all('a', href=True)
            for link in pub_links:
                href = link['href']
                # Skip internal SINTA links
                if href.startswith('http') and 'sinta.kemdikbud.go.id' not in href:
                    return href
                    
            return None
        except Exception as e:
            logger.error(f"Error extracting publication link: {e}")
            return None

    def extract_author_order(self, item, target_author_name):
        """Extract author order information from publication"""
        try:
            # Look for author information in the publication
            authors_elem = item.find('div', class_='ar-authors')
            if not authors_elem:
                return "1 out of 1"  # Default if no author info found
            
            authors_text = authors_elem.get_text().strip()
            
            # Try to parse author order patterns like "John Doe, Jane Smith, Bob Jones"
            if ',' in authors_text:
                authors = [name.strip() for name in authors_text.split(',')]
                total_authors = len(authors)
                
                # Find the position of the target author
                for i, author in enumerate(authors):
                    if target_author_name.lower() in author.lower() or author.lower() in target_author_name.lower():
                        return f"{i + 1} out of {total_authors}"
                
                # If not found, assume first author
                return f"1 out of {total_authors}"
            else:
                # Single author case
                return "1 out of 1"
                
        except Exception as e:
            logger.error(f"Error extracting author order: {e}")
            return "1 out of 1"

    def scrape_author_publications(self, author_id, author_name):
        """Scrape all Scopus publications for an author, handling pagination properly"""
        if not self.logged_in:
            logger.warning("Not logged in. Some pages may not be accessible.")
            # Try to check login status and relogin if needed
            self.relogin_if_needed()
        
        base_url = f"https://sinta.kemdikbud.go.id/authors/profile/{author_id}/"
        initial_url = base_url + "?view=scopus"
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
                page_url = f"{base_url}?page={page_num}&view=scopus"
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
                # Title
                title_link = item.find('a', href=lambda x: x and 'scopus.com/record' in x)
                title = title_link.text.strip() if title_link else "N/A"
                
                # Extract publication link URL
                link_url = self.extract_publication_link(item)
                
                # Quartile ranking (venue quality indicator)
                quartile = item.find('a', class_='ar-quartile')
                quartile_text = quartile.text.strip() if quartile else "N/A"
                
                # Extract ranking information (e.g. "Q2 as Journal")
                ranking = "N/A"
                if quartile:
                    # Parse the full ranking text which is like "Q2 as Journal"
                    ranking_text = quartile.text.strip()
                    # Extract just the ranking part (e.g. "Q2")
                    if " as " in ranking_text:
                        ranking = ranking_text.split(" as ")[0].strip()
                    else:
                        ranking = ranking_text
                
                # Journal/venue info
                journal_info = item.find('div', class_='ar-meta')
                old_venue = "N/A"
                volume = "N/A"
                issue = "N/A"
                pages = "N/A"
                publisher = "N/A"
                
                if journal_info:
                    journal_text = journal_info.text.strip()
                    # Try to parse the journal metadata
                    old_venue = journal_text
                    
                    # Parse volume, issue, pages from journal metadata
                    # Example format: "Journal Name, Vol. 10, Issue 2, pp. 123-145"
                    parts = journal_text.split(',')
                    for i, part in enumerate(parts):
                        part = part.strip()
                        if part.lower().startswith('vol'):
                            # Extract volume number
                            vol_match = re.search(r'vol\.?\s*(\d+)', part, re.IGNORECASE)
                            if vol_match:
                                volume = vol_match.group(1)
                        elif part.lower().startswith('issue') or part.lower().startswith('no'):
                            # Extract issue number
                            issue_match = re.search(r'(?:issue|no)\.?\s*(\d+)', part, re.IGNORECASE)
                            if issue_match:
                                issue = issue_match.group(1)
                        elif 'pp.' in part.lower() or 'p.' in part.lower():
                            # Extract page numbers
                            page_match = re.search(r'pp?\.?\s*([0-9\-]+)', part, re.IGNORECASE)
                            if page_match:
                                pages = page_match.group(1)
                
                # Get venue from the ar-pub class
                venue_elem = item.find('a', class_='ar-pub')
                venue_html = "N/A"
                venue_clean = "N/A"
                if venue_elem:
                    # Store the full HTML
                    venue_html = str(venue_elem)
                    # Extract clean venue name
                    venue_clean = self.extract_clean_venue_name(venue_html)
                
                # Publication type (default to article for Scopus)
                publication_type = "Article"
                
                # Year
                year_elem = item.find('a', class_='ar-year')
                year = year_elem.text.strip() if year_elem else "N/A"
                
                # Citations
                citations_elem = item.find('a', class_='ar-cited')
                total_citations = citations_elem.text.strip().replace('cited', '').strip() if citations_elem else "0"
                
                # Clean up citations to get just the number
                citation_match = re.search(r'(\d+)', total_citations)
                if citation_match:
                    total_citations = citation_match.group(1)
                else:
                    total_citations = "0"
                
                # Extract author order
                author_order = self.extract_author_order(item, author_name)
                
                # Format authors as HTML
                authors_elem = item.find('div', class_='ar-authors')
                authors_html = f'<a href="#!">Creator : {author_name}</a>'
                authors_clean = author_name
                if authors_elem:
                    authors_text = authors_elem.text.strip()
                    if authors_text and authors_text != "N/A":
                        # Create HTML format for full author data
                        authors_html = f'<a href="#!">Creator : {authors_text}</a>'
                        # Clean version with just the author name
                        authors_clean = authors_text
                
                pub_data = {
                    'judul': title,
                    'author_id': author_id,
                    'author': authors_clean,  # Clean author name
                    'tahun_publikasi': int(year) if year.isdigit() else None,
                    'venue': venue_clean,  # Clean venue name
                    'publication_type': publication_type,
                    'volume': volume if volume != "N/A" else None,
                    'issue': issue if issue != "N/A" else None,
                    'pages': pages if pages != "N/A" else None,
                    'publisher': publisher,
                    'total_sitasi_seluruhnya': int(total_citations) if total_citations.isdigit() else 0,
                    'total_sitasi_tahun': 0,  # Default to 0 as we don't have this info
                    'sumber': 'Sinta_Scopus',
                    'tanggal_unduh': self.today,
                    'ranking': ranking if ranking != "N/A" else None,
                    'link_url': link_url,  # Add the publication URL
                    'author_order': author_order  # Add author order information
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
            # Insert publications into database using Sinta ID
            inserted_count = scraper.db.process_publications_to_db(publications, author_id)
            logger.info(f"Saved {inserted_count} publications for {author_name}")
            
            # Update dosen statistics using Sinta ID
            if inserted_count > 0:
                scraper.db.update_dosen_stats(author_id)
            
            return inserted_count
        else:
            logger.info(f"No publications found for {author_name}")
            return 0
    except Exception as e:
        logger.error(f"Error processing author {author_id}: {e}")
        return 0

def process_authors_from_csv(scraper, input_csv):
    """Process all authors from a CSV file"""
    # Read author data
    try:
        df = pd.read_csv(input_csv)
        author_data = []
        for _, row in df.iterrows():
            # Make sure to handle potential NaN values
            sinta_id = row.get('ID SINTA', row.get('ID_SINTA', None))
            if pd.notna(sinta_id):
                author_data.append({
                    'id': str(int(sinta_id)),  # Convert to int then string to remove decimals
                    'name': row.get('Nama', 'Unknown')
                })
        logger.info(f"Found {len(author_data)} authors in the input CSV file.")
    except Exception as e:
        logger.error(f"Error reading input CSV with pandas: {e}")
        # Fallback to raw CSV reading if pandas fails
        author_data = []
        try:
            with open(input_csv, mode='r', encoding='utf-8') as file:
                reader = csv.DictReader(file)
                for row in reader:
                    sinta_id = row.get('ID SINTA', row.get('ID_SINTA', None))
                    if sinta_id and sinta_id.strip():
                        author_data.append({
                            'id': sinta_id.strip(),
                            'name': row.get('Nama', 'Unknown')
                        })
            logger.info(f"Found {len(author_data)} authors in the input CSV file (fallback method).")
        except Exception as e:
            logger.error(f"Error with fallback CSV reading: {e}")
            return
    
    # Process each author
    for i, author in enumerate(author_data):
        author_id = author['id']
        author_name = author['name']
            
        logger.info(f"\nProcessing author {i+1}/{len(author_data)}: {author_name} (ID: {author_id})")
        
        try:
            # Check login status and relogin if needed every 10 authors
            if i > 0 and i % 10 == 0:
                scraper.relogin_if_needed()
            
            process_single_author(scraper, author_id, author_name)
            
            # Random delay between authors to avoid rate limiting
            delay = random.uniform(3, 6)
            logger.info(f"Waiting {delay:.2f} seconds before next author...")
            sleep(delay)
            
        except Exception as e:
            logger.error(f"Error processing author {author_id}: {e}")
            continue

def process_authors_from_database(scraper):
    """Process all authors from the database"""
    # Get author data from database
    try:
        author_data = scraper.db.get_all_authors_from_db()
        logger.info(f"Found {len(author_data)} authors in the database.")
        
        if not author_data:
            logger.warning("No authors found in the database.")
            return
            
        # Process each author
        for i, author in enumerate(author_data):
            author_id = author['id']  # SINTA ID
            author_name = author['name']
                
            logger.info(f"\nProcessing author {i+1}/{len(author_data)}: {author_name} (ID: {author_id})")
            
            try:
                # Check login status and relogin if needed every 10 authors
                if i > 0 and i % 10 == 0:
                    scraper.relogin_if_needed()
                
                process_single_author(scraper, author_id, author_name)
                
                # Random delay between authors to avoid rate limiting
                delay = random.uniform(3, 6)
                logger.info(f"Waiting {delay:.2f} seconds before next author...")
                sleep(delay)
                
            except Exception as e:
                logger.error(f"Error processing author {author_id}: {e}")
                continue
                
    except Exception as e:
        logger.error(f"Error processing authors from database: {e}")

def main():
    """Main function with command line options"""
    # Database configuration - modify these values as needed
    DB_CONFIG = {
        'dbname': 'ProDSGabungan',  # Changed to match your schema
        'user': 'postgres',
        'password': 'password123',
        'host': 'localhost',
        'port': '5432'
    }
    
    # Initialize database manager
    db_manager = DatabaseManager(**DB_CONFIG)
    if not db_manager.connect():
        logger.error("Failed to connect to database. Exiting.")
        return
    
    # Initialize scraper with database manager
    scraper = SintaScraper(db_manager)
    
    # Login credentials
    username = "6182101045@student.unpar.ac.id"
    password = "PAPAganteng1_"
    
    logger.info("Starting SINTA Scraper - Database Edition")
    logger.info(f"Logging in to SINTA with username: {username}")
    
    if not scraper.login(username, password):
        logger.warning("Login failed. Some data may be limited or inaccessible.")
    
    try:
        # Choose scraping mode
        print("\nSINTA Scraper - Database Edition:")
        print("1: Scrape a single author")
        print("2: Scrape all authors from CSV file")
        print("3: Scrape all authors from database")
        scrape_mode = input("Select an option (1/2/3): ").strip()
        
        if scrape_mode == "1":
            # Single author mode
            author_id = input("Enter author SINTA ID: ").strip()
            author_name = input("Enter author name (or press Enter to use 'Unknown'): ").strip() or "Unknown"
            
            # Validate author ID
            if not author_id:
                logger.error("Author ID cannot be empty. Exiting.")
                return
            
            # Make sure it's numeric
            if not author_id.isdigit():
                logger.warning("Warning: Author ID should be numeric. Continuing anyway...")
            
            # Confirm before proceeding
            print(f"\nWill scrape publications for:")
            print(f"  Author: {author_name} (ID: {author_id})")
            
            confirm = input("Proceed? (y/n): ").strip().lower()
            if confirm != 'y':
                print("Operation cancelled.")
                return
            
            publications_found = process_single_author(scraper, author_id, author_name)
            print(f"\nScraping completed. Found {publications_found} publications.")
            
        elif scrape_mode == "2":
            # CSV batch mode
            input_csv = input("Enter input CSV filename (default: unpar_dosen_460.csv): ").strip() or "unpar_dosen_460.csv"
            
            # Check if input file exists
            if not os.path.exists(input_csv):
                logger.error(f"Input file '{input_csv}' not found. Exiting.")
                return
            
            # Confirm before proceeding
            print(f"\nWill scrape publications for all authors in {input_csv}")
            print("Note: Authors must exist in the database with matching Sinta IDs.")
            
            confirm = input("This may take a long time. Proceed? (y/n): ").strip().lower()
            if confirm != 'y':
                print("Operation cancelled.")
                return
            
            process_authors_from_csv(scraper, input_csv)
            print("\nBatch scraping completed.")
            
        elif scrape_mode == "3":
            # Database mode
            print("\nWill scrape publications for all authors in the database")
            print("Only authors with valid Sinta IDs will be processed.")
            
            confirm = input("This may take a long time. Proceed? (y/n): ").strip().lower()
            if confirm != 'y':
                print("Operation cancelled.")
                return
            
            process_authors_from_database(scraper)
            print("\nDatabase scraping completed.")
            
        else:
            logger.error("Invalid option selected. Exiting.")
            return
        
        logger.info("Scraping completed successfully!")
        
        # Show some statistics
        print("\n" + "="*50)
        print("DATABASE SUMMARY")
        print("="*50)
        
        try:
            with db_manager.connection.cursor() as cursor:
                # Count total dosen
                cursor.execute("SELECT COUNT(*) FROM tmp_dosen_dt")
                total_dosen = cursor.fetchone()[0]
                print(f"Total Dosen in database: {total_dosen}")
                
                # Count total publikasi
                cursor.execute("SELECT COUNT(*) FROM stg_publikasi_tr")
                total_publikasi = cursor.fetchone()[0]
                print(f"Total Publikasi in database: {total_publikasi}")
                
                # Count publikasi by type
                cursor.execute("SELECT v_jenis, COUNT(*) FROM stg_publikasi_tr GROUP BY v_jenis")
                for jenis, count in cursor.fetchall():
                    print(f"  - {jenis}: {count}")
                
                # Count total citations
                cursor.execute("SELECT SUM(n_total_sitasi) FROM stg_publikasi_tr")
                total_citations = cursor.fetchone()[0] or 0
                print(f"Total Citations: {total_citations}")
                
                # Count records added today
                cursor.execute("SELECT COUNT(*) FROM stg_publikasi_tr WHERE DATE(t_tanggal_unduh) = CURRENT_DATE")
                added_today = cursor.fetchone()[0]
                print(f"Publications added today: {added_today}")
                
        except Exception as e:
            logger.error(f"Error generating summary statistics: {e}")
        
        print("Data has been successfully stored in the database!")
    
    finally:
        # Ensure database connection is closed
        db_manager.disconnect()

if __name__ == "__main__":
    main()