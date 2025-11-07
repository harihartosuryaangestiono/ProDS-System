# -*- coding: utf-8 -*-
"""
Complete Scraping Tasks - Real Implementation for All Scrapers
File: backend/task/scraping_tasks.py

Integrates all SINTA scrapers:
- SINTA Dosen (sinta_dosen.py)
- SINTA Scopus (sinta_scopus.py)
- SINTA Google Scholar (sinta_googlescholar.py)
- SINTA Garuda (sinta_garuda.py)

Created: 2025-10-16
Author: System Integration
"""

import sys
import os
from datetime import datetime
import time
import traceback

# ============================================================================
# PATH SETUP
# ============================================================================

# Add scrapers directory to Python path
current_dir = os.path.dirname(os.path.abspath(__file__))
backend_dir = os.path.dirname(current_dir)
scrapers_dir = os.path.join(backend_dir, 'scrapers')

# Insert at beginning to prioritize local scrapers
sys.path.insert(0, scrapers_dir)
sys.path.insert(0, backend_dir)

print(f"📂 Scrapers directory: {scrapers_dir}")
print(f"📂 Backend directory: {backend_dir}")

# Import database config
try:
    from utils.database import DB_CONFIG
    print(f"✅ Database config loaded: {DB_CONFIG.get('dbname', 'Unknown')}")
except ImportError as e:
    print(f"⚠️ Warning: Could not import DB_CONFIG: {e}")
    # Fallback config
    DB_CONFIG = {
        'dbname': 'ProDSGabungan',
        'user': 'postgres',
        'password': 'password123',
        'host': 'localhost',
        'port': '5432'
    }

# ============================================================================
# HELPER FUNCTIONS
# ============================================================================

def print_header(title, job_id=None):
    """Print formatted header for scraping tasks"""
    print(f"\n{'='*80}")
    print(f"🚀 {title}")
    print(f"{'='*80}")
    if job_id:
        print(f"📋 Job ID: {job_id}")
    print(f"⏰ Started at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"{'='*80}\n")

def print_footer(title, success=True):
    """Print formatted footer for scraping tasks"""
    print(f"\n{'='*80}")
    if success:
        print(f"🎉 {title} - SUCCESS")
    else:
        print(f"❌ {title} - FAILED")
    print(f"⏰ Finished at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"{'='*80}\n")

# ============================================================================
# SINTA DOSEN SCRAPING TASK
# ============================================================================

def scrape_sinta_dosen_task(username, password, affiliation_id, target_dosen, 
                            max_pages, max_cycles, job_id=None):
    """
    Real scraping task for SINTA Dosen
    
    Args:
        username: SINTA login username
        password: SINTA login password
        affiliation_id: University affiliation ID
        target_dosen: Target number of dosen to scrape
        max_pages: Maximum pages per cycle
        max_cycles: Maximum number of cycles
        job_id: Unique job identifier
    
    Returns:
        dict: Result with success status, message, and summary
    """
    # Lazy import to avoid circular dependency
    def get_progress_helpers():
        from routes import scraping_routes
        return scraping_routes.active_jobs, scraping_routes.emit_progress
    
    print_header("SINTA DOSEN SCRAPING TASK - REAL MODE", job_id)
    
    print(f"📊 Configuration:")
    print(f"   - Username: {username}")
    print(f"   - Affiliation ID: {affiliation_id}")
    print(f"   - Target Dosen: {target_dosen}")
    print(f"   - Max Pages/Cycle: {max_pages}")
    print(f"   - Max Cycles: {max_cycles}")
    print(f"   - Database: {DB_CONFIG['dbname']}\n")
    
    try:
        # Get progress helpers
        active_jobs, emit_progress = get_progress_helpers() if job_id else (None, None)

        def cancel_requested():
            try:
                return bool(active_jobs.get(job_id, {}).get('cancel_requested')) if active_jobs and job_id else False
            except Exception:
                return False

        def finalize_cancel(message='Cancelled by user'):
            if job_id and active_jobs and emit_progress:
                active_jobs[job_id].update({
                    'status': 'cancelled',
                    'message': message,
                    'completed_at': datetime.now().isoformat(),
                    'result': {'success': False, 'message': message}
                })
                emit_progress(job_id, active_jobs[job_id])
            return {'success': False, 'message': message}
        
        # Update progress
        if job_id and active_jobs and emit_progress:
            active_jobs[job_id].update({
                'status': 'running',
                'message': 'Importing scraper modules...',
                'current': 0,
                'total': target_dosen
            })
            emit_progress(job_id, active_jobs[job_id])
        if cancel_requested():
            return finalize_cancel()
        
        # Import scraper
        print("📦 Importing SintaDosenScraper...")
        from sinta_dosen import SintaDosenScraper
        print("✅ Import successful!")
        
        # Update progress
        if job_id and active_jobs and emit_progress:
            active_jobs[job_id].update({
                'message': 'Connecting to database and initializing scraper...'
            })
            emit_progress(job_id, active_jobs[job_id])
        if cancel_requested():
            return finalize_cancel()
        
        # Initialize scraper
        print(f"\n🔌 Connecting to database: {DB_CONFIG['dbname']}@{DB_CONFIG['host']}")
        scraper = SintaDosenScraper(db_config=DB_CONFIG)
        print("✅ Scraper initialized successfully!")
        
        # Update progress
        if job_id and active_jobs and emit_progress:
            active_jobs[job_id].update({
                'message': f'Starting scraping process (target: {target_dosen} dosen)...'
            })
            emit_progress(job_id, active_jobs[job_id])
        if cancel_requested():
            return finalize_cancel()
        
        # Start scraping
        print(f"\n🏃 Starting scraping process...")
        print(f"⏱️  This may take several hours depending on target...\n")
        
        start_time = time.time()
        
        # Get current count before scraping
        current_count = scraper._get_current_dosen_count()
        
        # Update progress with current count
        if job_id and active_jobs and emit_progress:
            active_jobs[job_id].update({
                'current': current_count,
                'message': f'Current: {current_count}/{target_dosen} dosen. Starting scraping...'
            })
            emit_progress(job_id, active_jobs[job_id])
        if cancel_requested():
            return finalize_cancel()
        
        final_count = scraper.scrape_until_target_reached(
            affiliation_id=affiliation_id,
            target_dosen=target_dosen,
            max_pages=max_pages,
            max_cycles=max_cycles
        )
        
        elapsed_time = time.time() - start_time
        
        print(f"\n✅ Scraping completed!")
        print(f"📊 Final count: {final_count} dosen")
        print(f"⏱️  Total time: {elapsed_time/60:.2f} minutes")
        
        # Update final progress
        if job_id and active_jobs and emit_progress:
            active_jobs[job_id].update({
                'current': final_count,
                'message': f'Completed! {final_count} dosen scraped successfully'
            })
            emit_progress(job_id, active_jobs[job_id])
        
        # Get summary
        summary = scraper.get_extraction_summary()
        
        # Close connections
        scraper.close()
        
        # Prepare result
        result = {
            'success': True,
            'message': f'✅ Scraping berhasil! Total {final_count} dosen unik tersimpan',
            'final_count': final_count,
            'elapsed_time_minutes': round(elapsed_time/60, 2),
            'summary': summary
        }
        
        print_footer("SINTA DOSEN SCRAPING", success=True)
        return result
        
    except ImportError as e:
        error_msg = f"Failed to import sinta_dosen.py: {str(e)}"
        print(f"\n❌ IMPORT ERROR: {error_msg}")
        print(f"💡 Check if sinta_dosen.py exists in: {scrapers_dir}")
        print_footer("SINTA DOSEN SCRAPING", success=False)
        
        return {
            'success': False,
            'error': error_msg,
            'traceback': traceback.format_exc(),
            'hint': f'Place sinta_dosen.py in {scrapers_dir}'
        }
        
    except Exception as e:
        error_msg = str(e)
        traceback_msg = traceback.format_exc()
        
        print(f"\n❌ SCRAPING FAILED: {error_msg}")
        print(f"\n📋 Full Traceback:")
        print(traceback_msg)
        print_footer("SINTA DOSEN SCRAPING", success=False)
        
        return {
            'success': False,
            'error': error_msg,
            'traceback': traceback_msg
        }
    
    finally:
        # Ensure cleanup
        if 'scraper' in locals():
            try:
                scraper.close()
                print("🔒 Scraper connections closed")
            except:
                pass

# ============================================================================
# SINTA SCOPUS SCRAPING TASK
# ============================================================================

def scrape_sinta_scopus_task(username, password, job_id=None):
    """
    Real scraping task for SINTA Scopus publications
    
    Args:
        username: SINTA login username
        password: SINTA login password
        job_id: Unique job identifier
    
    Returns:
        dict: Result with success status and publication count
    """
    # Lazy import to avoid circular dependency
    def get_progress_helpers():
        from routes import scraping_routes
        return scraping_routes.active_jobs, scraping_routes.emit_progress
    
    print_header("SINTA SCOPUS SCRAPING TASK - REAL MODE", job_id)
    
    print(f"📊 Configuration:")
    print(f"   - Username: {username}")
    print(f"   - Database: {DB_CONFIG['dbname']}\n")
    
    try:
        # Get progress helpers
        active_jobs, emit_progress = get_progress_helpers() if job_id else (None, None)

        def cancel_requested():
            try:
                return bool(active_jobs.get(job_id, {}).get('cancel_requested')) if active_jobs and job_id else False
            except Exception:
                return False

        def finalize_cancel(message='Cancelled by user'):
            if job_id and active_jobs and emit_progress:
                active_jobs[job_id].update({
                    'status': 'cancelled',
                    'message': message,
                    'completed_at': datetime.now().isoformat(),
                    'result': {'success': False, 'message': message}
                })
                emit_progress(job_id, active_jobs[job_id])
            return {'success': False, 'message': message}
        
        # Update progress
        if job_id and active_jobs and emit_progress:
            active_jobs[job_id].update({
                'status': 'running',
                'message': 'Importing scraper modules...',
                'current': 0,
                'total': 0
            })
            emit_progress(job_id, active_jobs[job_id])
        if cancel_requested():
            return finalize_cancel()
        
        # Import scraper and database manager
        print("📦 Importing SintaScraper and DatabaseManager...")
        from sinta_scopus import SintaScraper, DatabaseManager
        print("✅ Import successful!")
        
        # Update progress
        if job_id and active_jobs and emit_progress:
            active_jobs[job_id].update({
                'message': 'Connecting to database...'
            })
            emit_progress(job_id, active_jobs[job_id])
        if cancel_requested():
            return finalize_cancel()
        
        # Initialize database
        print(f"\n🔌 Connecting to database: {DB_CONFIG['dbname']}@{DB_CONFIG['host']}")
        db_manager = DatabaseManager(
            dbname=DB_CONFIG['dbname'],
            user=DB_CONFIG['user'],
            password=DB_CONFIG['password'],
            host=DB_CONFIG['host'],
            port=DB_CONFIG['port']
        )
        
        if not db_manager.connect():
            raise Exception("Failed to connect to database")
        print("✅ Database connected!")
        
        # Initialize scraper
        scraper = SintaScraper(db_manager)
        print("✅ Scraper initialized!")
        
        # Update progress
        if job_id and active_jobs and emit_progress:
            active_jobs[job_id].update({
                'message': 'Logging in to SINTA...'
            })
            emit_progress(job_id, active_jobs[job_id])
        if cancel_requested():
            return finalize_cancel()
        
        # Login to SINTA
        print(f"\n🔐 Logging in to SINTA...")
        if not scraper.login(username, password):
            raise Exception("Login to SINTA failed")
        print("✅ Login successful!")
        if cancel_requested():
            return finalize_cancel()
        
        # Get authors from database
        print(f"\n📋 Retrieving authors from database...")
        authors = db_manager.get_all_authors_from_db()
        print(f"📊 Found {len(authors)} authors with SINTA IDs")
        
        if not authors:
            raise Exception("No authors found in database")
        
        # Update progress with total authors
        if job_id and active_jobs and emit_progress:
            active_jobs[job_id].update({
                'total': len(authors),
                'message': f'Starting Scopus scraping for {len(authors)} authors...'
            })
            emit_progress(job_id, active_jobs[job_id])
        if cancel_requested():
            return finalize_cancel()
        
        # Start scraping
        print(f"\n🏃 Starting Scopus scraping...")
        print(f"⏱️  This will process {len(authors)} authors...\n")
        
        start_time = time.time()
        total_publications = 0
        processed_authors = 0
        failed_authors = 0
        
        for i, author in enumerate(authors):
            try:
                author_id = author['id']  # SINTA ID
                author_name = author['name']
                
                # Update progress
                if job_id:
                    active_jobs[job_id].update({
                        'current': i + 1,
                        'message': f'Processing {author_name} ({i+1}/{len(authors)})...'
                    })
                    emit_progress(job_id, active_jobs[job_id])
                if cancel_requested():
                    return finalize_cancel()
                
                print(f"[{i+1}/{len(authors)}] Processing: {author_name} (SINTA: {author_id})")
                
                # Scrape publications
                publications = scraper.scrape_author_publications(author_id, author_name)
                
                if publications:
                    # Save to database
                    saved_count = db_manager.process_publications_to_db(publications, author_id)
                    total_publications += saved_count
                    
                    # Update dosen stats
                    db_manager.update_dosen_stats(author_id)
                    
                    print(f"   ✅ Saved {saved_count} publications")
                else:
                    print(f"   ℹ️  No publications found")
                
                processed_authors += 1
                
                # Delay between authors (avoid rate limiting)
                if i < len(authors) - 1:
                    delay = 3
                    print(f"   ⏳ Waiting {delay}s...")
                    time.sleep(delay)
                
            except Exception as e:
                failed_authors += 1
                print(f"   ❌ Error: {str(e)}")
                continue
        
        elapsed_time = time.time() - start_time
        
        # Close database
        db_manager.disconnect()
        
        # Update final progress
        if job_id:
            active_jobs[job_id].update({
                'current': len(authors),
                'message': f'Completed! {total_publications} publications from {processed_authors} authors'
            })
            emit_progress(job_id, active_jobs[job_id])
        
        # Prepare result
        result = {
            'success': True,
            'message': f'✅ Scopus scraping berhasil! {total_publications} publikasi dari {processed_authors} dosen',
            'total_publications': total_publications,
            'processed_authors': processed_authors,
            'failed_authors': failed_authors,
            'elapsed_time_minutes': round(elapsed_time/60, 2)
        }
        
        print(f"\n📊 Summary:")
        print(f"   - Total Publications: {total_publications}")
        print(f"   - Processed Authors: {processed_authors}")
        print(f"   - Failed Authors: {failed_authors}")
        print(f"   - Time Taken: {elapsed_time/60:.2f} minutes")
        
        print_footer("SINTA SCOPUS SCRAPING", success=True)
        return result
        
    except ImportError as e:
        error_msg = f"Failed to import sinta_scopus.py: {str(e)}"
        print(f"\n❌ IMPORT ERROR: {error_msg}")
        print(f"💡 Check if sinta_scopus.py exists in: {scrapers_dir}")
        print_footer("SINTA SCOPUS SCRAPING", success=False)
        
        return {
            'success': False,
            'error': error_msg,
            'traceback': traceback.format_exc(),
            'hint': f'Place sinta_scopus.py in {scrapers_dir}'
        }
        
    except Exception as e:
        error_msg = str(e)
        traceback_msg = traceback.format_exc()
        
        print(f"\n❌ SCRAPING FAILED: {error_msg}")
        print(f"\n📋 Full Traceback:")
        print(traceback_msg)
        print_footer("SINTA SCOPUS SCRAPING", success=False)
        
        return {
            'success': False,
            'error': error_msg,
            'traceback': traceback_msg
        }
    
    finally:
        # Ensure cleanup
        if 'db_manager' in locals():
            try:
                db_manager.disconnect()
            except:
                pass

# ============================================================================
# SINTA GOOGLE SCHOLAR SCRAPING TASK
# ============================================================================

def scrape_sinta_googlescholar_task(username, password, job_id=None):
    """
    Real scraping task for SINTA Google Scholar publications
    
    Args:
        username: SINTA login username
        password: SINTA login password
        job_id: Unique job identifier
    
    Returns:
        dict: Result with success status and publication count
    """
    # Lazy import to avoid circular dependency
    def get_progress_helpers():
        from routes import scraping_routes
        return scraping_routes.active_jobs, scraping_routes.emit_progress
    
    print_header("SINTA GOOGLE SCHOLAR SCRAPING TASK - REAL MODE", job_id)
    
    print(f"📊 Configuration:")
    print(f"   - Username: {username}")
    print(f"   - Database: {DB_CONFIG['dbname']}\n")
    
    try:
        # Get progress helpers
        active_jobs, emit_progress = get_progress_helpers() if job_id else (None, None)

        def cancel_requested():
            try:
                return bool(active_jobs.get(job_id, {}).get('cancel_requested')) if active_jobs and job_id else False
            except Exception:
                return False

        def finalize_cancel(message='Cancelled by user'):
            if job_id and active_jobs and emit_progress:
                active_jobs[job_id].update({
                    'status': 'cancelled',
                    'message': message,
                    'completed_at': datetime.now().isoformat(),
                    'result': {'success': False, 'message': message}
                })
                emit_progress(job_id, active_jobs[job_id])
            return {'success': False, 'message': message}
        
        # Update progress
        if job_id and active_jobs and emit_progress:
            active_jobs[job_id].update({
                'status': 'running',
                'message': 'Importing scraper modules...',
                'current': 0,
                'total': 0
            })
            emit_progress(job_id, active_jobs[job_id])
        if cancel_requested():
            return finalize_cancel()
        
        # Import scraper and database manager
        print("📦 Importing SintaScraper and DatabaseManager...")
        from sinta_googlescholar import SintaScraper, DatabaseManager
        print("✅ Import successful!")
        
        # Update progress
        if job_id and active_jobs and emit_progress:
            active_jobs[job_id].update({
                'message': 'Connecting to database...'
            })
            emit_progress(job_id, active_jobs[job_id])
        if cancel_requested():
            return finalize_cancel()
        
        # Initialize database
        print(f"\n🔌 Connecting to database: {DB_CONFIG['dbname']}@{DB_CONFIG['host']}")
        db_manager = DatabaseManager(
            dbname=DB_CONFIG['dbname'],
            user=DB_CONFIG['user'],
            password=DB_CONFIG['password'],
            host=DB_CONFIG['host'],
            port=DB_CONFIG['port']
        )
        
        if not db_manager.connect():
            raise Exception("Failed to connect to database")
        print("✅ Database connected!")
        
        # Initialize scraper
        scraper = SintaScraper(db_manager)
        print("✅ Scraper initialized!")
        
        # Update progress
        if job_id and active_jobs and emit_progress:
            active_jobs[job_id].update({
                'message': 'Logging in to SINTA...'
            })
            emit_progress(job_id, active_jobs[job_id])
        if cancel_requested():
            return finalize_cancel()
        
        # Login to SINTA
        print(f"\n🔐 Logging in to SINTA...")
        if not scraper.login(username, password):
            raise Exception("Login to SINTA failed")
        print("✅ Login successful!")
        if cancel_requested():
            return finalize_cancel()
        
        # Get authors from database
        print(f"\n📋 Retrieving authors from database...")
        authors = db_manager.get_all_authors()
        print(f"📊 Found {len(authors)} authors with SINTA IDs")
        
        if not authors:
            raise Exception("No authors found in database")
        
        # Update progress with total authors
        if job_id and active_jobs and emit_progress:
            active_jobs[job_id].update({
                'total': len(authors),
                'message': f'Starting Google Scholar scraping for {len(authors)} authors...'
            })
            emit_progress(job_id, active_jobs[job_id])
        if cancel_requested():
            return finalize_cancel()
        
        # Start scraping
        print(f"\n🏃 Starting Google Scholar scraping...")
        print(f"⏱️  This will process {len(authors)} authors...\n")
        
        start_time = time.time()
        total_publications = 0
        processed_authors = 0
        failed_authors = 0
        
        for i, author in enumerate(authors):
            try:
                author_id = author['id']  # SINTA ID
                author_name = author['name']
                
                # Update progress
                if job_id and active_jobs and emit_progress:
                    active_jobs[job_id].update({
                        'current': i + 1,
                        'message': f'Processing {author_name} ({i+1}/{len(authors)})...'
                    })
                    emit_progress(job_id, active_jobs[job_id])
                if cancel_requested():
                    return finalize_cancel()
                
                print(f"[{i+1}/{len(authors)}] Processing: {author_name} (SINTA: {author_id})")
                
                # Check login every 10 authors
                if i > 0 and i % 10 == 0:
                    scraper.relogin_if_needed()
                
                # Scrape publications
                publications = scraper.scrape_author_publications(author_id, author_name)
                
                if publications:
                    # Save to database
                    saved_count = db_manager.insert_publications_batch(publications)
                    total_publications += saved_count
                    
                    # Update dosen stats
                    db_manager.update_dosen_statistics(author_id)
                    
                    print(f"   ✅ Saved {saved_count} publications")
                else:
                    print(f"   ℹ️  No publications found")
                
                processed_authors += 1
                
                # Delay between authors
                if i < len(authors) - 1:
                    delay = 3
                    print(f"   ⏳ Waiting {delay}s...")
                    time.sleep(delay)
                
            except Exception as e:
                failed_authors += 1
                print(f"   ❌ Error: {str(e)}")
                continue
        
        elapsed_time = time.time() - start_time
        
        # Close database
        db_manager.disconnect()
        
        # Update final progress
        if job_id and active_jobs and emit_progress:
            active_jobs[job_id].update({
                'current': len(authors),
                'message': f'Completed! {total_publications} publications from {processed_authors} authors'
            })
            emit_progress(job_id, active_jobs[job_id])
        
        # Prepare result
        result = {
            'success': True,
            'message': f'✅ Google Scholar scraping berhasil! {total_publications} publikasi dari {processed_authors} dosen',
            'total_publications': total_publications,
            'processed_authors': processed_authors,
            'failed_authors': failed_authors,
            'elapsed_time_minutes': round(elapsed_time/60, 2)
        }
        
        print(f"\n📊 Summary:")
        print(f"   - Total Publications: {total_publications}")
        print(f"   - Processed Authors: {processed_authors}")
        print(f"   - Failed Authors: {failed_authors}")
        print(f"   - Time Taken: {elapsed_time/60:.2f} minutes")
        
        print_footer("SINTA GOOGLE SCHOLAR SCRAPING", success=True)
        return result
        
    except ImportError as e:
        error_msg = f"Failed to import sinta_googlescholar.py: {str(e)}"
        print(f"\n❌ IMPORT ERROR: {error_msg}")
        print(f"💡 Check if sinta_googlescholar.py exists in: {scrapers_dir}")
        print_footer("SINTA GOOGLE SCHOLAR SCRAPING", success=False)
        
        return {
            'success': False,
            'error': error_msg,
            'traceback': traceback.format_exc(),
            'hint': f'Place sinta_googlescholar.py in {scrapers_dir}'
        }
        
    except Exception as e:
        error_msg = str(e)
        traceback_msg = traceback.format_exc()
        
        print(f"\n❌ SCRAPING FAILED: {error_msg}")
        print(f"\n📋 Full Traceback:")
        print(traceback_msg)
        print_footer("SINTA GOOGLE SCHOLAR SCRAPING", success=False)
        
        return {
            'success': False,
            'error': error_msg,
            'traceback': traceback_msg
        }
    
    finally:
        if 'db_manager' in locals():
            try:
                db_manager.disconnect()
            except:
                pass

# ============================================================================
# SINTA GARUDA SCRAPING TASK
# ============================================================================

def scrape_sinta_garuda_task(username, password, job_id=None):
    """
    Real scraping task for SINTA Garuda publications
    
    Args:
        username: SINTA login username
        password: SINTA login password
        job_id: Unique job identifier
    
    Returns:
        dict: Result with success status and publication count
    """
    # Lazy import to avoid circular dependency
    def get_progress_helpers():
        from routes import scraping_routes
        return scraping_routes.active_jobs, scraping_routes.emit_progress
    
    print_header("SINTA GARUDA SCRAPING TASK - REAL MODE", job_id)
    
    print(f"📊 Configuration:")
    print(f"   - Username: {username}")
    print(f"   - Database: {DB_CONFIG['dbname']}\n")
    
    try:
        # Get progress helpers
        active_jobs, emit_progress = get_progress_helpers() if job_id else (None, None)

        def cancel_requested():
            try:
                return bool(active_jobs.get(job_id, {}).get('cancel_requested')) if active_jobs and job_id else False
            except Exception:
                return False

        def finalize_cancel(message='Cancelled by user'):
            if job_id and active_jobs and emit_progress:
                active_jobs[job_id].update({
                    'status': 'cancelled',
                    'message': message,
                    'completed_at': datetime.now().isoformat(),
                    'result': {'success': False, 'message': message}
                })
                emit_progress(job_id, active_jobs[job_id])
            return {'success': False, 'message': message}
        
        # Update progress
        if job_id and active_jobs and emit_progress:
            active_jobs[job_id].update({
                'status': 'running',
                'message': 'Importing scraper modules...',
                'current': 0,
                'total': 0
            })
            emit_progress(job_id, active_jobs[job_id])
        if cancel_requested():
            return finalize_cancel()
        
        # Import scraper and database manager
        print("📦 Importing SintaGarudaScraper and DatabaseManager...")
        from sinta_garuda import SintaGarudaScraper, DatabaseManager
        print("✅ Import successful!")
        
        # Update progress
        if job_id and active_jobs and emit_progress:
            active_jobs[job_id].update({
                'message': 'Connecting to database...'
            })
            emit_progress(job_id, active_jobs[job_id])
        if cancel_requested():
            return finalize_cancel()
        
        # Initialize database
        print(f"\n🔌 Connecting to database: {DB_CONFIG['dbname']}@{DB_CONFIG['host']}")
        db_manager = DatabaseManager(
            dbname=DB_CONFIG['dbname'],
            user=DB_CONFIG['user'],
            password=DB_CONFIG['password'],
            host=DB_CONFIG['host'],
            port=DB_CONFIG['port']
        )
        
        if not db_manager.connect():
            raise Exception("Failed to connect to database")
        print("✅ Database connected!")
        
        # Initialize scraper
        scraper = SintaGarudaScraper(db_manager)
        print("✅ Scraper initialized!")
        
        # Update progress
        if job_id and active_jobs and emit_progress:
            active_jobs[job_id].update({
                'message': 'Logging in to SINTA...'
            })
            emit_progress(job_id, active_jobs[job_id])
        if cancel_requested():
            return finalize_cancel()
        
        # Login to SINTA
        print(f"\n🔐 Logging in to SINTA...")
        if not scraper.login(username, password):
            raise Exception("Login to SINTA failed")
        print("✅ Login successful!")
        if cancel_requested():
            return finalize_cancel()
        
        # Get authors from database
        print(f"\n📋 Retrieving authors from database...")
        authors = db_manager.get_all_dosen_with_sinta()
        print(f"📊 Found {len(authors)} authors with SINTA IDs")
        
        if not authors:
            raise Exception("No authors found in database")
        
        # Generate batch ID
        db_manager.generate_batch_id()
        
        # Update progress with total authors
        if job_id and active_jobs and emit_progress:
            active_jobs[job_id].update({
                'total': len(authors),
                'message': f'Starting Garuda scraping for {len(authors)} authors...'
            })
            emit_progress(job_id, active_jobs[job_id])
        if cancel_requested():
            return finalize_cancel()
        
        # Start scraping
        print(f"\n🏃 Starting Garuda scraping...")
        print(f"⏱️  This will process {len(authors)} authors...\n")
        
        start_time = time.time()
        total_publications = 0
        processed_authors = 0
        failed_authors = 0
        
        for i, author in enumerate(authors):
            try:
                sinta_id = author['sinta_id']
                nama_dosen = author['nama']
                jurusan = author['jurusan']
                
                # Update progress
                if job_id and active_jobs and emit_progress:
                    active_jobs[job_id].update({
                        'current': i + 1,
                        'message': f'Processing {nama_dosen} ({i+1}/{len(authors)})...'
                    })
                    emit_progress(job_id, active_jobs[job_id])
                if cancel_requested():
                    return finalize_cancel()
                
                print(f"[{i+1}/{len(authors)}] Processing: {nama_dosen} (SINTA: {sinta_id})")
                
                dosen_data = {
                    'nama': nama_dosen,
                    'sinta_id': sinta_id,
                    'jurusan': jurusan
                }
                
                # Scrape publications
                saved_count = scraper.scrape_author_publications(dosen_data)
                
                if saved_count > 0:
                    total_publications += saved_count
                    print(f"   ✅ Saved {saved_count} publications")
                else:
                    print(f"   ℹ️  No publications found")
                
                processed_authors += 1
                
                # Delay between authors
                if i < len(authors) - 1:
                    delay = 3
                    print(f"   ⏳ Waiting {delay}s...")
                    time.sleep(delay)
                
            except Exception as e:
                failed_authors += 1
                print(f"   ❌ Error: {str(e)}")
                continue
        
        elapsed_time = time.time() - start_time
        
        # Close database
        db_manager.disconnect()
        
        # Update final progress
        if job_id and active_jobs and emit_progress:
            active_jobs[job_id].update({
                'current': len(authors),
                'message': f'Completed! {total_publications} publications from {processed_authors} authors'
            })
            emit_progress(job_id, active_jobs[job_id])
        
        # Prepare result
        result = {
            'success': True,
            'message': f'✅ Garuda scraping berhasil! {total_publications} publikasi dari {processed_authors} dosen',
            'total_publications': total_publications,
            'processed_authors': processed_authors,
            'failed_authors': failed_authors,
            'elapsed_time_minutes': round(elapsed_time/60, 2)
        }
        
        print(f"\n📊 Summary:")
        print(f"   - Total Publications: {total_publications}")
        print(f"   - Processed Authors: {processed_authors}")
        print(f"   - Failed Authors: {failed_authors}")
        print(f"   - Time Taken: {elapsed_time/60:.2f} minutes")
        
        print_footer("SINTA GARUDA SCRAPING", success=True)
        return result
        
    except ImportError as e:
        error_msg = f"Failed to import sinta_garuda.py: {str(e)}"
        print(f"\n❌ IMPORT ERROR: {error_msg}")
        print(f"💡 Check if sinta_garuda.py exists in: {scrapers_dir}")
        print_footer("SINTA GARUDA SCRAPING", success=False)
        
        return {
            'success': False,
            'error': error_msg,
            'traceback': traceback.format_exc(),
            'hint': f'Place sinta_garuda.py in {scrapers_dir}'
        }
        
    except Exception as e:
        error_msg = str(e)
        traceback_msg = traceback.format_exc()
        
        print(f"\n❌ SCRAPING FAILED: {error_msg}")
        print(f"\n📋 Full Traceback:")
        print(traceback_msg)
        print_footer("SINTA GARUDA SCRAPING", success=False)
        
        return {
            'success': False,
            'error': error_msg,
            'traceback': traceback_msg
        }
    
    finally:
        if 'db_manager' in locals():
            try:
                db_manager.disconnect()
            except:
                pass

# ============================================================================
# MODULE INFO
# ============================================================================

if __name__ == "__main__":
    print("=" * 80)
    print("SCRAPING TASKS MODULE")
    print("=" * 80)
    print("Available tasks:")
    print("  1. scrape_sinta_dosen_task()")
    print("  2. scrape_sinta_scopus_task()")
    print("  3. scrape_sinta_googlescholar_task()")
    print("  4. scrape_sinta_garuda_task()")
    print("=" * 80)
    print(f"Scrapers directory: {scrapers_dir}")
    print(f"Database: {DB_CONFIG['dbname']}@{DB_CONFIG['host']}")
    print("=" * 80)