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
        
        # Validasi input
        required_fields = ['username', 'password', 'affiliation_id', 'target_dosen', 'max_pages', 'max_cycles']
        for field in required_fields:
            if field not in data:
                print(f"❌ Missing field: {field}")
                return jsonify({
                    'success': False,
                    'error': f'Field {field} is required'
                }), 400
        
        # Generate job ID
        job_id = f"sinta_dosen_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        print(f"🆔 Generated job ID: {job_id}")
        
        # Initialize job immediately in active_jobs
        active_jobs[job_id] = {
            'status': 'starting',
            'current': 0,
            'total': data['target_dosen'],
            'message': 'Initializing SINTA Dosen scraping...',
            'started_at': datetime.now().isoformat()
        }
        print(f"✅ Job initialized in active_jobs")
        
        # Prepare task kwargs (WITHOUT job_id, akan ditambahkan di run_scraping_task)
        task_kwargs = {
            'username': data['username'],
            'password': data['password'],
            'affiliation_id': data['affiliation_id'],
            'target_dosen': data['target_dosen'],
            'max_pages': data['max_pages'],
            'max_cycles': data['max_cycles']
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

# ============================================================================
# JOB MANAGEMENT ROUTES - CRITICAL FIX!
# ============================================================================

# ============================================================================
# JOB MANAGEMENT ROUTES
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