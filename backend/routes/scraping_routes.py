from flask import Blueprint, request, jsonify, current_app
from flask_socketio import emit
import sys
import os
from datetime import datetime
import threading
import traceback

# Add scrapers directory to path
sys.path.append(os.path.join(os.path.dirname(__file__), '..', 'scrapers'))
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from utils.database import DB_CONFIG
from task.scraping_tasks import (
    scrape_sinta_dosen_task,
    scrape_sinta_scopus_task,
    scrape_sinta_googlescholar_task,
    scrape_sinta_garuda_task
)
from flask_cors import cross_origin

scraping_bp = Blueprint('scraping', __name__)

# Store active jobs
active_jobs = {}

def emit_progress(job_id, progress_data):
    """Emit progress update via SocketIO"""
    try:
        from app import socketio
        socketio.emit('scraping_progress', {
            'job_id': job_id,
            'progress': progress_data
        })
        print(f"✅ Progress emitted for job {job_id}: {progress_data.get('message', 'N/A')}")
    except Exception as e:
        print(f"⚠️ Error emitting progress: {e}")

def run_scraping_task(job_id, task_func, task_kwargs):
    """
    Run scraping task in background thread
    
    Args:
        job_id: Unique job identifier
        task_func: Function to execute
        task_kwargs: Dictionary of keyword arguments for task_func
    """
    try:
        print(f"\n🚀 Starting scraping task - Job ID: {job_id}")
        print(f"📝 Task function: {task_func.__name__}")
        print(f"📋 Task kwargs: {list(task_kwargs.keys())}")
        
        # Initialize job with proper structure
        active_jobs[job_id] = {
            'status': 'running',
            'started_at': datetime.now().isoformat(),
            'progress': 0,
            'current': 0,
            'total': task_kwargs.get('target_dosen', 100),
            'message': 'Starting scraping task...'
        }
        
        emit_progress(job_id, active_jobs[job_id])
        
        # Run the task with job_id included in kwargs
        task_kwargs['job_id'] = job_id
        print(f"🔄 Executing task function...")
        result = task_func(**task_kwargs)
        
        # Update job status on completion
        active_jobs[job_id].update({
            'status': 'completed',
            'completed_at': datetime.now().isoformat(),
            'result': result,
            'message': result.get('message', 'Scraping completed successfully!')
        })
        
        print(f"✅ Task completed successfully - Job ID: {job_id}")
        
        # Emit completion
        emit_progress(job_id, {
            'status': 'completed',
            'message': result.get('message', 'Scraping completed!'),
            'result': result
        })
        
    except Exception as e:
        error_msg = str(e)
        traceback_msg = traceback.format_exc()
        
        print(f"\n❌ Task failed - Job ID: {job_id}")
        print(f"Error: {error_msg}")
        print(f"Traceback:\n{traceback_msg}")
        
        active_jobs[job_id].update({
            'status': 'failed',
            'error': error_msg,
            'traceback': traceback_msg,
            'failed_at': datetime.now().isoformat(),
            'message': f'Scraping failed: {error_msg}'
        })
        
        emit_progress(job_id, {
            'status': 'failed',
            'error': error_msg,
            'message': f'Scraping failed: {error_msg}'
        })

# ============================================================================
# SINTA ROUTES
# ============================================================================

@scraping_bp.route('/api/scraping/sinta/dosen', methods=['POST', 'OPTIONS'])
@cross_origin(origins=['http://localhost:5173'], supports_credentials=True)
def scrape_sinta_dosen():
    """Endpoint untuk scraping SINTA Dosen"""
    print("\n" + "="*60)
    print("📥 Received request to /api/scraping/sinta/dosen")
    print("="*60)
    
    # Handle OPTIONS request
    if request.method == 'OPTIONS':
        print("✅ Handling OPTIONS request")
        return '', 204
        
    try:
        data = request.get_json()
        print(f"📋 Request data: {data}")
        
        # Validasi input minimal
        required_fields = ['username', 'password']
        for field in required_fields:
            if field not in data or not data[field]:
                print(f"❌ Missing field: {field}")
                return jsonify({
                    'success': False,
                    'error': f'Field {field} is required'
                }), 400
        
        # Default configuration (optional overrides from request)
        affiliation_id = data.get('affiliation_id') or '1397'
        max_cycles = int(data.get('max_cycles') or 20)
        max_pages = data.get('max_pages')  # akan ditentukan otomatis jika None
        target_dosen = data.get('target_dosen')  # akan ditentukan otomatis jika None
        
        # Generate job ID
        job_id = f"sinta_dosen_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        print(f"🆔 Generated job ID: {job_id}")
        
        # Initialize job immediately in active_jobs
        active_jobs[job_id] = {
            'status': 'starting',
            'current': 0,
            'total': target_dosen or 0,
            'message': 'Initializing SINTA Dosen scraping...',
            'started_at': datetime.now().isoformat()
        }
        print(f"✅ Job initialized in active_jobs")
        
        # Prepare task kwargs (WITHOUT job_id, akan ditambahkan di run_scraping_task)
        task_kwargs = {
            'username': data['username'],
            'password': data['password'],
            'affiliation_id': affiliation_id,
            'target_dosen': target_dosen,
            'max_pages': max_pages,
            'max_cycles': max_cycles
        }
        
        # Start scraping task
        thread = threading.Thread(
            target=run_scraping_task,
            args=(job_id, scrape_sinta_dosen_task, task_kwargs)
        )
        thread.daemon = True
        thread.start()
        print(f"🚀 Background thread started")
        
        response_data = {
            'success': True,
            'message': 'SINTA Dosen scraping started',
            'job_id': job_id
        }
        print(f"📤 Sending response: {response_data}")
        
        return jsonify(response_data), 200
        
    except Exception as e:
        error_msg = str(e)
        traceback_msg = traceback.format_exc()
        print(f"\n❌ ERROR in scrape_sinta_dosen:")
        print(f"Error: {error_msg}")
        print(f"Traceback:\n{traceback_msg}")
        
        return jsonify({
            'success': False,
            'error': error_msg
        }), 500

@scraping_bp.route('/api/scraping/sinta/scopus', methods=['POST'])
def scrape_sinta_scopus():
    """Endpoint untuk scraping publikasi Scopus dari SINTA"""
    try:
        data = request.get_json()
        
        required_fields = ['username', 'password']
        for field in required_fields:
            if field not in data or not data[field]:
                return jsonify({
                    'success': False,
                    'error': f'Field {field} is required'
                }), 400
        
        job_id = f"sinta_scopus_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        
        # Initialize job
        active_jobs[job_id] = {
            'status': 'starting',
            'message': 'Initializing Scopus scraping...',
            'started_at': datetime.now().isoformat()
        }
        
        task_kwargs = {
            'username': data['username'],
            'password': data['password']
        }
        
        thread = threading.Thread(
            target=run_scraping_task,
            args=(job_id, scrape_sinta_scopus_task, task_kwargs)
        )
        thread.daemon = True
        thread.start()
        
        return jsonify({
            'success': True,
            'message': 'Scopus scraping job started',
            'job_id': job_id
        })
        
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@scraping_bp.route('/api/scraping/sinta/googlescholar', methods=['POST'])
def scrape_sinta_googlescholar():
    """Endpoint untuk scraping publikasi Google Scholar dari SINTA"""
    try:
        data = request.get_json()
        
        required_fields = ['username', 'password']
        for field in required_fields:
            if field not in data or not data[field]:
                return jsonify({
                    'success': False,
                    'error': f'Field {field} is required'
                }), 400
        
        job_id = f"sinta_gs_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        
        # Initialize job
        active_jobs[job_id] = {
            'status': 'starting',
            'message': 'Initializing Google Scholar scraping...',
            'started_at': datetime.now().isoformat()
        }
        
        task_kwargs = {
            'username': data['username'],
            'password': data['password']
        }
        
        thread = threading.Thread(
            target=run_scraping_task,
            args=(job_id, scrape_sinta_googlescholar_task, task_kwargs)
        )
        thread.daemon = True
        thread.start()
        
        return jsonify({
            'success': True,
            'message': 'Google Scholar scraping job started',
            'job_id': job_id
        })
        
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@scraping_bp.route('/api/scraping/sinta/garuda', methods=['POST'])
def scrape_sinta_garuda():
    """Endpoint untuk scraping publikasi Garuda dari SINTA"""
    try:
        data = request.get_json()
        
        required_fields = ['username', 'password']
        for field in required_fields:
            if field not in data or not data[field]:
                return jsonify({
                    'success': False,
                    'error': f'Field {field} is required'
                }), 400
        
        job_id = f"sinta_garuda_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        
        # Initialize job
        active_jobs[job_id] = {
            'status': 'starting',
            'message': 'Initializing Garuda scraping...',
            'started_at': datetime.now().isoformat()
        }
        
        task_kwargs = {
            'username': data['username'],
            'password': data['password']
        }
        
        thread = threading.Thread(
            target=run_scraping_task,
            args=(job_id, scrape_sinta_garuda_task, task_kwargs)
        )
        thread.daemon = True
        thread.start()
        
        return jsonify({
            'success': True,
            'message': 'Garuda scraping job started',
            'job_id': job_id
        })
        
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

# ============================================================================
# CANCEL ENDPOINT
# ============================================================================
@scraping_bp.route('/api/scraping/jobs/<job_id>/cancel', methods=['POST'])
def cancel_job(job_id):
    try:
        job = active_jobs.get(job_id)
        if not job:
            return jsonify({'success': False, 'error': 'Job not found'}), 404

        # Mark cancel requested
        job['cancel_requested'] = True
        job['status'] = 'cancelling'
        job['message'] = 'Cancellation requested by user'

        emit_progress(job_id, job)
        return jsonify({'success': True, 'message': 'Cancellation requested', 'job_id': job_id})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

# ============================================================================
# GOOGLE SCHOLAR ROUTE
# ============================================================================
def run_google_scholar_scraping(job_id, max_authors, scrape_from_beginning):
    """Run Google Scholar scraping in background thread"""
    try:
        from gs_scraper import GoogleScholarScraper
        
        active_jobs[job_id] = {
            'status': 'running',
            'current': 0,
            'total': max_authors,
            'message': 'Initializing scraper...',
            'started_at': datetime.now().isoformat()
        }
        
        emit_progress(job_id, active_jobs[job_id])
        
        # Create scraper instance
        scraper = GoogleScholarScraper(
            db_config=DB_CONFIG,
            job_id=job_id,
            progress_callback=lambda data: emit_progress(job_id, data)
        )
        
        # Run scraping
        result = scraper.run(max_authors=max_authors, scrape_from_beginning=scrape_from_beginning)
        
        active_jobs[job_id]['status'] = 'completed'
        active_jobs[job_id]['message'] = 'Scraping completed successfully!'
        active_jobs[job_id]['completed_at'] = datetime.now().isoformat()
        active_jobs[job_id]['result'] = result
        
        emit_progress(job_id, {
            'status': 'completed',
            'message': result.get('message', 'Scraping completed'),
            'summary': result.get('summary', {})
        })
        
    except Exception as e:
        import traceback
        error_msg = str(e)
        traceback_msg = traceback.format_exc()
        
        print(f"\n❌ ERROR: {error_msg}")
        print(f"Traceback:\n{traceback_msg}")
        
        active_jobs[job_id]['status'] = 'failed'
        active_jobs[job_id]['message'] = error_msg
        active_jobs[job_id]['error'] = error_msg
        active_jobs[job_id]['traceback'] = traceback_msg
        active_jobs[job_id]['failed_at'] = datetime.now().isoformat()
        
        emit_progress(job_id, {
            'status': 'failed',
            'error': error_msg
        })

@scraping_bp.route('/api/scraping/googlescholar/scrape', methods=['POST'])
def scrape_google_scholar():
    """
    Endpoint to start Google Scholar scraping directly (not through SINTA)
    """
    try:
        data = request.get_json() or {}
        max_authors = data.get('max_authors', 10)
        scrape_from_beginning = data.get('scrape_from_beginning', False)
        
        # Validate input
        if not isinstance(max_authors, int) or max_authors <= 0:
            return jsonify({
                'success': False,
                'error': 'max_authors must be a positive integer'
            }), 400
        
        # Generate job ID
        job_id = f"gs_scrape_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        
        # Initialize job
        active_jobs[job_id] = {
            'status': 'starting',
            'current': 0,
            'total': max_authors,
            'message': 'Initializing Google Scholar scraping...',
            'started_at': datetime.now().isoformat()
        }
        
        # Start scraping in background thread
        thread = threading.Thread(
            target=run_google_scholar_scraping,
            args=(job_id, max_authors, scrape_from_beginning)
        )
        thread.daemon = True
        thread.start()
        
        return jsonify({
            'success': True,
            'message': 'Google Scholar scraping started. Browser will open for manual login.',
            'job_id': job_id,
            'instructions': 'Please login to Google Scholar in the browser window, then press Enter in the terminal.'
        }), 200
    
    except Exception as e:
        import traceback
        return jsonify({
            'success': False,
            'error': str(e),
            'traceback': traceback.format_exc()
        }), 500
    
def run_google_scholar_dosen_scraping(job_id, max_pages, search_query):
    """Run Google Scholar dosen scraping in background thread with auto-login"""
    try:
        # Import fungsi dari dosen_unpar.py
        from dosen_unpar import get_all_unpar_scholars
        
        active_jobs[job_id] = {
            'status': 'running',
            'current': 0,
            'total': max_pages * 10,  # Estimasi 10 dosen per halaman
            'message': 'Initializing scraper with auto-login...',
            'started_at': datetime.now().isoformat()
        }
        
        emit_progress(job_id, active_jobs[job_id])
        
        # Update status: auto-login in progress
        active_jobs[job_id]['status'] = 'logging_in'
        active_jobs[job_id]['message'] = 'Auto-login in progress... This may take a few minutes.'
        emit_progress(job_id, active_jobs[job_id])
        
        # Run scraping dengan auto-login (driver dibuat otomatis di dalam fungsi)
        # Fungsi akan membuat driver sendiri dengan auto-login
        scholars_data = get_all_unpar_scholars(
            max_pages=max_pages,
            driver=None,  # Driver akan dibuat otomatis
            search_query=search_query
        )
        
        # Process results
        if scholars_data:
            import pandas as pd
            df = pd.DataFrame(scholars_data)
            
            # Remove duplicates
            df_clean = df.drop_duplicates(subset=["Profile URL"])
            
            # Update status: saving to database
            active_jobs[job_id]['status'] = 'saving'
            active_jobs[job_id]['message'] = f'Scraping complete. Saving {len(df_clean)} scholars to database...'
            emit_progress(job_id, active_jobs[job_id])
            
            # Save to database
            from utils.database import get_db_connection
            conn = get_db_connection()
            cursor = conn.cursor()
            
            inserted = 0
            updated = 0
            
            for idx, row in df_clean.iterrows():
                try:
                    # Check if scholar already exists
                    cursor.execute(
                        "SELECT id FROM dosen WHERE id_google_scholar = %s",
                        (row['ID Google Scholar'],)
                    )
                    existing = cursor.fetchone()
                    
                    if existing:
                        # Update existing record
                        cursor.execute("""
                            UPDATE dosen 
                            SET nama = %s, citations = %s, profile_url_gs = %s, updated_at = NOW()
                            WHERE id_google_scholar = %s
                        """, (row['Name'], row['Citations'], row['Profile URL'], row['ID Google Scholar']))
                        updated += 1
                    else:
                        # Insert new record
                        cursor.execute("""
                            INSERT INTO dosen (id_google_scholar, nama, afiliasi, citations, profile_url_gs, created_at)
                            VALUES (%s, %s, %s, %s, %s, NOW())
                        """, (row['ID Google Scholar'], row['Name'], row['Affiliation'], 
                              row['Citations'], row['Profile URL']))
                        inserted += 1
                    
                    # Update progress
                    current = inserted + updated
                    active_jobs[job_id]['current'] = current
                    active_jobs[job_id]['message'] = f'Saving: {current}/{len(df_clean)} scholars'
                    emit_progress(job_id, active_jobs[job_id])
                    
                except Exception as e:
                    print(f"Warning: Error processing scholar {row.get('Name', 'Unknown')}: {e}")
                    continue
            
            conn.commit()
            cursor.close()
            conn.close()
            
            result = {
                'success': True,
                'message': f'Successfully scraped and saved {len(df_clean)} scholars',
                'summary': {
                    'total_scraped': len(df_clean),
                    'inserted': inserted,
                    'updated': updated
                }
            }
        else:
            result = {
                'success': False,
                'message': 'No scholars data found. This might be due to login failure or no results.',
                'summary': {
                    'total_scraped': 0,
                    'inserted': 0,
                    'updated': 0
                }
            }
        
        active_jobs[job_id]['status'] = 'completed'
        active_jobs[job_id]['message'] = result['message']
        active_jobs[job_id]['completed_at'] = datetime.now().isoformat()
        active_jobs[job_id]['result'] = result
        
        emit_progress(job_id, {
            'status': 'completed',
            'message': result['message'],
            'summary': result.get('summary', {})
        })
        
    except Exception as e:
        import traceback
        error_msg = str(e)
        traceback_msg = traceback.format_exc()
        
        print(f"\n❌ ERROR: {error_msg}")
        print(f"Traceback:\n{traceback_msg}")
        
        active_jobs[job_id]['status'] = 'failed'
        active_jobs[job_id]['message'] = error_msg
        active_jobs[job_id]['error'] = error_msg
        active_jobs[job_id]['traceback'] = traceback_msg
        active_jobs[job_id]['failed_at'] = datetime.now().isoformat()
        
        emit_progress(job_id, {
            'status': 'failed',
            'error': error_msg
        })

@scraping_bp.route('/api/scraping/googlescholar/dosen', methods=['POST'])
def scrape_google_scholar_dosen():
    """
    Endpoint to start Google Scholar dosen profile scraping with auto-login
    
    Request Body:
    {
        "max_pages": 100,  // optional, default: 100
        "search_query": "..." // optional, default: UNPAR query
    }
    
    Response:
    {
        "success": true,
        "message": "...",
        "job_id": "gs_dosen_20250110_123456",
        "instructions": "..."
    }
    """
    try:
        data = request.get_json() or {}
        max_pages = data.get('max_pages', 100)
        search_query = data.get('search_query', '"Universitas Katolik Parahyangan" OR "Parahyangan Catholic University" OR "unpar"')
        
        # Validate input
        if not isinstance(max_pages, int) or max_pages <= 0:
            return jsonify({
                'success': False,
                'error': 'max_pages must be a positive integer'
            }), 400
        
        # Limit max_pages to prevent abuse
        if max_pages > 500:
            return jsonify({
                'success': False,
                'error': 'max_pages cannot exceed 500'
            }), 400
        
        if not search_query or not isinstance(search_query, str):
            return jsonify({
                'success': False,
                'error': 'search_query must be a non-empty string'
            }), 400
        
        # Generate job ID
        job_id = f"gs_dosen_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        
        # Initialize job
        active_jobs[job_id] = {
            'status': 'starting',
            'current': 0,
            'total': max_pages * 10,
            'message': 'Initializing Google Scholar dosen scraping with auto-login...',
            'started_at': datetime.now().isoformat()
        }
        
        # Start scraping in background thread
        thread = threading.Thread(
            target=run_google_scholar_dosen_scraping,
            args=(job_id, max_pages, search_query)
        )
        thread.daemon = True
        thread.start()
        
        return jsonify({
            'success': True,
            'message': 'Google Scholar dosen scraping started with auto-login.',
            'job_id': job_id,
            'instructions': 'The scraper will automatically login using the configured accounts. No manual action required.',
            'max_pages': max_pages,
            'search_query': search_query
        }), 200
    
    except Exception as e:
        import traceback
        return jsonify({
            'success': False,
            'error': str(e),
            'traceback': traceback.format_exc()
        }), 500


@scraping_bp.route('/api/scraping/googlescholar/dosen/status/<job_id>', methods=['GET'])
def get_scraping_status(job_id):
    """
    Get status of a scraping job
    
    Response:
    {
        "success": true,
        "job_id": "gs_dosen_20250110_123456",
        "status": "running|completed|failed",
        "current": 50,
        "total": 1000,
        "message": "...",
        "started_at": "2025-01-10T12:34:56",
        "completed_at": "2025-01-10T12:45:30",  // if completed
        "result": {...}  // if completed
    }
    """
    try:
        if job_id not in active_jobs:
            return jsonify({
                'success': False,
                'error': f'Job {job_id} not found'
            }), 404
        
        job_data = active_jobs[job_id]
        
        return jsonify({
            'success': True,
            'job_id': job_id,
            **job_data
        }), 200
    
    except Exception as e:
        import traceback
        return jsonify({
            'success': False,
            'error': str(e),
            'traceback': traceback.format_exc()
        }), 500


@scraping_bp.route('/api/scraping/googlescholar/dosen/jobs', methods=['GET'])
def list_scraping_jobs():
    """
    List all scraping jobs
    
    Response:
    {
        "success": true,
        "jobs": [
            {
                "job_id": "gs_dosen_20250110_123456",
                "status": "completed",
                "message": "...",
                ...
            }
        ]
    }
    """
    try:
        jobs_list = [
            {'job_id': job_id, **job_data}
            for job_id, job_data in active_jobs.items()
        ]
        
        # Sort by started_at (newest first)
        jobs_list.sort(key=lambda x: x.get('started_at', ''), reverse=True)
        
        return jsonify({
            'success': True,
            'jobs': jobs_list,
            'total': len(jobs_list)
        }), 200
    
    except Exception as e:
        import traceback
        return jsonify({
            'success': False,
            'error': str(e),
            'traceback': traceback.format_exc()
        }), 500

# ============================================================================
# JOB MANAGEMENT ROUTES - CRITICAL FIX!
# ============================================================================

@scraping_bp.route('/api/scraping/jobs/<job_id>', methods=['GET'])
def get_job_status(job_id):
    """Get status of a specific scraping job"""
    print(f"\n📊 Job status requested for: {job_id}")
    print(f"📋 Active jobs: {list(active_jobs.keys())}")
    
    if job_id in active_jobs:
        job_data = active_jobs[job_id]
        print(f"✅ Job found: {job_data}")
        return jsonify({
            'success': True,
            'job': job_data
        }), 200
    else:
        print(f"❌ Job not found: {job_id}")
        return jsonify({
            'success': False,
            'error': 'Job not found'
        }), 404

@scraping_bp.route('/api/scraping/jobs', methods=['GET'])
def list_jobs():
    """List all scraping jobs"""
    print(f"\n📋 Listing all jobs - Total: {len(active_jobs)}")
    return jsonify({
        'success': True,
        'jobs': active_jobs,
        'total_jobs': len(active_jobs)
    }), 200

@scraping_bp.route('/api/scraping/jobs/<job_id>', methods=['DELETE'])
def delete_job(job_id):
    """Delete/clear a job from memory"""
    if job_id in active_jobs:
        del active_jobs[job_id]
        return jsonify({
            'success': True,
            'message': f'Job {job_id} deleted'
        }), 200
    else:
        return jsonify({
            'success': False,
            'error': 'Job not found'
        }), 404

@scraping_bp.route('/api/scraping/health', methods=['GET'])
def scraping_health():
    """Health check for scraping service"""
    running_jobs = len([j for j in active_jobs.values() if j.get('status') == 'running'])
    return jsonify({
        'success': True,
        'status': 'healthy',
        'active_jobs_count': running_jobs,
        'total_jobs': len(active_jobs),
        'jobs': list(active_jobs.keys())
    }), 200