import sys
import os
sys.path.append(os.path.join(os.path.dirname(__file__), '..', 'scrapers'))

from sinta_dosen import SintaDosenScraper
from sinta_scopus import SintaScraper as SintaScopusScraper, DatabaseManager as ScopusDBManager
from sinta_googlescholar import SintaScraper as SintaGSScraper, DatabaseManager as GSDBManager
from sinta_garuda import SintaGarudaScraper, DatabaseManager as GarudaDBManager
from utils.database import DB_CONFIG  # Fixed: changed from config.database to utils.database
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def emit_progress_update(job_id, progress_data):
    """Emit progress update via SocketIO"""
    try:
        from app import socketio
        socketio.emit('scraping_progress', {
            'job_id': job_id,
            'type': 'progress',
            'progress': progress_data
        })
    except Exception as e:
        logger.error(f"Error emitting progress: {e}")

def scrape_sinta_dosen_task(username, password, affiliation_id, target_dosen=473, 
                            max_pages=50, max_cycles=20, job_id=None):
    """Task untuk scraping SINTA Dosen"""
    try:
        logger.info(f"Starting SINTA Dosen scraping job {job_id}")
        
        # Initialize scraper
        scraper = SintaDosenScraper(db_config=DB_CONFIG)
        
        # Emit initial progress
        if job_id:
            emit_progress_update(job_id, {
                'status': 'starting',
                'message': 'Initializing scraper...',
                'currentCount': 0,
                'targetCount': target_dosen
            })
        
        # Start scraping with progress callbacks
        def progress_callback(current, target, cycle, message):
            if job_id:
                emit_progress_update(job_id, {
                    'status': 'running',
                    'message': message,
                    'currentCount': current,
                    'targetCount': target,
                    'cycle': cycle,
                    'maxCycles': max_cycles
                })
        
        # Scrape until target reached
        final_count = scraper.scrape_until_target_reached(
            affiliation_id=affiliation_id,
            target_dosen=target_dosen,
            max_pages=max_pages,
            max_cycles=max_cycles
        )
        
        # Get summary
        summary = scraper.get_extraction_summary()
        
        # Close scraper
        scraper.close()
        
        result = {
            'success': True,
            'message': f'Scraping completed! Total dosen: {final_count}',
            'summary': summary,
            'details': {
                'final_count': final_count,
                'target_reached': final_count >= target_dosen
            }
        }
        
        logger.info(f"SINTA Dosen scraping job {job_id} completed successfully")
        return result
        
    except Exception as e:
        logger.error(f"Error in SINTA Dosen scraping: {e}")
        raise

def scrape_sinta_scopus_task(username, password, job_id=None):
    """Task untuk scraping SINTA Scopus"""
    try:
        logger.info(f"Starting SINTA Scopus scraping job {job_id}")
        
        # Initialize database and scraper
        db_manager = ScopusDBManager(**DB_CONFIG)
        if not db_manager.connect():
            raise Exception("Failed to connect to database")
        
        scraper = SintaScopusScraper(db_manager)
        
        # Login
        if not scraper.login(username, password):
            raise Exception("Failed to login to SINTA")
        
        # Emit initial progress
        if job_id:
            emit_progress_update(job_id, {
                'status': 'running',
                'message': 'Getting authors from database...',
                'currentCount': 0
            })
        
        # Get all authors from database
        authors = db_manager.get_all_authors_from_db()
        total_authors = len(authors)
        
        if total_authors == 0:
            raise Exception("No authors found in database")
        
        logger.info(f"Found {total_authors} authors to process")
        
        # Process each author
        processed_count = 0
        total_publications = 0
        
        for i, author in enumerate(authors):
            try:
                author_id = author['id']
                author_name = author['name']
                
                # Emit progress
                if job_id:
                    emit_progress_update(job_id, {
                        'status': 'running',
                        'message': f'Processing {author_name}...',
                        'currentCount': i + 1,
                        'targetCount': total_authors,
                        'currentAuthor': author_name
                    })
                
                # Scrape author publications
                publications = scraper.scrape_author_publications(author_id, author_name)
                
                if publications:
                    # Process to database
                    inserted = db_manager.process_publications_to_db(publications, author_id)
                    total_publications += inserted
                    
                    # Update dosen stats
                    db_manager.update_dosen_stats(author_id)
                
                processed_count += 1
                
            except Exception as e:
                logger.error(f"Error processing author {author.get('name', 'Unknown')}: {e}")
                continue
        
        # Disconnect
        db_manager.disconnect()
        
        result = {
            'success': True,
            'message': f'Scopus scraping completed!',
            'summary': {
                'total_authors': total_authors,
                'processed_authors': processed_count,
                'total_publications': total_publications
            }
        }
        
        logger.info(f"SINTA Scopus scraping job {job_id} completed successfully")
        return result
        
    except Exception as e:
        logger.error(f"Error in SINTA Scopus scraping: {e}")
        raise

def scrape_sinta_googlescholar_task(username, password, job_id=None):
    """Task untuk scraping SINTA Google Scholar"""
    try:
        logger.info(f"Starting SINTA Google Scholar scraping job {job_id}")
        
        # Initialize database and scraper
        db_manager = GSDBManager(**DB_CONFIG)
        if not db_manager.connect():
            raise Exception("Failed to connect to database")
        
        scraper = SintaGSScraper(db_manager)
        
        # Login
        if not scraper.login(username, password):
            raise Exception("Failed to login to SINTA")
        
        # Emit initial progress
        if job_id:
            emit_progress_update(job_id, {
                'status': 'running',
                'message': 'Getting authors from database...',
                'currentCount': 0
            })
        
        # Get all authors
        authors = db_manager.get_all_authors()
        total_authors = len(authors)
        
        if total_authors == 0:
            raise Exception("No authors found in database")
        
        logger.info(f"Found {total_authors} authors to process")
        
        # Process each author
        processed_count = 0
        total_publications = 0
        
        for i, author in enumerate(authors):
            try:
                author_id = author['id']
                author_name = author['name']
                
                # Emit progress
                if job_id:
                    emit_progress_update(job_id, {
                        'status': 'running',
                        'message': f'Processing {author_name}...',
                        'currentCount': i + 1,
                        'targetCount': total_authors,
                        'currentAuthor': author_name
                    })
                
                # Scrape publications
                publications = scraper.scrape_author_publications(author_id, author_name)
                
                if publications:
                    # Insert to database
                    inserted = db_manager.insert_publications_batch(publications)
                    total_publications += inserted
                    
                    # Update stats
                    db_manager.update_dosen_statistics(author_id)
                
                processed_count += 1
                
            except Exception as e:
                logger.error(f"Error processing author {author.get('name', 'Unknown')}: {e}")
                continue
        
        # Disconnect
        db_manager.disconnect()
        
        result = {
            'success': True,
            'message': f'Google Scholar scraping completed!',
            'summary': {
                'total_authors': total_authors,
                'processed_authors': processed_count,
                'total_publications': total_publications
            }
        }
        
        logger.info(f"SINTA Google Scholar scraping job {job_id} completed successfully")
        return result
        
    except Exception as e:
        logger.error(f"Error in SINTA Google Scholar scraping: {e}")
        raise

def scrape_sinta_garuda_task(username, password, job_id=None):
    """Task untuk scraping SINTA Garuda"""
    try:
        logger.info(f"Starting SINTA Garuda scraping job {job_id}")
        
        # Initialize database and scraper
        db_manager = GarudaDBManager(**DB_CONFIG)
        if not db_manager.connect():
            raise Exception("Failed to connect to database")
        
        scraper = SintaGarudaScraper(db_manager)
        
        # Login
        if not scraper.login(username, password):
            raise Exception("Failed to login to SINTA")
        
        # Emit initial progress
        if job_id:
            emit_progress_update(job_id, {
                'status': 'running',
                'message': 'Getting authors from database...',
                'currentCount': 0
            })
        
        # Get all authors
        authors = db_manager.get_all_dosen_with_sinta()
        total_authors = len(authors)
        
        if total_authors == 0:
            raise Exception("No authors found in database")
        
        logger.info(f"Found {total_authors} authors to process")
        
        # Process each author
        processed_count = 0
        total_publications = 0
        
        for i, author in enumerate(authors):
            try:
                sinta_id = author['sinta_id']
                author_name = author['nama']
                jurusan = author['jurusan']
                
                # Emit progress
                if job_id:
                    emit_progress_update(job_id, {
                        'status': 'running',
                        'message': f'Processing {author_name}...',
                        'currentCount': i + 1,
                        'targetCount': total_authors,
                        'currentAuthor': author_name
                    })
                
                # Scrape publications
                author_data = {
                    'nama': author_name,
                    'sinta_id': sinta_id,
                    'jurusan': jurusan
                }
                
                pub_count = scraper.scrape_author_publications(author_data)
                total_publications += pub_count
                
                processed_count += 1
                
            except Exception as e:
                logger.error(f"Error processing author {author.get('nama', 'Unknown')}: {e}")
                continue
        
        # Disconnect
        db_manager.disconnect()
        
        result = {
            'success': True,
            'message': f'Garuda scraping completed!',
            'summary': {
                'total_authors': total_authors,
                'processed_authors': processed_count,
                'total_publications': total_publications
            }
        }
        
        logger.info(f"SINTA Garuda scraping job {job_id} completed successfully")
        return result
        
    except Exception as e:
        logger.error(f"Error in SINTA Garuda scraping: {e}")
        raise