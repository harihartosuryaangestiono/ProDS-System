from flask import Blueprint, request, jsonify, current_app
from flask_socketio import emit
import sys
import os
from datetime import datetime
import threading
import traceback

# Add scrapers directory to path
sys.path.append(os.path.join(os.path.dirname(__file__), '..', 'scrapers'))

from utils.database import DB_CONFIG
from task.scraping_tasks import (  # Fixed: changed 'tasks' to 'task'
    scrape_sinta_dosen_task,
    scrape_sinta_scopus_task,
    scrape_sinta_googlescholar_task,
    scrape_sinta_garuda_task
)

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

@scraping_bp.route('/api/scraping/sinta/dosen', methods=['POST'])
def scrape_sinta_dosen():
    """Endpoint untuk scraping data dosen dari SINTA"""
    try:
        data = request.get_json()
        
        # Validate required fields
        required_fields = ['username', 'password', 'affiliation_id']
        for field in required_fields:
            if field not in data or not data[field]:
                return jsonify({
                    'success': False,
                    'error': f'Field {field} is required'
                }), 400
        
        # Generate job ID
        job_id = f"sinta_dosen_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        
        # Start background task
        thread = threading.Thread(
            target=run_scraping_task,
            args=(job_id, scrape_sinta_dosen_task),
            kwargs={
                'username': data['username'],
                'password': data['password'],
                'affiliation_id': data['affiliation_id'],
                'target_dosen': data.get('target_dosen', 473),
                'max_pages': data.get('max_pages', 50),
                'max_cycles': data.get('max_cycles', 20),
                'job_id': job_id
            }
        )
        thread.daemon = True
        thread.start()
        
        return jsonify({
            'success': True,
            'message': 'Scraping job started',
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

@scraping_bp.route('/api/scraping/status/<job_id>', methods=['GET'])
def get_scraping_status(job_id):
    """Get status of a scraping job"""
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
        'jobs': active_jobs
    })