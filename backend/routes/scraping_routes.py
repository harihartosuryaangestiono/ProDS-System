from flask import Blueprint, request, jsonify, current_app
from flask_socketio import emit
import sys
import os
from datetime import datetime
import threading
import traceback
import random
import time

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
    except Exception as e:
        print(f"Error emitting progress: {e}")

def run_scraping_task(job_id, task_func, **kwargs):
    """Run scraping task in background thread"""
    try:
        active_jobs[job_id] = {
            'status': 'running',
            'started_at': datetime.now().isoformat(),
            'progress': 0
        }
        
        # Run the task
        result = task_func(**kwargs)
        
        # Update job status
        active_jobs[job_id] = {
            'status': 'completed',
            'completed_at': datetime.now().isoformat(),
            'result': result
        }
        
        # Emit completion
        emit_progress(job_id, {
            'status': 'completed',
            'result': result
        })
        
    except Exception as e:
        error_msg = str(e)
        traceback_msg = traceback.format_exc()
        
        active_jobs[job_id] = {
            'status': 'failed',
            'error': error_msg,
            'traceback': traceback_msg,
            'failed_at': datetime.now().isoformat()
        }
        
        emit_progress(job_id, {
            'status': 'failed',
            'error': error_msg
        })

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
# ============================================================================
# SINTA ROUTES
# ============================================================================

@scraping_bp.route('/api/scraping/sinta/dosen', methods=['POST', 'OPTIONS'])
@cross_origin(origins=['http://localhost:5173'], supports_credentials=True)
def scrape_sinta_dosen():
    """Endpoint untuk scraping SINTA Dosen"""
    # Handle OPTIONS request
    if request.method == 'OPTIONS':
        return '', 204
        
    try:
        data = request.get_json()
        
        # Validasi input
        required_fields = ['username', 'password', 'affiliation_id', 'target_dosen', 'max_pages', 'max_cycles']
        for field in required_fields:
            if field not in data:
                return jsonify({
                    'success': False,
                    'error': f'Field {field} is required'
                }), 400
        
        # Generate job ID
        job_id = f"sinta_dosen_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        
        # Start scraping task
        thread = threading.Thread(
            target=run_scraping_task,
            args=(job_id, scrape_sinta_dosen_task),
            kwargs={
                'username': data['username'],
                'password': data['password'],
                'affiliation_id': data['affiliation_id'],
                'target_dosen': data['target_dosen'],
                'max_pages': data['max_pages'],
                'max_cycles': data['max_cycles'],
                'job_id': job_id
            }
        )
        thread.daemon = True
        thread.start()
        
        return jsonify({
            'success': True,
            'message': 'SINTA Dosen scraping started',
            'job_id': job_id
        })
        
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
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
        
        thread = threading.Thread(
            target=run_scraping_task,
            args=(job_id, scrape_sinta_scopus_task),
            kwargs={
                'username': data['username'],
                'password': data['password'],
                'job_id': job_id
            }
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
        
        thread = threading.Thread(
            target=run_scraping_task,
            args=(job_id, scrape_sinta_googlescholar_task),
            kwargs={
                'username': data['username'],
                'password': data['password'],
                'job_id': job_id
            }
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
        
        thread = threading.Thread(
            target=run_scraping_task,
            args=(job_id, scrape_sinta_garuda_task),
            kwargs={
                'username': data['username'],
                'password': data['password'],
                'job_id': job_id
            }
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
# GOOGLE SCHOLAR ROUTE
# ============================================================================

@scraping_bp.route('/api/scraping/googlescholar/scrape', methods=['POST'])
def scrape_google_scholar():
    """
    Endpoint to start Google Scholar scraping directly (not through SINTA)
    """
    try:
        data = request.get_json() or {}
        max_authors = data.get('max_authors', 10)
        
        # Validate input
        if not isinstance(max_authors, int) or max_authors <= 0:
            return jsonify({
                'success': False,
                'error': 'max_authors must be a positive integer'
            }), 400
        
        # Generate job ID
        job_id = f"gs_scrape_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        
        # Get socketio instance from app
        try:
            from app import socketio
        except ImportError:
            return jsonify({
                'success': False,
                'error': 'SocketIO not configured properly'
            }), 500
        
        # Start scraping in background thread
        thread = threading.Thread(
            target=run_google_scholar_scraping,
            args=(job_id, max_authors, socketio)
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

# ============================================================================
# JOB MANAGEMENT ROUTES
# ============================================================================

@scraping_bp.route('/api/scraping/jobs/<job_id>', methods=['GET'])
def get_job_status(job_id):
    """Get status of a specific scraping job"""
    if job_id in active_jobs:
        return jsonify({
            'success': True,
            'job': active_jobs[job_id]
        })
    else:
        return jsonify({
            'success': False,
            'error': 'Job not found'
        }), 404

@scraping_bp.route('/api/scraping/jobs', methods=['GET'])
def list_jobs():
    """List all scraping jobs"""
    return jsonify({
        'success': True,
        'jobs': active_jobs,
        'total_jobs': len(active_jobs)
    })

@scraping_bp.route('/api/scraping/jobs/<job_id>', methods=['DELETE'])
def delete_job(job_id):
    """Delete/clear a job from memory"""
    if job_id in active_jobs:
        del active_jobs[job_id]
        return jsonify({
            'success': True,
            'message': f'Job {job_id} deleted'
        })
    else:
        return jsonify({
            'success': False,
            'error': 'Job not found'
        }), 404

@scraping_bp.route('/api/scraping/health', methods=['GET'])
def scraping_health():
    """Health check for scraping service"""
    return jsonify({
        'success': True,
        'status': 'healthy',
        'active_jobs_count': len([j for j in active_jobs.values() if j.get('status') == 'running']),
        'total_jobs': len(active_jobs)
    })